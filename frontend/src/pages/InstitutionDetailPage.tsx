// frontend/src/pages/InstitutionDetailPage.tsx ---
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
    getInstitution,
    getInstitutionRepositories,
    getInstitutionAffiliationsFiltered, // API client function for fetching filtered affiliations
} from '../services/apiClient';
import LoadingSpinner, { LoadingSpinnerProps } from '../components/LoadingSpinner'; // Import props type for explicit prop passing
import ErrorMessage, { ErrorMessageProps } from '../components/ErrorMessage'; // Import props type for explicit prop passing
import SimpleTable, { SimpleTableProps } from '../components/SimpleTable'; // Import props type for explicit prop passing
import type {
    InstitutionResponse,
    RepositorySummary,
    AffiliationResultResponse,
} from '../services/apiClient'; // Import relevant API response types
import './DetailPage.css'; // Shared detail page styles

// --- State Type Definitions ---

/** Defines the structure for storing the state related to linked repositories,
 * including the repository data array, loading status, and any potential error message. */
interface LinkedReposState {
    repos: RepositorySummary[];
    loading: boolean;
    error: string | null;
}

/** Defines the structure for storing the state related to calculated affiliations,
 * including the affiliation data array, loading status, and any potential error message. */
interface AffiliationsState {
    affiliations: AffiliationResultResponse[];
    loading: boolean;
    error: string | null;
}

/**
 * `InstitutionDetailPage` Component
 *
 * Displays detailed information about a specific institution identified by its ID
 * from the URL parameters. It fetches the main institution data and then fetches
 * related data like linked repositories (via works) and calculated affiliations.
 * It handles loading and error states for each data fetch operation.
 */
const InstitutionDetailPage: React.FC = () => {
  // --- Hooks and State Initialization ---

  /** Extracts the 'id' parameter from the current URL using react-router's useParams hook. */
  const { id } = useParams<{ id: string }>();
  /** Parses the extracted ID string into an integer. Defaults to 0 if ID is missing or invalid. */
  const institutionId = parseInt(id ?? '0', 10);

  /** State for storing the main institution data fetched from the API. Null initially or if not found. */
  const [institution, setInstitution] = useState<InstitutionResponse | null>(null);
  /** Loading state for the initial fetch of the main institution data. True while fetching. */
  const [loading, setLoading] = useState<boolean>(true);
  /** Error state for the initial fetch of the main institution data. Null if no error. */
  const [error, setError] = useState<string | null>(null);

  /** State object holding the list of linked repositories, their loading status, and any fetch error. */
  const [linkedRepos, setLinkedRepos] = useState<LinkedReposState>({ repos: [], loading: false, error: null });
  /** State object holding the list of calculated affiliations, their loading status, and any fetch error. */
  const [affiliations, setAffiliations] = useState<AffiliationsState>({ affiliations: [], loading: false, error: null });


  // --- Data Fetching Callbacks ---

  /**
   * Fetches repositories linked to the given institution ID (typically via associated works).
   * Uses useCallback to memoize the function, preventing unnecessary re-creation on re-renders.
   * Updates the `linkedRepos` state with loading status, results, or error information.
   * @param instId The ID of the institution for which to fetch linked repositories.
   */
  const fetchLinkedRepositories = useCallback(async (instId: number) => {
        // Set loading state immediately before starting the fetch.
        setLinkedRepos({ repos: [], loading: true, error: null });
        try {
            // Call the API service function.
            const repoData = await getInstitutionRepositories(instId);
            // Update state with the fetched data on success.
            setLinkedRepos({ repos: repoData, loading: false, error: null });
        } catch (err: any) {
            // Update state with the error message on failure.
            setLinkedRepos({ repos: [], loading: false, error: err.message || 'Failed to fetch linked repositories.' });
        }
    }, []); // Empty dependency array: function doesn't depend on props or state, won't change.

  /**
   * Fetches calculated affiliation data (linking repositories to this institution)
   * for the given institution ID. Uses useCallback for memoization.
   * Updates the `affiliations` state with loading status, results, or error information.
   * @param instId The ID of the institution for which to fetch affiliation data.
   */
  const fetchAffiliationData = useCallback(async (instId: number) => {
      // Set loading state immediately before starting the fetch.
      setAffiliations({ affiliations: [], loading: true, error: null });
      try {
          // Call the API service function.
          const data = await getInstitutionAffiliationsFiltered(instId);
          // Update state with the fetched data on success.
          setAffiliations({ affiliations: data, loading: false, error: null });
      } catch (err: any) {
          // Update state with the error message on failure.
          setAffiliations({ affiliations: [], loading: false, error: err.message || 'Failed to fetch affiliations.' });
      }
  }, []); // Empty dependency array: function doesn't depend on props or state.


  // --- Effects ---

  /**
   * Effect Hook for fetching initial data.
   * Runs when the component mounts or when `institutionId` changes.
   * It validates the ID, fetches the main institution details, and upon success,
   * triggers the fetching of related data (linked repositories and affiliations).
   * Handles loading and error states for the primary fetch.
   */
  useEffect(() => {
    // Validate the institution ID extracted from the URL.
    if (!institutionId || isNaN(institutionId) || institutionId <= 0) {
         setError('Institution ID is missing or invalid.'); // Set error message.
         setLoading(false); // Stop the main loading indicator.
         return; // Exit the effect early.
    }

    /** Asynchronous function to perform the main data fetching sequence. */
    const fetchInstitution = async () => {
       // Reset states before starting fetch: main loading ON, errors OFF, related data cleared.
       setLoading(true);
       setError(null);
       setLinkedRepos({ repos: [], loading: false, error: null });
       setAffiliations({ affiliations: [], loading: false, error: null });

      try {
        // Fetch the primary institution data.
        const data = await getInstitution(institutionId);
        setInstitution(data); // Update state with the fetched institution data.
        // Trigger fetches for related data *after* the main institution data is successfully fetched.
        fetchLinkedRepositories(institutionId);
        fetchAffiliationData(institutionId);
      } catch (err: any) {
        // Handle errors during the primary institution fetch.
        setError(err.message || 'Failed to fetch institution details.');
      } finally {
        // Ensure the main loading indicator is turned off regardless of success or failure.
        setLoading(false);
      }
    };

    // Execute the fetch function.
    fetchInstitution();
  }, [institutionId, fetchLinkedRepositories, fetchAffiliationData]); // Dependencies: re-run if ID or fetch functions change.


  // --- Render Helper Functions ---

    /**
     * Renders a section displaying a list of linked items (specifically Repositories in this usage).
     * Handles loading, error, and empty states for the provided data state.
     * Creates links to the detail pages of the linked items.
     * @param title The title to display for this section.
     * @param state The state object (`LinkedReposState`) containing the data, loading, and error status.
     * @param linkPrefix The base path for the links to individual item detail pages (e.g., "/repositories/").
     * @param emptyMessage The message to display if the list is empty after loading and without errors.
     * @returns JSX element representing the linked items section.
     */
    const renderLinkedItems = (
        title: string,
        state: LinkedReposState,
        linkPrefix: string,
        emptyMessage: string
    ) => {
        // Define props for child components (LoadingSpinner, ErrorMessage) for clarity, even if empty.
        // This makes it easier to add props like 'message' later if needed.
        const loadingProps: LoadingSpinnerProps = {}; // Example: { message: 'Loading items...' }
        const errorProps = (msg: string): ErrorMessageProps => ({ message: msg });

        return (
            <div className="detail-section"> {/* Container for the section */}
                <h4>{title}</h4> {/* Section title */}
                {/* Show loading spinner while data is being fetched */}
                {state.loading && <LoadingSpinner {...loadingProps} />}
                {/* Show error message if fetching failed */}
                {state.error && <ErrorMessage {...errorProps(state.error)} />}
                {/* Show the list if not loading, no error, and data exists */}
                {!state.loading && !state.error && state.repos.length > 0 && (
                    <ul>
                        {/* Map over the repository data to create list items */}
                        {state.repos.map(item => (
                            <li key={item.id}>
                                {/* Link to the repository's detail page */}
                                <Link to={`${linkPrefix}/${item.id}`}> {/* Corrected Link usage with template literal */}
                                    {/* Display repository name or fallback to ID */}
                                    {item.full_name || `ID ${item.id}`}
                                </Link>
                                {/* Optionally display the primary language */}
                                {item.language && ` (${item.language})`}
                            </li>
                        ))}
                    </ul>
                )}
                {/* Show empty message if not loading, no error, and no data */}
                {!state.loading && !state.error && state.repos.length === 0 && <p>{emptyMessage}</p>}
            </div>
        );
    };

    /**
     * Renders a section displaying calculated affiliations in a table.
     * Handles loading, error, and empty states for the affiliation data.
     * Formats the data and passes it to the `SimpleTable` component.
     * @param state The state object (`AffiliationsState`) containing the affiliation data, loading, and error status.
     * @returns JSX element representing the affiliations table section.
     */
     const renderAffiliationsList = (
        state: AffiliationsState
    ) => {
        // Prepare props for child components.
        const loadingProps: LoadingSpinnerProps = {};
        const errorProps = (msg: string): ErrorMessageProps => ({ message: msg });

        // Handle loading state: show only the title and spinner.
        if (state.loading) return <div className="detail-section"><h4>Calculated Repository Affiliations</h4><LoadingSpinner {...loadingProps} /></div>;
        // Handle error state: show only the title and error message.
        if (state.error) return <div className="detail-section"><h4>Calculated Repository Affiliations</h4><ErrorMessage {...errorProps(state.error)} /></div>;
        // Handle empty state: show title and 'not found' message.
        if (state.affiliations.length === 0) return <div className="detail-section"><h4>Calculated Repository Affiliations</h4><p>No calculated affiliations found.</p></div>;

        // --- Prepare data for the SimpleTable component ---
        // Map the raw affiliation data to the structure expected by the table.
        const tableData = state.affiliations.map(aff => ({
            // Create a link to the affiliated repository's detail page.
            repository: <Link to={`/repositories/${aff.repository_id}`}>{aff.repository_name}</Link>,
            // Format confidence score to 3 decimal places.
            confidence: aff.confidence_score.toFixed(3),
            // Combine algorithm name and version.
            algorithm: `${aff.algorithm_name} v${aff.algorithm_version}`,
            // Format the calculation timestamp to a locale date string.
            calculated_at: new Date(aff.calculated_at).toLocaleDateString(),
        }));
        // Define the column headers for the table.
        const headers = ['Repository', 'Confidence', 'Algorithm', 'Calculated At'];

        // Define the props object to be passed to the SimpleTable component.
        const tableProps: SimpleTableProps = { headers, data: tableData };

        // Render the section title and the table.
        return (
            <div className="detail-section">
                <h4>Calculated Repository Affiliations</h4>
                {/* Render the SimpleTable component, passing the prepared props */}
                {/* --- CORRECTED (comment refers to previous code state): Pass props object --- */}
                <SimpleTable {...tableProps} />
                {/* --- END CORRECTION (comment refers to previous code state) --- */}
            </div>
         );
    };


  // --- Main Component Render Logic ---

  // Display loading spinner if the main institution data is loading.
  if (loading && !institution) return <div className="detail-container"><LoadingSpinner /></div>;
  // Display error message if fetching the main institution data failed.
  if (error && !institution) return <div className="detail-container"><ErrorMessage message={error} /></div>;
  // Display 'not found' message if loading finished without error but no institution data was retrieved.
  if (!institution) return <div className="detail-container"><p>Institution not found or ID is invalid.</p></div>;

  // --- Render the main detail page content if institution data is available ---
  return (
    <div className="detail-container institution-detail"> {/* Main container with specific class */}
      {/* Page Title: Institution Name */}
      <h2>Institution: {institution.display_name}</h2>

       {/* Section for core institution details */}
       <div className="detail-section">
           <h3>Details</h3>
           <p><strong>ID:</strong> {institution.id}</p>
           {/* Link to external OpenAlex page */}
           <p><strong>OpenAlex ID:</strong> <a href={`https://openalex.org/${institution.openalex_id}`} target="_blank" rel="noopener noreferrer">{institution.openalex_id}</a></p>
           {/* Link to external ROR page if ROR ID exists */}
           <p><strong>ROR:</strong> {institution.ror ? <a href={`https://ror.org/${institution.ror}`} target="_blank" rel="noopener noreferrer">{institution.ror}</a> : 'N/A'}</p>
           <p><strong>Type:</strong> {institution.type || 'N/A'}</p>
           <p><strong>Country Code:</strong> {institution.country_code || 'N/A'}</p>
           {/* Display potential GitHub org logins if available */}
           {institution.github_organization_logins && institution.github_organization_logins.length > 0 && (
                <p><strong>Potential GitHub Orgs:</strong> {institution.github_organization_logins.join(', ')}</p>
           )}
           {/* Display internal timestamps */}
           <p><small>Created in MOSS: {new Date(institution.created_at).toLocaleString()}</small></p>
           <p><small>Updated in MOSS: {new Date(institution.updated_at).toLocaleString()}</small></p>
       </div>

      {/* Separator line */}
      <hr />

        {/* Render the linked repositories section using the helper function */}
        {renderLinkedItems(
           "Linked Repositories (via Works)", // Section title
           linkedRepos,                       // State object containing repo data
           "/repositories",                   // Base URL for repository links
           "No repositories found linked via works." // Empty state message
       )}

       {/* Render the affiliations table section using the helper function */}
       {renderAffiliationsList(affiliations)} {/* Pass the affiliations state object */}

    </div> // End detail-container
  );
};

export default InstitutionDetailPage;