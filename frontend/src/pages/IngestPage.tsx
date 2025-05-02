// frontend/src/pages/IngestPage.tsx ---
import React, { useState, useEffect, useRef } from 'react';
import {
    triggerUrlIngestion,
    triggerKeywordIngestion,
    getKeywordSessionStatus,
} from '../services/apiClient';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
// Alias KeywordSearchSessionResponse to avoid naming conflict and clarify its use here.
import type { DiscoveryChainSummary, KeywordSearchSessionResponse as KeywordResult } from '../services/apiClient';
import './IngestPage.css';

/**
 * Interface for Keyword Polling State.
 * Extends the API result type (`KeywordResult`) to include additional
 * UI-specific state related to the polling process itself, like errors
 * encountered during polling and whether polling is currently active.
 */
interface KeywordPollState extends KeywordResult {
    /** Stores error messages specifically related to the polling fetch operation. Null if no polling error. */
    error: string | null;
    /** Flag indicating if the component is actively polling for status updates for this session. */
    isPolling: boolean;
}

/**
 * `IngestPage` Component
 *
 * This component provides the user interface for initiating data ingestion processes.
 * It allows users to ingest data either by providing a direct URL to a GitHub repository
 * or by specifying keywords to discover and subsequently ingest relevant repositories.
 * For keyword-based ingestion, it handles triggering the backend process and then
 * polls the backend periodically to display the status and progress of the keyword search session.
 */
const IngestPage: React.FC = () => {
    // --- State for URL Ingestion ---
    /** The URL input value entered by the user. */
    const [url, setUrl] = useState<string>('');
    /** Loading state flag specifically for the URL ingestion API request. True while the request is in flight. */
    const [isUrlLoading, setIsUrlLoading] = useState<boolean>(false);
    /** Stores any error message returned from the URL ingestion API request or network errors. */
    const [urlError, setUrlError] = useState<string | null>(null);
    /** Stores the success response (summary) from the URL ingestion API request. */
    const [urlSuccess, setUrlSuccess] = useState<DiscoveryChainSummary | null>(null);

    // --- State for Keyword Ingestion ---
    /** The keywords input value entered by the user. */
    const [keywords, setKeywords] = useState<string>('');
    /** Loading state flag specifically for the initial API call to *trigger* keyword ingestion. True while the trigger request is in flight. */
    const [isKeywordLoading, setIsKeywordLoading] = useState<boolean>(false);
    /** Stores any error message related to the *initial trigger* of the keyword ingestion process. */
    const [keywordError, setKeywordError] = useState<string | null>(null);
    /** State to hold the latest keyword search session data received from polling, plus polling-specific UI state (isPolling flag, polling errors). Initialized to null. */
    const [pollState, setPollState] = useState<KeywordPollState | null>(null);
    /** Ref to hold the ID returned by `window.setInterval`, used to clear the interval when polling stops. Type is number | null. */
    const pollIntervalRef = useRef<number | null>(null); // Type is number | null

    // --- URL Ingestion Handler ---
    /**
     * Handles the submission event for the URL ingestion form.
     * It prevents the default form submission, sets loading states,
     * calls the `triggerUrlIngestion` API endpoint, and updates the state
     * with the result (success or error).
     * @param event The form submission event object.
     */
    const handleUrlSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault(); // Prevent default browser form submission
        setIsUrlLoading(true);  // Set loading state for UI feedback
        setUrlError(null);      // Clear any previous errors
        setUrlSuccess(null);    // Clear any previous success messages
        try {
            // Call the API service to trigger ingestion
            const result = await triggerUrlIngestion(url);
            setUrlSuccess(result); // Store the success response
            console.log(`URL Ingestion success. Root chain ID: ${result.id}, Status: ${result.status}`);
            // Optionally provide specific feedback based on the immediate status returned
            if (result.status === 'FAILED') {
                 setUrlError(`Ingestion failed. Check logs for chain ${result.id}.`);
            } else if (result.status !== 'COMPLETED') {
                 // Note: COMPLETED might not be the status immediately upon triggering
                 setUrlError(`Ingestion ended with status ${result.status}. Check logs for chain ${result.id}.`);
            }
            setUrl(''); // Clear the input field after submission
        } catch (error: any) {
            // Handle errors from the API call or network issues
            setUrlError(error.message || 'An unknown error occurred during URL ingestion.');
        } finally {
            // Ensure loading state is turned off regardless of success or failure
            setIsUrlLoading(false);
        }
    };

    // --- Keyword Ingestion Handler ---
    /**
     * Handles the submission event for the keyword ingestion form.
     * Prevents default submission, sets loading state for the trigger action,
     * resets any previous polling state, calls the `triggerKeywordIngestion` API,
     * and if successful, initializes the `pollState` and starts the polling process.
     * @param event The form submission event object.
     */
    const handleKeywordSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault(); // Prevent default browser form submission
        setIsKeywordLoading(true); // Set loading state for the *trigger* action
        setKeywordError(null);    // Clear previous *trigger* errors
        setPollState(null);       // Reset previous session's polling state completely
        stopPolling();            // Stop any previous polling interval just in case

        try {
            // Call the API service to trigger keyword ingestion and get initial session data
            const initialSession = await triggerKeywordIngestion(keywords);
            // Update pollState with the initial data received and mark polling as active
            setPollState({
                ...initialSession, // Spread the data from the API response (id, status='QUEUED', etc.)
                error: null,       // Clear any previous polling error
                isPolling: true,   // Indicate that polling should now be active
            });
            console.log(`Keyword Ingestion queued. Session ID: ${initialSession.id}`);
            startPolling(initialSession.id); // Initiate the polling mechanism
            setKeywords(''); // Clear the input field upon successful queueing
        } catch (error: any) {
            // Handle errors during the *initial trigger* request
            setKeywordError(error.message || 'An unknown error occurred triggering keyword search.');
            setPollState(null); // Ensure no polling state remains if the trigger failed
        } finally {
            // Ensure the trigger loading indicator is turned off
            setIsKeywordLoading(false);
        }
    };

    // --- Polling Logic ---
    /**
     * Clears the active polling interval timer stored in `pollIntervalRef`.
     * It also updates the `pollState` (using a functional update to avoid stale state)
     * to set the `isPolling` flag to false, preserving the last known session data.
     * This function is designed to be callable multiple times without adverse effects.
     */
    const stopPolling = () => {
        if (pollIntervalRef.current !== null) {
            window.clearInterval(pollIntervalRef.current); // Clear the scheduled interval
            pollIntervalRef.current = null; // Reset the ref
            // Update the state to reflect that polling has stopped.
            // Uses functional update form to ensure we're modifying the latest state.
            setPollState(prev => {
                // Only modify the state if it exists and was previously polling.
                if (prev && prev.isPolling) {
                    // Return a new state object with isPolling set to false, keeping other data.
                    return { ...prev, isPolling: false };
                }
                // If state is null or wasn't polling, return it unchanged.
                return prev;
            });
            console.log("Polling stopped.");
        }
    };

    /**
     * Initiates the polling process for a specific keyword search session.
     * It first stops any existing polling interval, then performs an immediate
     * status check, and finally sets up a recurring interval timer (`setInterval`)
     * to call the status check function repeatedly.
     * @param sessionId The ID of the keyword search session to poll.
     */
    const startPolling = (sessionId: number) => {
        stopPolling(); // Ensure no duplicate intervals are running.

        /**
         * The core polling function executed at each interval.
         * It checks if polling should still be active for the *current* session ID.
         * If so, it calls the `getKeywordSessionStatus` API, updates the `pollState`
         * with the latest session status, and handles potential errors or session completion.
         */
        const poll = async () => {
             // Check if we are still supposed to be polling *this* session before making the API call.
             // This uses a functional update of setPollState to reliably get the *current* state
             // without causing a re-render itself, just to read the value.
            let shouldStop = false;
            setPollState(currentState => {
                // If there's no state, or polling is inactive, or the session ID doesn't match, polling should stop.
                if (!currentState || !currentState.isPolling || currentState.id !== sessionId) {
                    shouldStop = true;
                    // No state change needed here, just signal to stop the timer.
                    return currentState;
                }
                // Otherwise, continue polling.
                return currentState;
            });

            // If the check above determined polling should stop, clear the interval and exit.
            if (shouldStop) {
                 stopPolling();
                 return;
             }

            // Proceed with the API call if polling is still active for this session.
            try {
                console.log(`Polling status for session ID: ${sessionId}`);
                // Fetch the latest status from the API.
                const sessionStatus = await getKeywordSessionStatus(sessionId);

                // Update the component's state with the received status.
                // Use functional update to base changes on the most recent previous state.
                setPollState(prev => {
                    // Only apply update if the fetched status is for the session we are currently tracking.
                    if (prev && prev.id === sessionId) {
                        // Determine if the session has reached a terminal state (COMPLETED or FAILED).
                        const isStillPolling = !(sessionStatus.status === 'COMPLETED' || sessionStatus.status === 'FAILED');

                        console.log(`Updating poll state for ${sessionId}: New status=${sessionStatus.status}, isStillPolling=${isStillPolling}`);

                        // If polling was active but the new status is terminal, stop the interval timer immediately.
                        if (!isStillPolling && prev.isPolling) {
                            stopPolling(); // This will clear the interval via the stopPolling function.
                        }

                        // Return the new state object, merging the latest API data and the calculated polling status.
                        return {
                           ...sessionStatus,         // Update with latest data from API
                           error: null,             // Clear any previous *polling* error message
                           isPolling: isStillPolling, // Set the flag for whether polling should continue in the *next* cycle
                        };
                    }
                    // If the session ID changed (e.g., user started a new search), ignore this stale result.
                    return prev;
                });

                // No need for a separate stop polling check here, it's handled within the state update logic.

            } catch (error: any) {
                 // Handle errors during the polling API call itself.
                 console.error(`Error polling status for session ${sessionId}:`, error);
                 stopPolling(); // Stop the polling timer on fetch error.
                 // Update the state to show the polling error message.
                 setPollState(prev => {
                     // Ensure the error is associated with the correct session ID.
                     if (prev && prev.id === sessionId) {
                        return {
                           ...prev, // Keep the last known session data
                           error: `Polling failed: ${error.message}`, // Display the polling error
                           isPolling: false, // Ensure polling is marked as stopped
                         };
                     }
                     // Ignore error if it pertains to a session ID we are no longer tracking.
                     return prev;
                 });
            }
        };

        poll(); // Perform an initial poll immediately without waiting for the first interval.
        // Set up the recurring interval timer.
        pollIntervalRef.current = window.setInterval(poll, 5000); // Poll every 5 seconds.
    };


    // --- Component Lifecycle Effect ---
    /**
     * Cleanup effect hook. Runs when the component is unmounted.
     * Its purpose is to clear any active polling interval timer to prevent
     * memory leaks and unnecessary background activity after the user
     * navigates away from the page.
     */
    useEffect(() => {
        // The function returned by useEffect is the cleanup function.
        return () => {
            stopPolling(); // Call stopPolling to clear the interval.
        };
    }, []); // Empty dependency array ensures this effect runs only on mount and unmount.

    // --- Render Helper for Keyword Status ---
    /**
     * Renders the status display section for the keyword search session.
     * Uses the data stored in `pollState` to show the session ID, keywords,
     * current status (with specific text variations), progress (results count),
     * relevant timestamps, and any errors encountered during polling.
     * Displays a loading spinner if the session is actively being polled and in a non-terminal state.
     * @returns JSX element representing the keyword status display, or null if no poll state exists.
     */
    const renderKeywordStatus = () => {
        // Do not render anything if there's no poll state or the state lacks a session ID.
        if (!pollState || pollState.id === null || pollState.id === undefined) return null;

        // Determine the display text and styling based on the current poll state.
        let statusText = `Status: ${pollState.status || 'Unknown'}`;
        // Generate a CSS class based on the status for potential styling.
        let statusClass = `status-${(pollState.status || 'unknown').toLowerCase()}`;
        // Show the spinner if polling is active AND the status is one indicating work is in progress.
        let showSpinner = pollState.isPolling && (pollState.status === 'QUEUED' || pollState.status === 'RUNNING');

        const results = pollState.results_count ?? 0; // Use nullish coalescing for default value

        // Provide more descriptive status text for different states.
        if (pollState.status === 'COMPLETED') {
            statusText = `Status: COMPLETED (Processed ${results} repositories)`; // Changed "Found" to "Processed" for clarity
        }
        if (pollState.status === 'FAILED') {
            statusText = `Status: FAILED`;
        }
        if (pollState.status === 'QUEUED'){
            statusText = `Status: QUEUED...`;
        }
        // Show RUNNING status text consistently while in that state.
        if (pollState.status === 'RUNNING'){
             statusText = `Status: RUNNING... (Processed ${results} so far)`;
        }


        // Construct the JSX for the status display area.
        return (
            <div className={`keyword-status ${statusClass}`}>
                <p><strong>Keyword Search Session ID: {pollState.id}</strong></p>
                 {pollState.keywords_raw && <p><strong>Keywords:</strong> {pollState.keywords_raw}</p>}
                {/* Flex container for status text and spinner */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <p style={{ margin: 0 }}>{statusText}</p>
                    {/* Conditionally render the loading spinner */}
                    {showSpinner && <LoadingSpinner message="" />}
                </div>
                {/* Display polling-specific error messages */}
                {pollState.error && <ErrorMessage message={pollState.error} />}
                 {/* Display timestamps if available, formatted for readability */}
                 {pollState.created_at && (
                    <p><small>Queued At: {new Date(pollState.created_at).toLocaleString()}</small></p>
                )}
                {/* Show 'Started At' only if the session has actually started (not QUEUED) */}
                {pollState.started_at && pollState.status !== 'QUEUED' && (
                    <p><small>Started At: {new Date(pollState.started_at).toLocaleString()}</small></p>
                )}
                {/* Show 'Completed At' if the timestamp is available */}
                {pollState.completed_at && (
                    <p><small>Completed At: {new Date(pollState.completed_at).toLocaleString()}</small></p>
                )}
            </div>
        );
    };


    // --- Component Render ---
    return (
        <div className="ingest-page">
            <h2>Ingest Data</h2>

            {/* Section for Ingesting by URL */}
            <section className="ingest-section">
                <h3>Ingest by Repository URL</h3>
                {/* URL Ingestion Form */}
                <form onSubmit={handleUrlSubmit} className="ingest-form">
                    <div className="form-group">
                        <label htmlFor="url">GitHub Repository URL:</label>
                        <input
                            type="url"
                            id="url"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="https://github.com/owner/repo"
                            required
                            // Disable input field while the URL submission is in progress.
                            disabled={isUrlLoading}
                        />
                    </div>
                    {/* Submit button for URL ingestion */}
                    <button type="submit" disabled={isUrlLoading || !url}>
                        {/* Show spinner inside button when loading */}
                        {isUrlLoading ? <LoadingSpinner message="" /> : 'Ingest URL'}
                    </button>
                </form>
                {/* Display error message if URL ingestion fails */}
                {urlError && <ErrorMessage message={urlError} />}
                {/* Display success message and details after URL ingestion trigger */}
                {urlSuccess && (
                    // Apply a dynamic class based on the status for potential styling
                    <div className={`success-message status-${urlSuccess.status?.toLowerCase()}`}>
                        <p>URL Ingestion Task Status: <strong>{urlSuccess.status || 'Unknown'}</strong></p>
                        {/* Provide user-friendly messages based on the resulting status */}
                        {urlSuccess.status === 'COMPLETED' && <p>Ingestion completed successfully.</p>}
                        {urlSuccess.status === 'FAILED' && <p>Ingestion failed. Check server logs.</p>}
                        {/* Handle non-terminal statuses that might be returned immediately */}
                        {urlSuccess.status !== 'COMPLETED' && urlSuccess.status !== 'FAILED' && <p>Ingestion ended with unexpected status.</p>}
                        <p><small>Root Discovery Chain ID: {urlSuccess.id}</small></p>
                    </div>
                )}
            </section>

            {/* Section for Ingesting by Keywords */}
            <section className="ingest-section">
                <h3>Discover & Ingest by Keywords</h3>
                {/* Keyword Ingestion Form */}
                <form onSubmit={handleKeywordSubmit} className="ingest-form">
                    <div className="form-group">
                        <label htmlFor="keywords">Keywords:</label>
                        <input
                            type="text"
                            id="keywords"
                            value={keywords}
                            onChange={(e) => setKeywords(e.target.value)}
                            placeholder="e.g., scientific computing python"
                            required
                            // Disable input field while the initial keyword trigger is loading OR while polling is active.
                            disabled={isKeywordLoading || pollState?.isPolling}
                        />
                    </div>
                    {/* Submit button for keyword ingestion */}
                    <button type="submit" disabled={isKeywordLoading || pollState?.isPolling || !keywords}>
                         {/* Button text/content changes based on the current state */}
                        {isKeywordLoading ? <LoadingSpinner message="" /> : (pollState?.isPolling ? 'Processing...' : 'Search & Ingest')}
                    </button>
                </form>
                 {/* Display error message if the initial keyword trigger fails */}
                {keywordError && <ErrorMessage message={keywordError} />}
                {/* Render the dynamic status display area for keyword polling */}
                {renderKeywordStatus()}
            </section>
        </div>
    );
};

export default IngestPage;