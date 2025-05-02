// --- CORRECTED FILE: frontend/src/pages/WorkDetailPage.tsx ---
import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
    getWork, getWorkRepositories, getWorkCitations, getWorkReferences,
    getWorkCitingPeople, getWorkCitingInstitutions, handleApiError, // API client functions and types
    type WorkResponse, type RepositorySummary, type WorkSummary, type PersonSummary, type InstitutionSummary, // Use import type for types
    // --- ADDED Topic/Hierarchy Interfaces ---
    type PrimaryTopicResponse, type TopicSummary // Use import type for topic-related types
    // --- END ADDED ---
} from '../services/apiClient';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import GraphDisplay from '../components/GraphDisplay'; // Component for visualizing relationships
import { Node, Edge } from 'reactflow'; // Types for the graph display
import './DetailPage.css'; // Shared detail page styles

// --- Render Helper Functions ---

/**
 * Generic helper function to render a list of linked items (e.g., Repositories, Works, People).
 * Handles loading, error, and empty states for the list. Creates links to the detail pages
 * of the items using the provided link prefix.
 * @template T The type of items in the list, constrained to have an `id` and optional display fields.
 * @param title The heading to display for the list section.
 * @param items The array of items to display. Can be null or undefined.
 * @param linkPrefix The base path for the detail page links (e.g., "/repositories/").
 * @param isLoading Boolean indicating if the data for this list is currently loading.
 * @param error String containing an error message if loading failed, otherwise null.
 * @returns JSX element representing the linked items list section.
 */
// Helper function to render lists of linked items (unchanged comment, as function is unchanged)
const renderLinkedItems = <T extends { id: number; display_name?: string | null; full_name?: string | null; title?: string | null }>(
    title: string,
    items: T[] | null | undefined,
    linkPrefix: string,
    isLoading: boolean,
    error: string | null
) => {
    // Display loading state
    if (isLoading) return <div><LoadingSpinner /> Loading {title}...</div>;
    // Display error state
    if (error) return <ErrorMessage message={`Error loading ${title}: ${error}`} />;
    // Display message if no items are found after loading without error
    if (!items || items.length === 0) return <div>No {title} found.</div>;

    // Render the list if items exist
    return (
        <div>
            <h4>{title} ({items.length})</h4> {/* Title with item count */}
            <ul>
                {/* Map over items to create list entries */}
                {items.map((item) => (
                    <li key={item.id}> {/* Unique key for React */}
                        {/* Link to the item's detail page */}
                        <Link to={`${linkPrefix}${item.id}`}>
                            {/* Display preferred name/title, falling back to ID */}
                            {item.display_name || item.full_name || item.title || `ID: ${item.id}`}
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
};


/**
 * `WorkDetailPage` Component
 *
 * Displays detailed information about a specific scholarly work (e.g., paper, dataset description)
 * identified by its ID from the URL parameters. Fetches the main work data and various related
 * entities like referencing repositories, citations, references, citing people/institutions,
 * and topic information. Also visualizes direct relationships in a graph.
 */
function WorkDetailPage() {
    // --- Hooks and State Initialization ---

    /** Extracts the 'id' parameter from the URL. */
    const { id } = useParams<{ id: string }>();
    /** Parses the extracted ID string into a number. */
    const workId = Number(id); // Use Number() which handles null/undefined better than parseInt for this case

    // State for the main work data
    /** Stores the main work data fetched from the API. Null initially or if not found/error. */
    const [workData, setWorkData] = useState<WorkResponse | null>(null);
    /** Loading state for the initial fetch of the main work data. True while fetching. */
    const [isLoading, setIsLoading] = useState<boolean>(true);
    /** Error state for the initial fetch of the main work data. Null if no error. */
    const [error, setError] = useState<string | null>(null);

    // State for related items fetched separately
    /** Stores the list of repositories referencing this work. */
    const [repositories, setRepositories] = useState<RepositorySummary[] | null>(null);
    /** Stores the list of works citing this work. */
    const [citations, setCitations] = useState<WorkSummary[] | null>(null);
    /** Stores the list of works referenced by this work. */
    const [references, setReferences] = useState<WorkSummary[] | null>(null);
    /** Stores the list of people whose works cite this work. */
    const [citingPeople, setCitingPeople] = useState<PersonSummary[] | null>(null);
    /** Stores the list of institutions whose works cite this work. */
    const [citingInstitutions, setCitingInstitutions] = useState<InstitutionSummary[] | null>(null);

    // State to track loading status for each related data type individually
    /** Stores loading flags for each related data fetch (e.g., repositories, citations). */
    const [loadingRelated, setLoadingRelated] = useState<Record<string, boolean>>({
        repositories: false, citations: false, references: false, citingPeople: false, citingInstitutions: false
    });
    // State to track error status for each related data type individually
    /** Stores error messages for each related data fetch. Null if no error for that category. */
    const [errorRelated, setErrorRelated] = useState<Record<string, string | null>>({
        repositories: null, citations: null, references: null, citingPeople: null, citingInstitutions: null
    });

    // State for the relationship graph visualization
    /** Stores the nodes (works, repos) for the react-flow graph display. */
    const [graphNodes, setGraphNodes] = useState<Node[]>([]);
    /** Stores the edges (relationships) for the react-flow graph display. */
    const [graphEdges, setGraphEdges] = useState<Edge[]>([]);

    // --- Helper Functions for Managing Related Data State ---

    /**
     * Updates the loading state for a specific related data category.
     * @param key The key corresponding to the related data type (e.g., 'repositories').
     * @param loading The new loading state (true or false).
     */
    const setRelatedLoadState = (key: string, loading: boolean) => {
        setLoadingRelated(prev => ({ ...prev, [key]: loading }));
    };
    /**
     * Updates the error state for a specific related data category.
     * @param key The key corresponding to the related data type.
     * @param errorMsg The error message string, or null to clear the error.
     */
    const setRelatedErrorState = (key: string, errorMsg: string | null) => {
        setErrorRelated(prev => ({ ...prev, [key]: errorMsg }));
    };


    // --- Effects ---

    /**
     * Effect Hook to fetch the main work data when the component mounts or `workId` changes.
     * Handles loading and error states for this primary fetch. Also initializes the graph
     * with the main work node upon successful fetch. Includes a cleanup function to prevent
     * state updates if the component unmounts during the fetch.
     */
    // Fetch main work data (unchanged comment)
    useEffect(() => {
        // Validate the work ID early.
        if (!workId) {
            setError("Invalid Work ID.");
            setIsLoading(false);
            return;
        }
        let isMounted = true; // Flag to track if the component is still mounted.
        setIsLoading(true); // Set loading state ON.
        setError(null); // Clear previous errors.

        // Call the API function to get work details.
        getWork(workId)
            .then(data => {
               // Only update state if the component is still mounted.
               if (isMounted) {
                    setWorkData(data); // Store the fetched work data.
                    // Initialize the graph with the main work node.
                    setGraphNodes([{ id: `work-${workId}`, data: { label: data.title || `Work ${workId}` }, position: { x: 250, y: 5 }, type: 'input' }]);
                    setGraphEdges([]); // Clear any previous edges.
               }
            })
            .catch(err => {
                // Use the shared error handler and update state only if mounted.
                if(isMounted) setError(handleApiError(err))
            })
            .finally(() => {
                // Turn off loading state only if mounted.
                if(isMounted) setIsLoading(false)
            });

        // Cleanup function: Set isMounted to false when the component unmounts.
        return () => { isMounted = false };
    }, [workId]); // Dependency: Re-run this effect if workId changes.

    /**
     * Effect Hook to fetch all related data (repositories, citations, references, etc.)
     * after the main work data has been potentially loaded (triggered by `workId` change).
     * Uses a helper async function `fetchRelated` to handle fetching, loading state,
     * and error state for each category individually. Includes cleanup logic.
     */
    // Fetch related data (unchanged comment)
    useEffect(() => {
        if (!workId) return; // Don't fetch if workId is invalid
        let isMounted = true; // Prevent state update on unmounted component

        /**
         * Helper async function to fetch a specific category of related data.
         * Manages loading and error states for the given category key.
         * @template T The expected type of the data being fetched.
         * @param key The key identifying the data category (must match keys in loadingRelated/errorRelated).
         * @param fetcher An async function that performs the API call.
         * @param setter The React state setter function to update with the fetched data.
         */
        const fetchRelated = async <T,>(
            key: keyof typeof loadingRelated, // Use keyof for type safety on state keys
            fetcher: () => Promise<T>, // The API call function
            setter: React.Dispatch<React.SetStateAction<T | null>> // The state setter
        ) => {
            // Set loading ON and clear error for this specific category.
            setRelatedLoadState(key, true);
            setRelatedErrorState(key, null);
            try {
                // Perform the API call.
                const data = await fetcher();
                // Update state only if component is still mounted.
                if (isMounted) setter(data);
            } catch (err) {
                 // Handle API errors using the shared handler and update state if mounted.
                 if (isMounted) setRelatedErrorState(key, handleApiError(err));
            } finally {
                // Turn off loading state for this category if mounted.
                if (isMounted) setRelatedLoadState(key, false);
            }
        };

        // Initiate fetches for all related data categories concurrently.
        fetchRelated('repositories', () => getWorkRepositories(workId), setRepositories);
        fetchRelated('citations', () => getWorkCitations(workId), setCitations);
        fetchRelated('references', () => getWorkReferences(workId), setReferences);
        fetchRelated('citingPeople', () => getWorkCitingPeople(workId), setCitingPeople);
        fetchRelated('citingInstitutions', () => getWorkCitingInstitutions(workId), setCitingInstitutions);

         // Cleanup function for this effect.
         return () => { isMounted = false };

    }, [workId]); // Dependency: Re-fetch all related data if workId changes.


    /**
     * Effect Hook to update the graph nodes and edges whenever the main work data
     * or any of the relevant related data arrays (repositories, citations, references) change.
     * It reconstructs the nodes and edges arrays based on the available data.
     */
    // Update graph nodes and edges when related data loads (unchanged comment)
    useEffect(() => {
        // Ensure main work data is loaded before building graph.
        if (!workData) return;

        const newNodes: Node[] = []; // Array to hold newly generated nodes
        // Ensure workId is valid before using it for the main node ID.
        if (workId) {
            // Add the central node for the current work.
            newNodes.push({ id: `work-${workId}`, data: { label: workData.title || `Work ${workId}` }, position: { x: 250, y: 5 }, type: 'input' });
        } else {
             // Log a warning if workId is missing, can happen briefly or if URL is invalid.
             console.warn("Work ID missing when trying to build graph");
             setGraphNodes([]); // Clear graph state
             setGraphEdges([]);
             return; // Stop graph generation
        }

        const newEdges: Edge[] = []; // Array to hold newly generated edges
        let yOffset = 150; // Initial Y offset for the first row of related nodes
        const xOffsetStep = 180; // Horizontal spacing between related nodes in a row

        /**
         * Helper function to add nodes and edges for a specific category of related items.
         * @param items Array of related items (e.g., repositories, works).
         * @param type String identifier for the item type (used in node IDs).
         * @param labelKey The key in the item object containing the display label (e.g., 'full_name', 'title').
         * @param linkPrefix Base path for detail page links (not used directly here but kept for consistency).
         * @param edgeLabel Label text for the edges connecting to the main work node.
         * @param currentYOffset The starting Y coordinate for this row of nodes.
         * @returns The updated Y offset for the next row.
         */
        const addNodesAndEdges = (
            items: any[] | null | undefined, // Input array of items
            type: string, // Type identifier (e.g., 'repo', 'work')
            labelKey: string, // Key for the label text in the item object
            linkPrefix: string, // Base URL prefix (unused here)
            edgeLabel: string, // Label for the edge
            currentYOffset: number // Current Y position
        ): number => {
            // Process only if items array exists and is not empty.
            if (items && items.length > 0) {
                 // Limit the number of nodes per category for performance/clarity (e.g., first 10).
                 items.slice(0, 10).forEach((item, index) => {
                    // Generate a unique node ID.
                    const nodeId = `${type}-${item.id}`;
                    // Add the node to the array.
                    newNodes.push({
                        id: nodeId,
                        data: { label: item[labelKey] || `${type} ${item.id}` }, // Use labelKey or fallback
                        position: { x: index * xOffsetStep, y: currentYOffset } // Position horizontally
                    });
                    // Add the edge connecting this node to the main work node.
                    newEdges.push({
                        id: `e-work-${workId}-${type}-${item.id}`, // Unique edge ID
                        source: `work-${workId}`, // Source is the main work node
                        target: nodeId, // Target is the related item node
                        label: edgeLabel, // Edge label text
                        // Optionally animate citation/reference edges.
                        animated: type === 'citation' || type === 'reference'
                    });
                });
                // Return the Y offset for the next row, adding spacing.
                return currentYOffset + 150;
            }
            // If no items, return the current Y offset unchanged.
            return currentYOffset;
        };

        // Call the helper function for each relevant related data category.
        yOffset = addNodesAndEdges(repositories, 'repo', 'full_name', '/repositories/', 'Referenced In', yOffset);
        yOffset = addNodesAndEdges(citations, 'work', 'title', '/works/', 'Cited By', yOffset);
        yOffset = addNodesAndEdges(references, 'work', 'title', '/works/', 'References', yOffset);

        // Update the component state with the newly generated nodes and edges.
        setGraphNodes(newNodes);
        setGraphEdges(newEdges);

    }, [workData, workId, repositories, citations, references]); // Dependencies: Re-run graph generation if these change.


    /**
     * Renders the topic information section, displaying the primary topic hierarchy
     * and a list of secondary topics. Handles cases where topic data might be missing.
     * @returns JSX element for the topic information section, or null if no work data.
     */
    // --- MODIFIED: Render Topic Information ---
    const renderTopicInfo = () => {
        // Return null if the main work data hasn't loaded yet.
        if (!workData) return null;

        // Access primary and secondary topic data using optional chaining safely.
        const primary: PrimaryTopicResponse | null | undefined = workData.primary_topic;
        // Filter secondary topics to exclude the primary one if it exists.
        const secondary: TopicSummary[] | undefined = workData.topics?.filter(t => t.id !== primary?.id);

        let primaryTopicString = "N/A"; // Default string if no primary topic
        // Construct the hierarchical string for the primary topic if it exists.
        if (primary) {
            // Safely access nested display names and build the hierarchy string.
            const domainStr = primary.domain?.display_name ? ` / ${primary.domain.display_name} (Domain)` : "";
            const fieldStr = primary.field?.display_name ? ` / ${primary.field.display_name} (Field)` : "";
            const subfieldStr = primary.subfield?.display_name ? ` / ${primary.subfield.display_name} (Subfield)` : "";
            // Format the score if available.
            const scoreStr = primary.score !== null && primary.score !== undefined ? ` (Score: ${primary.score.toFixed(3)})` : "";

            // Combine parts into the final string.
            primaryTopicString = `${primary.display_name} (Topic)${scoreStr}${subfieldStr}${fieldStr}${domainStr}`;
        }

        // Render the topic section.
        return (
            <div className="detail-section">
                <h3>Subject Information</h3>
                <p><strong>Primary Topic:</strong> {primaryTopicString}</p>
                {/* Render secondary topics only if the array exists and is not empty */}
                {secondary && secondary.length > 0 && (
                    <>
                        <p><strong>Other Topics:</strong></p>
                        <ul>
                            {/* List secondary topic names */}
                            {secondary.map(topic => (
                                <li key={topic.id}>{topic.display_name}</li>
                                // Potential enhancement: Add links to a future Topic detail page here.
                            ))}
                        </ul>
                    </>
                )}
                {/* Display a message only if *both* primary and secondary topics are unavailable */}
                { !primary && (!secondary || secondary.length === 0) && (
                     <p>No topic information available.</p>
                )}
            </div>
        );
    };
     // --- END MODIFIED ---


    // --- Main Component Render Logic ---

    // Display global loading spinner while the main work data is loading.
    if (isLoading) return <div className="detail-container"><LoadingSpinner /> Loading Work Details...</div>;
    // Display global error message if the main work fetch failed.
    if (error) return <div className="detail-container"><ErrorMessage message={error} /></div>;
    // Display message if loading finished without error but no work data was retrieved.
    if (!workData) return <div className="detail-container"><ErrorMessage message="Work data could not be loaded." /></div>;


    // --- Render the main detail page content if work data is available ---
    return (
        <div className="detail-container"> {/* Main container */}
            {/* Page Title */}
            <h2>Work: {workData.title || 'N/A'}</h2>
            {/* Grid layout for details and related items */}
            <div className="detail-grid">
                {/* --- Left Column: Core Info & Topics --- */}
                <div> {/* Wrapper div for left column content */}
                    {/* Section for core work details */}
                    <div className="detail-section">
                        <h3>Details</h3>
                         <p><strong>ID:</strong> {workData.id}</p>
                        <p><strong>OpenAlex ID:</strong> {workData.openalex_id || 'N/A'}</p>
                        {/* Link to DOI resolver */}
                        <p><strong>DOI:</strong> {workData.doi ? <a href={`https://doi.org/${workData.doi}`} target="_blank" rel="noopener noreferrer">{workData.doi}</a> : 'N/A'}</p>
                        <p><strong>Publication Year:</strong> {workData.publication_year || 'N/A'}</p>
                        <p><strong>Type:</strong> {workData.type || 'N/A'}</p>
                        <p><strong>Cited By Count (OpenAlex):</strong> {workData.cited_by_count ?? 'N/A'}</p>
                        <p><strong>Host Venue:</strong> {workData.host_venue_display_name || 'N/A'}</p>
                        {/* Link to OpenAlex page */}
                        {workData.openalex_url && <p><a href={workData.openalex_url} target="_blank" rel="noopener noreferrer">View on OpenAlex</a></p>}
                    </div>

                    {/* --- ADDED Call to Render Topic Info --- */}
                    {/* Render the topic information section */}
                    {renderTopicInfo()}
                    {/* --- END ADDED --- */}
                </div>

                {/* --- Right Column: Related Entities --- */}
                <div> {/* Wrapper div for right column content */}
                    {/* Render related repositories */}
                    <div className="detail-section">
                        {renderLinkedItems('Repositories Referencing This Work', repositories, '/repositories/', loadingRelated['repositories'], errorRelated['repositories'])}
                    </div>
                    {/* Render references (works cited by this work) */}
                    <div className="detail-section">
                        {renderLinkedItems('Works Cited By This Work (References)', references, '/works/', loadingRelated['references'], errorRelated['references'])}
                    </div>
                    {/* Render citations (works citing this work) */}
                    <div className="detail-section">
                        {renderLinkedItems('Works Citing This Work', citations, '/works/', loadingRelated['citations'], errorRelated['citations'])}
                    </div>
                    {/* Render citing people */}
                    <div className="detail-section">
                         {renderLinkedItems('People Citing This Work', citingPeople, '/persons/', loadingRelated['citingPeople'], errorRelated['citingPeople'])}
                    </div>
                    {/* Render citing institutions */}
                     <div className="detail-section">
                         {renderLinkedItems('Institutions Citing This Work', citingInstitutions, '/institutions/', loadingRelated['citingInstitutions'], errorRelated['citingInstitutions'])}
                    </div>
                </div>
            </div> {/* End detail-grid */}

            {/* --- Graph Visualization Section --- */}
            {/* (unchanged comment block) */}
            <div className="detail-section graph-section">
                <h3>Relationship Graph</h3>
                {/* Render the graph display component, passing nodes and edges */}
                <GraphDisplay initialNodes={[]} initialEdges={[]} nodes={graphNodes} edges={graphEdges} />
            </div>
        </div> // End detail-container
    );
}

export default WorkDetailPage;