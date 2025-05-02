// frontend/src/pages/SearchPage.tsx ---

import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';

// Import API functions and types for searching different entity types
import {
    searchRepositories, searchWorks, searchPeople, searchInstitutions,
    RepositorySummary, WorkSummary, PersonSummary, InstitutionSummary // Summary types returned by search APIs
} from '../services/apiClient';

// Import shared components for UI feedback
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

// Import page-specific styles
import './SearchPage.css';

/**
 * Interface defining the structure for storing search results across different entity types.
 * Each property holds an array of summary objects for that entity type.
 */
interface SearchResults {
    /** Array of repository summaries matching the search query. */
    repositories: RepositorySummary[];
    /** Array of work summaries matching the search query. */
    works: WorkSummary[];
    /** Array of person summaries matching the search query. */
    people: PersonSummary[];
    /** Array of institution summaries matching the search query. */
    institutions: InstitutionSummary[];
}

/**
 * `SearchPage` Component
 *
 * Provides a user interface for searching across multiple MOSS entity types
 * (Repositories, Works, People, Institutions) using a single query string.
 * It concurrently calls the respective search API endpoints and displays the
 * results grouped by category. Handles loading states and potential errors
 * during the search process.
 */
function SearchPage() {
    // --- State Management ---

    /** Stores the current search query entered by the user in the input field. */
    const [query, setQuery] = useState<string>('');
    /** Stores the aggregated search results from all categories. Initialized with empty arrays. */
    const [results, setResults] = useState<SearchResults>({
        repositories: [],
        works: [],
        people: [],
        institutions: []
    });
    /** Loading state flag. True while the search API calls are in progress. */
    const [isLoading, setIsLoading] = useState<boolean>(false);
    /** Stores any error message encountered during the search process. Null if no error. */
    const [error, setError] = useState<string | null>(null);
    /** Flag indicating whether a search has been attempted at least once. Used to control initial display messages. */
    const [searched, setSearched] = useState<boolean>(false);

    // --- Event Handlers ---

    /**
     * Handles the submission of the search form.
     * Prevents default form submission, validates the query, initiates concurrent API calls
     * for each entity type using `Promise.allSettled`, processes the results (handling
     * potential failures for individual categories), and updates the component's state
     * (loading, error, results).
     * @param event The form submission event object.
     */
    const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault(); // Prevent full page reload on form submission

        // Basic validation: Ensure the query is not empty or just whitespace.
        if (!query.trim()) {
            setError("Please enter a search query."); // Display validation error
            setSearched(false); // Reset searched flag as no valid search was performed
            setResults({ repositories: [], works: [], people: [], institutions: [] }); // Clear previous results
            return; // Stop execution
        }

        // Set initial state for a new search
        setIsLoading(true); // Show loading indicator
        setError(null); // Clear previous errors
        setResults({ repositories: [], works: [], people: [], institutions: [] }); // Clear previous results
        setSearched(true); // Mark that a search has been initiated

        try {
            // Prepare an array of promises for all search API calls
            const searchPromises = [
                searchRepositories(query),
                searchWorks(query),
                searchPeople(query),
                searchInstitutions(query)
            ];

            // Execute all search promises concurrently and wait for all to settle (either fulfill or reject).
            // This allows partial results even if some searches fail.
            const settledResults = await Promise.allSettled(searchPromises);

            // Initialize an object to hold the successfully fetched results.
            const newResults: SearchResults = {
                repositories: [],
                works: [],
                people: [],
                institutions: []
            };

            // Process the settled results, extracting data from fulfilled promises.
            // --- Add Type Assertions ---
            // (These comments refer to the type assertions added in a previous step)
            if (settledResults[0].status === 'fulfilled') {
                // Assert that the fulfilled value is of type RepositorySummary[] before assignment.
                newResults.repositories = settledResults[0].value as RepositorySummary[];
            }
            if (settledResults[1].status === 'fulfilled') {
                 // Assert that the fulfilled value is of type WorkSummary[] before assignment.
                newResults.works = settledResults[1].value as WorkSummary[];
            }
            if (settledResults[2].status === 'fulfilled') {
                 // Assert that the fulfilled value is of type PersonSummary[] before assignment.
                newResults.people = settledResults[2].value as PersonSummary[];
            }
            if (settledResults[3].status === 'fulfilled') {
                 // Assert that the fulfilled value is of type InstitutionSummary[] before assignment.
                newResults.institutions = settledResults[3].value as InstitutionSummary[];
            }
            // --- End Type Assertions ---

            // Update the component state with the collected results.
            setResults(newResults);

            // Check if any search category failed and set a warning error if needed.
            const failedSearches = settledResults.filter(r => r.status === 'rejected');
            if (failedSearches.length > 0) {
                console.warn("Some search categories failed:", failedSearches); // Log detailed errors for debugging
                setError("Some search categories failed. Results might be incomplete."); // Inform user
            }

        } catch (err) {
             // Catch unexpected errors during the Promise.allSettled setup or initial processing.
             // Individual promise rejections are handled above.
             const message = err instanceof Error ? err.message : "An unexpected error occurred during search setup.";
            setError(message);
            console.error("Error during search setup:", err);
        } finally {
            // Ensure loading indicator is hidden once the search process completes (success or error).
            setIsLoading(false);
        }
    };

    // --- Computed Values ---

    /** A boolean flag indicating if any results were found across all categories. */
    const hasResults = results && (
        results.repositories.length > 0 ||
        results.works.length > 0 ||
        results.people.length > 0 ||
        results.institutions.length > 0
    );

    // --- Component Render ---
    return (
        <div className="search-page">
            <h2>Search MOSS Entities</h2>
            {/* Search form */}
            <form onSubmit={handleSearch} className="search-form">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)} // Update query state on input change
                    placeholder="Search repositories, works, people, institutions..."
                    required // HTML5 validation for empty input
                    className="search-input"
                />
                <button type="submit" disabled={isLoading} className="search-button">
                    {/* Show different text while loading */}
                    {isLoading ? 'Searching...' : 'Search'}
                </button>
            </form>

            {/* Display loading spinner while search is in progress */}
            {isLoading && <LoadingSpinner />}
            {/* Display error message if any error occurred */}
            {error && <ErrorMessage message={error} />}

            {/* Conditionally render the results area only after a search has been attempted and is not loading */}
            {searched && !isLoading && (
                <div className="search-results">
                     {/* Display 'no results' message only if no error occurred and no results were found */}
                     {!error && !hasResults && <p>No results found for "{query}" across all categories.</p>}

                     {/* --- Results for Repositories --- */}
                     {/* Render this section only if repository results exist */}
                     {results.repositories.length > 0 && (
                        <div className="results-category">
                            <h4>Repositories ({results.repositories.length})</h4> {/* Title with result count */}
                            <ul>
                                {/* Map over repository results to create list items */}
                                {results.repositories.map(repo => (
                                    <li key={`repo-${repo.id}`}> {/* Unique key for React */}
                                        {/* Link to the repository detail page */}
                                        <Link to={`/repositories/${repo.id}`}>{repo.full_name}</Link>
                                        {/* Optionally display language */}
                                        {repo.language && ` (${repo.language})`}
                                    </li>
                                ))}
                            </ul>
                        </div>
                     )}

                    {/* --- Results for Works --- */}
                    {/* Render this section only if work results exist */}
                    {results.works.length > 0 && (
                        <div className="results-category">
                            <h4>Works ({results.works.length})</h4>
                             <ul>
                                {/* Map over work results */}
                                {results.works.map(work => (
                                    <li key={`work-${work.id}`}>
                                        {/* Link to the work detail page */}
                                        <Link to={`/works/${work.id}`}>{work.title || work.doi || `Work ID ${work.id}`}</Link> {/* Use title, DOI, or ID as link text */}
                                        {/* Optionally display publication year */}
                                        {work.publication_year && ` (${work.publication_year})`}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* --- Results for People --- */}
                    {/* Render this section only if people results exist */}
                    {results.people.length > 0 && (
                         <div className="results-category">
                            <h4>People ({results.people.length})</h4>
                            <ul>
                                {/* Map over people results */}
                                {results.people.map(person => (
                                    <li key={`person-${person.id}`}>
                                        {/* Link to the person detail page */}
                                        <Link to={`/persons/${person.id}`}>{person.display_name}</Link>
                                        {/* Optionally display ORCID */}
                                        {person.orcid && ` (ORCID: ${person.orcid})`}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* --- Results for Institutions --- */}
                    {/* Render this section only if institution results exist */}
                    {results.institutions.length > 0 && (
                         <div className="results-category">
                            <h4>Institutions ({results.institutions.length})</h4>
                            <ul>
                                {/* Map over institution results */}
                                {results.institutions.map(inst => (
                                    <li key={`inst-${inst.id}`}>
                                        {/* Link to the institution detail page */}
                                        <Link to={`/institutions/${inst.id}`}>{inst.display_name}</Link>
                                         {/* Optionally display ROR ID */}
                                        {inst.ror && ` (ROR: ${inst.ror})`}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div> // End search-results
            )}
        </div> // End search-page
    );
}

export default SearchPage;