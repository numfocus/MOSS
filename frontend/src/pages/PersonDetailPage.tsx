// --- FILE: frontend/src/pages/PersonDetailPage.tsx ---
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPerson, getPersonWorks } from '../services/apiClient'; // API client functions
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import type { PersonResponse, WorkSummary } from '../services/apiClient'; // API response types

/**
 * Defines the structure for storing the state related to works authored by the person,
 * including the works data array, loading status, and any potential error message.
 */
interface AuthoredWorksState {
    /** Array of WorkSummary objects representing the works authored by the person. */
    works: WorkSummary[];
    /** Boolean flag indicating if the authored works data is currently being fetched. */
    loading: boolean;
    /** String containing an error message if fetching authored works failed, otherwise null. */
    error: string | null;
}

/**
 * `PersonDetailPage` Component
 *
 * Displays detailed information about a specific person identified by an ID
 * from the URL parameters. It fetches the main person data and then fetches
 * the list of works authored by that person. Handles loading and error states
 * for these data fetches.
 */
const PersonDetailPage: React.FC = () => {
  // --- Hooks and State Initialization ---

  /** Extracts the 'id' parameter from the current URL using react-router's useParams hook. */
  const { id } = useParams<{ id: string }>();
  /** Parses the extracted ID string into an integer. Defaults to 0 if ID is missing or invalid. */
  const personId = parseInt(id || '0', 10);

  /** State for storing the main person data fetched from the API. Null initially or if not found. */
  const [person, setPerson] = useState<PersonResponse | null>(null);
  /** Loading state primarily for the initial fetch of the main person data. True while fetching. */
  const [loading, setLoading] = useState<boolean>(true);
  /** Error state primarily for the initial fetch of the main person data. Null if no error. */
  const [error, setError] = useState<string | null>(null);
  /** State object holding the list of authored works, their loading status, and any fetch error. */
  const [authoredWorks, setAuthoredWorks] = useState<AuthoredWorksState>({ works: [], loading: false, error: null });

  // --- Data Fetching Callbacks ---

  /**
   * Fetches the list of works authored by the specified person ID.
   * Uses useCallback to memoize the function, preventing unnecessary re-creation.
   * Updates the `authoredWorks` state with loading status, results, or error information.
   * It also manages the *main* loading state (`setLoading(false)`) in its `finally` block,
   * assuming the page load is complete once both person and works (or an error) are processed.
   * @param persId The ID of the person for whom to fetch authored works.
   */
  const fetchAuthoredWorks = useCallback(async (persId: number) => {
        // Set loading state specifically for authored works before fetching.
        setAuthoredWorks({ works: [], loading: true, error: null });
        try {
            // Call the API service function to get works.
            const worksData = await getPersonWorks(persId);
            // Update state with the fetched works data on success.
            setAuthoredWorks({ works: worksData, loading: false, error: null });
        } catch (err: any) {
            // Update state with the error message on failure.
            setAuthoredWorks({ works: [], loading: false, error: err.message || 'Failed to fetch authored works.' });
        } finally {
            // Indicate that the overall page loading process (person + initial works attempt) is complete.
            // This might be adjusted if more parallel/independent loading indicators are desired.
            setLoading(false); // Combined loading state update
        }
    }, []); // Empty dependency array: function itself doesn't depend on props or state.

  // --- Effects ---

  /**
   * Effect Hook for fetching initial data.
   * Runs when the component mounts or when `personId` changes.
   * Validates the ID, fetches the main person details, and upon success,
   * triggers the fetching of authored works using `fetchAuthoredWorks`.
   * Manages the primary loading and error states (`loading`, `error`).
   */
  useEffect(() => {
      // Validate the person ID from the URL.
      if (!personId || isNaN(personId)) {
         setError('Invalid Person ID.'); // Set error if ID is invalid.
         setLoading(false); // Stop loading indicator.
         return; // Exit effect early.
       }

    /** Asynchronous function defining the data fetching sequence. */
    const fetchPerson = async () => {
       // Reset states before starting: main loading ON, error OFF, related works cleared.
       setLoading(true);
       setError(null);
       setAuthoredWorks({ works: [], loading: false, error: null }); // Clear previous works state
      try {
        // Fetch the primary person data.
        const data = await getPerson(personId);
        setPerson(data); // Update state with person data.
        // Trigger the fetch for authored works *after* successfully getting the person.
        fetchAuthoredWorks(personId);
      } catch (err: any) {
        // Handle errors during the primary person fetch.
        setError(err.message || 'Failed to fetch person details.');
        // Ensure loading is stopped if the primary fetch fails.
        setLoading(false);
      }
      // Note: setLoading(false) is primarily handled within fetchAuthoredWorks' finally block
      // to signify completion after *both* attempts (person and works) have resolved/failed.
    };

    // Execute the fetch sequence.
    fetchPerson();
  }, [personId, fetchAuthoredWorks]); // Dependencies: re-run if ID or the fetch callback changes.

  // --- Render Helper Functions ---

  /**
   * Generic function to render a section displaying a list of linked items.
   * Handles loading, error, and empty states based on the provided arguments.
   * Creates links to the detail pages of the items.
   * The generic type `T` ensures items have an `id`, and allows optional common fields like `title`, `doi`, `publication_year`.
   * @template T - The type of items in the list, constrained to have at least an `id`.
   * @param title - The title for the section.
   * @param items - The array of items to display. (Directly passed, unlike previous version)
   * @param loading - Boolean indicating if the items are currently loading. (Directly passed)
   * @param error - String containing an error message, or null. (Directly passed)
   * @param linkPrefix - The base path for the links (e.g., "/works").
   * @param emptyMessage - Message to display if `items` is empty after loading and without error.
   * @returns JSX element representing the linked items section.
   */
  // FIX: Modify renderLinkedItems signature and usage (Comment refers to previous code state)
  const renderLinkedItems = <T extends { id: number; title?: string | null; doi?: string | null; publication_year?: number | null; }> (
      title: string,
      items: T[], // Pass items array directly
      loading: boolean, // Pass loading flag
      error: string | null, // Pass error message
      linkPrefix: string,
      emptyMessage: string
    ) => {
      return (
        <div className="detail-section"> {/* Container for the section */}
          <h4>{title}</h4> {/* Section title */}
           {/* Show loading spinner if loading flag is true */}
           {/* FIX: Remove size prop (Comment refers to previous code state) */}
          {loading && <LoadingSpinner message="" />}
          {/* Show error message if error exists */}
          {error && <ErrorMessage message={error} />}
          {/* Show list if not loading, no error, and items exist */}
          {!loading && !error && items.length > 0 && (
            <ul>
              {/* Map over items to create list entries */}
              {items.map(item => (
                <li key={item.id}>
                  {/* Link to the item's detail page */}
                  <Link to={`${linkPrefix}/${item.id}`}>
                    {/* Display item title or fallback to ID */}
                    {item.title || `ID ${item.id}`}
                  </Link>
                  {/* Conditionally display DOI if present */}
                  {'doi' in item && item.doi && ` (DOI: ${item.doi})`}
                  {/* Conditionally display publication year if present */}
                  {'publication_year' in item && item.publication_year && ` [${item.publication_year}]`}
                </li>
              ))}
            </ul>
          )}
          {/* Show empty message if not loading, no error, and no items */}
          {!loading && !error && items.length === 0 && <p>{emptyMessage}</p>}
        </div>
      );
  };


  // --- Main Component Render Logic ---

  // Display a loading spinner covering the page if the main person data is still loading initially.
  if (loading && !person) return <LoadingSpinner message={`Loading person ${id}...`} />;
  // Display an error message covering the page if the main person fetch failed.
  if (error && !person) return <ErrorMessage message={error} />;
  // Display a 'not found' message if loading finished without error but no person data was retrieved.
  if (!person) return <p>Person not found.</p>;

  // --- Render the main detail page content if person data is available ---
  return (
    <div className="detail-page person-detail"> {/* Main container with specific class */}
      {/* Page Title: Person Name */}
      <h2>Person: {person.display_name}</h2>
       {/* Section displaying core person details */}
       <p><strong>ID:</strong> {person.id}</p>
       {/* Link to external OpenAlex page */}
       <p><strong>OpenAlex ID:</strong> <a href={`https://openalex.org/${person.openalex_id}`} target="_blank" rel="noopener noreferrer">{person.openalex_id}</a></p>
       {/* Link to external ORCID page if ORCID exists */}
       <p><strong>ORCID:</strong> {person.orcid ? <a href={`https://orcid.org/${person.orcid}`} target="_blank" rel="noopener noreferrer">{person.orcid}</a> : 'N/A'}</p>
       {/* Internal timestamps */}
       <p><small>Created in MOSS: {new Date(person.created_at).toLocaleString()}</small></p>
       <p><small>Updated in MOSS: {new Date(person.updated_at).toLocaleString()}</small></p>

      {/* Separator line */}
      <hr />

       {/* Render the authored works section using the helper function */}
       {/* FIX: Pass items, loading, error directly (Comment refers to previous code state) */}
       {renderLinkedItems(
           "Authored Works",         // Section title
           authoredWorks.works,      // Pass the works array
           authoredWorks.loading,    // Pass the loading flag for works
           authoredWorks.error,      // Pass the error status for works
           "/works",                 // Base path for work links
           "No works found authored by this person." // Empty state message
       )}

       {/* Placeholder section for future affiliated institutions display */}
       <div className="detail-section">
            <h4>Affiliated Institutions (Placeholder)</h4>
            <p>Functionality to display affiliated institutions will be added later.</p>
       </div>
    </div> // End detail-page container
  );
};

export default PersonDetailPage;