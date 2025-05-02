// frontend/src/pages/RepositoryDetailPage.tsx ---
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Node, Edge } from 'reactflow'; // Types for the graph display component
import GraphDisplay from '../components/GraphDisplay'; // Component for visualizing relationships
import {
    getRepository, // Fetches main repository details
    getRepositoryWorks, // Fetches scholarly works linked to the repository
    getRepositoryCitationCount, // Fetches citation counts for the repository
    getRepositoriesSharingContributors, // Fetches repositories sharing contributors with this one
    getRepositoriesSharingWorks, // Fetches repositories linked to the same works as this one
    getRepositoryAffiliationsFiltered, // Fetches calculated institutional affiliations for the repository
    getSharedContributorsDetails, // Fetches details of contributors shared between two repositories
    getRepositoryDependencies, // <<< Added: Fetches software dependencies declared in the repository
} from '../services/apiClient'; // API client functions
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import SimpleTable from '../components/SimpleTable'; // <<< Added: Component for displaying tabular data (like dependencies)
import type {
    RepositoryResponse, // Type for the main repository data
    RepositorySummary, // Type for summary info of related repositories
    WorkSummary, // Type for summary info of linked works
    RepositoryCitationCountResponse, // Type for citation count data
    AffiliationResultResponse, // Type for calculated affiliation data
    ContributorResponse, // Type for contributor details
    SoftwareDependencyResponse, // <<< Added: Type for software dependency data
} from '../services/apiClient'; // API response types

// --- State Type Definitions ---

/** Defines the structure for storing citation count state, including data, loading, and error status. */
interface CitationCountState {
    data: RepositoryCitationCountResponse | null;
    loading: boolean;
    error: string | null;
}

/** Generic state structure for lists of related repositories (e.g., sharing contributors or works). */
interface RelatedReposState {
    repos: RepositorySummary[];
    loading: boolean;
    error: string | null;
}

/** State structure for the list of linked scholarly works. */
interface LinkedWorksState {
    works: WorkSummary[];
    loading: boolean;
    error: string | null;
}

/** State structure for the list of calculated institutional affiliations. */
interface AffiliationsState {
    affiliations: AffiliationResultResponse[];
    loading: boolean;
    error: string | null;
}

/** State structure for the list of discovered software dependencies. */
// --- Added State Interface ---
interface DependenciesState {
    dependencies: SoftwareDependencyResponse[];
    loading: boolean;
    error: string | null;
}
// --- End Added State Interface ---

/**
 * State structure for storing the details of shared contributors between the main repository
 * and other specific repositories. The key is the ID of the *other* repository.
 * Stores contributor details, loading status, and errors per related repository ID.
 */
interface SharedContributorsDetailsState {
    [repoId: number]: { // Keyed by the ID of the *other* repository
        contributors: ContributorResponse[];
        loading: boolean;
        error: string | null;
    } | undefined; // Undefined if details haven't been requested or are hidden
}

/**
 * `RepositoryDetailPage` Component
 *
 * Displays comprehensive details about a specific software repository identified by its ID
 * from the URL. It fetches the main repository data and subsequently fetches various
 * related data points like linked works, citation counts, related repositories (based on
 * shared contributors or works), calculated affiliations, and software dependencies.
 * It also provides functionality to visualize relationships in a graph and view details
 * of shared contributors.
 */
const RepositoryDetailPage: React.FC = () => {
    // --- Hooks and State Initialization ---

    /** Extracts the 'id' parameter from the current URL. */
    const { id } = useParams<{ id: string }>();
    /** Parses the extracted ID string into an integer. Defaults to 0 if ID is missing or invalid. */
    const repoId = parseInt(id || '0', 10);

    // State for the primary repository data
    /** Stores the main repository data fetched from the API. */
    const [repository, setRepository] = useState<RepositoryResponse | null>(null);
    /** Loading state specifically for the initial fetch of the main repository data. */
    const [isLoadingRepo, setIsLoadingRepo] = useState(true);
    /** Error state specifically for the initial fetch of the main repository data. */
    const [repoError, setRepoError] = useState<string | null>(null);

    // State for related data sections
    /** State for linked scholarly works (data, loading, error). */
    const [linkedWorks, setLinkedWorks] = useState<LinkedWorksState>({ works: [], loading: false, error: null });
    /** State for citation counts (data, loading, error). */
    const [citationCount, setCitationCount] = useState<CitationCountState>({ data: null, loading: false, error: null });
    /** State for repositories sharing contributors (data, loading, error). */
    const [sharedContribRepos, setSharedContribRepos] = useState<RelatedReposState>({ repos: [], loading: false, error: null });
    /** State for repositories sharing linked works (data, loading, error). */
    const [sharedWorksRepos, setSharedWorksRepos] = useState<RelatedReposState>({ repos: [], loading: false, error: null });
    /** State for calculated institutional affiliations (data, loading, error). */
    const [affiliations, setAffiliations] = useState<AffiliationsState>({ affiliations: [], loading: false, error: null });
    // --- Added State ---
    /** State for software dependencies (data, loading, error). */
    const [dependencies, setDependencies] = useState<DependenciesState>({ dependencies: [], loading: false, error: null });
    // --- End Added State ---
    /** State storing details of shared contributors, keyed by the other repository's ID. */
    const [sharedContributorsDetails, setSharedContributorsDetails] = useState<SharedContributorsDetailsState>({});

    // State for the relationship graph
    /** State storing the nodes for the react-flow graph display. */
    const [graphNodes, setGraphNodes] = useState<Node[]>([]);
    /** State storing the edges for the react-flow graph display. */
    const [graphEdges, setGraphEdges] = useState<Edge[]>([]);

    // --- Data Fetching Callbacks ---

    /**
     * Fetches all related data for a given repository ID *after* the main repository data is loaded.
     * This includes linked works, citation counts, related repositories, affiliations, and dependencies.
     * Uses useCallback for memoization. It initiates all fetches concurrently.
     * Each fetch updates its corresponding state slice (loading, data/error).
     * @param currentRepoId The ID of the repository for which to fetch related data.
     */
    const fetchAllRelatedData = useCallback((currentRepoId: number) => {
         console.log(`Fetching related data for repository ID: ${currentRepoId}`);
         // --- Fetch Linked Works ---
         setLinkedWorks(prev => ({ ...prev, loading: true, error: null }));
         getRepositoryWorks(currentRepoId)
            .then(data => setLinkedWorks({ works: data, loading: false, error: null }))
            .catch(error => setLinkedWorks({ works: [], loading: false, error: (error as Error).message }));

         // --- Fetch Citation Count ---
         setCitationCount(prev => ({ ...prev, loading: true, error: null }));
         getRepositoryCitationCount(currentRepoId)
             .then(data => { setCitationCount({ data: data, loading: false, error: null }); })
             .catch (error => { setCitationCount({ data: null, loading: false, error: (error as Error).message }); });

         // --- Fetch Repos Sharing Contributors ---
         setSharedContribRepos(prev => ({ ...prev, loading: true, error: null }));
         getRepositoriesSharingContributors(currentRepoId)
            .then(data => setSharedContribRepos({ repos: data, loading: false, error: null }))
            .catch(error => setSharedContribRepos({ repos: [], loading: false, error: (error as Error).message }));

         // --- Fetch Repos Sharing Works ---
         setSharedWorksRepos(prev => ({ ...prev, loading: true, error: null }));
         getRepositoriesSharingWorks(currentRepoId)
            .then(data => setSharedWorksRepos({ repos: data, loading: false, error: null }))
            .catch(error => setSharedWorksRepos({ repos: [], loading: false, error: (error as Error).message }));

         // --- Fetch Affiliations ---
         setAffiliations(prev => ({ ...prev, loading: true, error: null }));
         getRepositoryAffiliationsFiltered(currentRepoId)
             .then(data => setAffiliations({ affiliations: data, loading: false, error: null }))
             .catch(error => setAffiliations({ affiliations: [], loading: false, error: (error as Error).message }));

        // --- Added Fetch for Dependencies ---
        setDependencies(prev => ({ ...prev, loading: true, error: null }));
        getRepositoryDependencies(currentRepoId)
            .then(data => setDependencies({ dependencies: data, loading: false, error: null }))
            .catch(error => setDependencies({ dependencies: [], loading: false, error: (error as Error).message }));
        // --- End Added Fetch ---

        // Reset details state when fetching related data for a new main repo
        setSharedContributorsDetails({});

    }, []); // Empty dependency array: function doesn't depend on component state/props.

    // --- Effects ---

    /**
     * Effect Hook for fetching the primary repository data.
     * Runs when the component mounts or when `repoId` (from URL) changes.
     * Validates the ID, resets all states, fetches the main repository details,
     * and upon success, calls `fetchAllRelatedData` to fetch associated information.
     * Manages the primary loading (`isLoadingRepo`) and error (`repoError`) states.
     */
    useEffect(() => {
         // Validate the repository ID from the URL.
         if (!repoId || isNaN(repoId)) {
            setRepoError('Invalid Repository ID.');
            setIsLoadingRepo(false);
            return; // Exit early if ID is invalid.
         }

        /** Asynchronous function defining the primary data fetching sequence. */
        const fetchRepoData = async () => {
            // Reset all states before starting the fetch for the new ID.
            setIsLoadingRepo(true);
            setRepoError(null);
            setRepository(null); // Clear previous repo data
            // Reset related data states
            setGraphNodes([]); setGraphEdges([]);
            setLinkedWorks({ works: [], loading: false, error: null });
            setCitationCount({ data: null, loading: false, error: null });
            setSharedContribRepos({ repos: [], loading: false, error: null });
            setSharedWorksRepos({ repos: [], loading: false, error: null });
            setAffiliations({ affiliations: [], loading: false, error: null });
            setDependencies({ dependencies: [], loading: false, error: null }); // Reset deps state
            setSharedContributorsDetails({}); // Clear contributor details

            try {
                // Fetch the primary repository data.
                const repoData = await getRepository(repoId);
                setRepository(repoData); // Update state with the fetched data.
                // If successful, trigger the fetching of all related data.
                fetchAllRelatedData(repoId);
            } catch (error) {
                // Handle errors during the primary repository fetch.
                setRepoError((error as Error).message);
            } finally {
                // Ensure the main loading indicator is turned off after the primary fetch attempt.
                // Loading indicators for related data are managed separately.
                setIsLoadingRepo(false);
            }
        };
        // Execute the fetch sequence.
        fetchRepoData();
    }, [repoId, fetchAllRelatedData]); // Dependencies: re-run if ID or the fetch callback changes.

    /**
     * Effect Hook for generating graph nodes and edges.
     * Runs whenever the main repository data, linked works, or affiliations data changes.
     * Creates nodes for the main repository, linked works, and affiliated institutions,
     * and edges connecting them, then updates the graph state (`graphNodes`, `graphEdges`).
     */
    // --- Graph useEffect remains the same ---
    useEffect(() => {
        // Don't generate graph if the main repository data isn't loaded yet.
        if (!repository) return;

        const nodes: Node[] = []; // Initialize nodes array
        const edges: Edge[] = []; // Initialize edges array
        const mainNodeId = `repo-${repository.id}`; // Unique ID for the central repository node
        const nodeXOffsetLeft = 50; // X-coordinate for nodes positioned to the left

        // Create the central node for the current repository.
        nodes.push({
            id: mainNodeId,
            data: { label: repository.full_name }, // Node label is the repo name
            position: { x: 250, y: 250 }, // Center position
            // Styling for the main node
            style: { background: '#aaaaff', fontWeight: 'bold', width: 150, textAlign: 'center', border: '1px solid #66f' },
        });

        let currentLeftY = 50; // Starting Y-coordinate for left-side nodes

        // Create nodes and edges for linked works.
        linkedWorks.works.forEach((work, index) => {
            const workNodeId = `work-${work.id}`; // Unique ID for the work node
            // Add node for the work.
            nodes.push({
                id: workNodeId,
                data: { label: work.title || `Work ${work.id}` }, // Label is work title or ID
                position: { x: nodeXOffsetLeft, y: currentLeftY + index * 100 }, // Position vertically stacked
                // Styling for work nodes
                style: { background: '#aaffaa', width: 150, textAlign: 'center', border: '1px solid #6f6' }
            });
            // Add edge connecting the main repo node to the work node.
            edges.push({ id: `e-${mainNodeId}-links-${workNodeId}`, source: mainNodeId, target: workNodeId, label: 'links work' });
        });
        // Adjust Y-coordinate for the next section based on the number of work nodes added.
        currentLeftY += Math.max(0, linkedWorks.works.length) * 100 + 50; // Add spacing

        // Create nodes and edges for affiliated institutions.
        affiliations.affiliations.forEach((affil, index) => {
             const instNodeId = `inst-${affil.institution_id}`; // Unique ID for the institution node
             // Add institution node only if it doesn't already exist (to avoid duplicates if multiple affiliations exist).
             if (!nodes.some(n => n.id === instNodeId)) {
                 nodes.push({
                     id: instNodeId,
                     data: { label: affil.institution_name || `Inst ${affil.institution_id}` }, // Label is institution name or ID
                     position: { x: nodeXOffsetLeft, y: currentLeftY + index * 100 }, // Position vertically stacked below works
                     // Styling for institution nodes
                     style: { background: '#ffccaa', width: 150, textAlign: 'center', border: '1px solid #f96' }
                 });
             }
             // Add edge connecting the main repo node to the institution node.
             edges.push({ id: `e-affil-${mainNodeId}-${instNodeId}`, source: mainNodeId, target: instNodeId, label: `affiliated (${affil.confidence_score.toFixed(2)})`, type: 'smoothstep', style: { stroke: '#f96' } });
        });

        // Update the component's state with the generated nodes and edges.
        setGraphNodes(nodes);
        setGraphEdges(edges);

    }, [repository, linkedWorks.works, affiliations.affiliations]); // Dependencies: re-run if these data points change.

    // --- Event Handlers ---

    /**
     * Handles the click event for the "Show/Hide Shared" button next to a repository
     * in the "Repositories Sharing Contributors" list.
     * Fetches and displays (or hides) the specific contributors shared between the current
     * repository and the target repository ID. Manages loading and error states specifically
     * for the details of the clicked repository ID within `sharedContributorsDetails`.
     * @param otherRepoId The ID of the repository for which to show/hide shared contributor details.
     */
    // --- handleShowSharedContributors remains the same ---
    const handleShowSharedContributors = async (otherRepoId: number) => {
        // Ensure the main repository ID is valid.
        if (!repoId) return;

         // If details for this repo ID already exist in state, toggle to hide them (set to undefined).
         if (sharedContributorsDetails[otherRepoId]) {
             setSharedContributorsDetails(prev => ({
                 ...prev,
                 [otherRepoId]: undefined // Remove the entry to hide details
             }));
             return; // Exit after hiding
         }

        // Set loading state specifically for this otherRepoId before fetching.
        setSharedContributorsDetails(prev => ({
            ...prev,
            [otherRepoId]: { contributors: [], loading: true, error: null }
        }));

        try {
            // Fetch the shared contributor details from the API.
            const contributors = await getSharedContributorsDetails(repoId, otherRepoId);
            // Update the state with the fetched contributors on success.
            setSharedContributorsDetails(prev => ({
                ...prev,
                [otherRepoId]: { contributors: contributors, loading: false, error: null }
            }));
        } catch (error) {
             // Update the state with the error message on failure.
             setSharedContributorsDetails(prev => ({
                ...prev,
                [otherRepoId]: { contributors: [], loading: false, error: (error as Error).message }
            }));
        }
    };


    // --- Render Helper Functions ---

    /**
     * Generic function to render a section displaying a list of linked items (Repositories or Works).
     * Handles loading, error, and empty states. Creates links to detail pages.
     * Includes special handling for the "Repositories Sharing Contributors" list to show
     * a button for fetching and displaying the specific shared contributors.
     * @template T - The type of items, constrained to have common fields like id, name/title etc.
     * @param title - The title for the section.
     * @param items - Array of items to display.
     * @param loading - Boolean indicating if the list is loading.
     * @param error - String error message or null.
     * @param linkPrefix - Base path for item detail links (e.g., "/repositories", "/works").
     * @param emptyMessage - Message shown if the list is empty.
     * @param isSharedContributorsList - Flag to enable the "Show/Hide Shared" button functionality.
     * @returns JSX element for the linked items section.
     */
    // --- renderLinkedItems remains the same ---
    const renderLinkedItems = <T extends { id: number; full_name?: string | null; title?: string | null; language?: string | null; doi?: string | null; publication_year?: number | null; }> (
        title: string,
        items: T[],
        loading: boolean,
        error: string | null,
        linkPrefix: string,
        emptyMessage: string,
        isSharedContributorsList?: boolean // Optional flag for special handling
    ) => {
        return (
            <div className="detail-section"> {/* Section container */}
                <h4>{title}</h4> {/* Section title */}
                {/* Display loading spinner */}
                {loading && <LoadingSpinner message="" />}
                {/* Display error message */}
                {error && <ErrorMessage message={error} />}
                {/* Display list if not loading, no error, and items exist */}
                {!loading && !error && items.length > 0 && (
                    <ul>
                        {/* Map over items to create list entries */}
                        {items.map(item => {
                            // --- Correction Start (Comment refers to previous code state) ---
                            // Get the details object for the current item *outside* the inner JSX
                            // This retrieves the specific loading/error/data state for shared contributors of *this* item.id
                            const details = sharedContributorsDetails[item.id];
                            // --- Correction End (Comment refers to previous code state) ---

                            return (
                                <li key={item.id}>
                                    {/* Link to the item's detail page */}
                                    <Link to={`${linkPrefix}/${item.id}`}>
                                        {item.full_name || item.title || `ID ${item.id}`} {/* Display name/title */}
                                    </Link>
                                    {/* Conditionally display language */}
                                    {'language' in item && item.language && ` (${item.language})`}
                                    {/* Conditionally display DOI */}
                                    {'doi' in item && item.doi && ` (DOI: ${item.doi})`}
                                    {/* Conditionally display publication year */}
                                    {'publication_year' in item && item.publication_year && ` [${item.publication_year}]`}

                                    {/* Special section for the 'Shared Contributors' list */}
                                    {isSharedContributorsList && (
                                        <>
                                            {/* Button to toggle shared contributor details */}
                                            <button
                                                onClick={() => handleShowSharedContributors(item.id)}
                                                style={{ marginLeft: '10px', fontSize: '0.8em', padding: '2px 5px' }}
                                                disabled={details?.loading} // Disable button while details are loading
                                            >
                                                {/* Dynamic button text based on state */}
                                                {details?.loading ? 'Loading...' : (details ? 'Hide' : 'Show')} Shared
                                            </button>
                                            {/* --- Correction Start (Comment refers to previous code state) --- */}
                                            {/* Conditionally render the details section if details exist and are not loading */}
                                            {details && !details.loading && (
                                                <div style={{ marginLeft: '20px', marginTop: '5px', fontSize: '0.9em', borderLeft: '2px solid #eee', paddingLeft: '10px' }}>
                                                    {/* Display error if fetching details failed */}
                                                    {details.error && <ErrorMessage message={details.error || 'Error fetching details'} />}
                                                    {/* Display message if no shared contributors were found */}
                                                    {!details.error && details.contributors.length === 0 && <span>(No specific shared contributors found - data mismatch?)</span>}
                                                    {/* Display list of shared contributors if found */}
                                                    {!details.error && details.contributors.length > 0 && (
                                                        <>
                                                            Shared ({details.contributors.length}):{' '}
                                                            {/* Map over contributors to display links */}
                                                            {details.contributors.map((c, index) => (
                                                                <React.Fragment key={c.id}>
                                                                     {/* Link to contributor's GitHub profile */}
                                                                     <a href={c.html_url ?? '#'} target="_blank" rel="noopener noreferrer">{c.login}</a>
                                                                    {/* Add comma separator */}
                                                                    {index < details.contributors.length - 1 ? ', ' : ''}
                                                                </React.Fragment>
                                                            ))}
                                                        </>
                                                    )}
                                                </div>
                                            )}
                                            {/* --- Correction End (Comment refers to previous code state) --- */}
                                        </>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                )}
                {/* Display empty message if applicable */}
                {!loading && !error && items.length === 0 && <p>{emptyMessage}</p>}
            </div>
        );
    };

    /**
     * Renders the section displaying citation counts (OpenAlex aggregated and MOSS discovered).
     * Handles loading, error, and data availability states for citation data.
     * @returns JSX element for the citation counts section.
     */
    // --- renderCitationCounts remains the same ---
    const renderCitationCounts = () => (
         <div className="detail-section">
            <h4>Citation Counts</h4>
            {/* Display loading spinner */}
            {citationCount.loading && <LoadingSpinner message="" />}
            {/* Display error message */}
            {citationCount.error && <ErrorMessage message={citationCount.error} />}
            {/* Display citation data if available and not loading */}
            {citationCount.data !== null && !citationCount.loading && (
                <>
                    <p>
                        OpenAlex Aggregated Citations:
                        {/* Display count or 'N/A' */}
                        <strong>{citationCount.data.openalex_aggregated_citations ?? 'N/A'}</strong>
                        <br/>
                        <small>(Sum of cited_by_count from linked works as reported by OpenAlex)</small>
                    </p>
                    <p>
                        MOSS Discovered Citations:
                        {/* Display count or 'N/A' */}
                        <strong>{citationCount.data.moss_discovered_citations ?? 'N/A'}</strong>
                        <br/>
                        <small>(Count of unique citing works discovered and linked within MOSS)</small>
                    </p>
                </>
            )}
            {/* Display message if data is null after loading and without error */}
            {citationCount.data === null && !citationCount.loading && !citationCount.error && (
                <p>Citation count data not available.</p>
            )}
        </div>
    );

    /**
     * Renders the section displaying calculated institutional affiliations.
     * Handles loading, error, and empty states for the affiliation data.
     * Creates links to the affiliated institution detail pages.
     * @param state The `AffiliationsState` object containing affiliation data.
     * @returns JSX element for the affiliations list section.
     */
    // --- renderAffiliationsList remains the same ---
    const renderAffiliationsList = (
        state: AffiliationsState
    ) => (
         <div className="detail-section">
            <h4>Affiliated Institutions (Calculated)</h4>
            {/* Display loading spinner */}
            {state.loading && <LoadingSpinner message="" />}
            {/* Display error message */}
            {state.error && <ErrorMessage message={state.error} />}
            {/* Display list if not loading, no error, and affiliations exist */}
            {!state.loading && !state.error && state.affiliations.length > 0 && (
                <ul>
                    {/* Map over affiliations to create list items */}
                    {state.affiliations.map((affil) => (
                        // Key includes multiple fields for potential duplicates across algorithms/dates
                        <li key={`${affil.institution_id}-${affil.algorithm_name}-${affil.algorithm_version}`}>
                            {/* Link to the institution's detail page */}
                            <Link to={`/institutions/${affil.institution_id}`}>{affil.institution_name}</Link>
                            {/* Display additional details (score, algorithm, date) */}
                            <span style={{ marginLeft: '10px', color: '#666', fontSize: '0.9em' }}>
                                (Score: {affil.confidence_score.toFixed(2)}, Algo: {affil.algorithm_name} v{affil.algorithm_version}, Date: {new Date(affil.calculated_at).toLocaleDateString()})
                            </span>
                        </li>
                    ))}
                </ul>
            )}
            {/* Display empty message if applicable */}
            {!state.loading && !state.error && state.affiliations.length === 0 && (
                <p>No calculated affiliations found.</p>
            )}
        </div>
    );

    /**
     * Renders the section displaying software dependencies found in the repository.
     * Uses the `SimpleTable` component for display. Handles loading, error, and empty states.
     * @param state The `DependenciesState` object containing dependency data.
     * @returns JSX element for the dependencies table section.
     */
    // --- Added Render Function for Dependencies ---
    const renderDependencies = (state: DependenciesState) => {
        // Prepare data for SimpleTable: Convert boolean 'is_dev_dependency' to string for display.
        const tableData = state.dependencies.map(dep => ({
            ...dep,
            // Handle null case and convert boolean to string ('true'/'false')
            is_dev_dependency: dep.is_dev_dependency === null ? '' : String(dep.is_dev_dependency),
        }));

        return (
            <div className="detail-section">
                <h4>Software Dependencies</h4>
                {/* Display loading spinner */}
                {state.loading && <LoadingSpinner message="" />}
                {/* Display error message */}
                {state.error && <ErrorMessage message={state.error} />}
                {/* Display table if not loading, no error, and dependencies exist */}
                {!state.loading && !state.error && tableData.length > 0 && (
                     <SimpleTable data={tableData} columns={[ // Define columns for the table
                         { key: 'dependency_name', header: 'Name' },
                         { key: 'version_constraint', header: 'Version' },
                         { key: 'dependency_type', header: 'Type' },
                         { key: 'source_file', header: 'Source' },
                         { key: 'is_dev_dependency', header: 'Dev?' }, // Header for the converted boolean field
                     ]} />
                )}
                {/* Display empty message if applicable */}
                {!state.loading && !state.error && tableData.length === 0 && (
                    <p>No software dependencies found in supported files (e.g., requirements.txt, package.json).</p>
                )}
            </div>
        );
    };
    // --- End Added Render Function ---

    // --- Main Component Render Logic ---

    // Display global loading spinner if the main repository data is still loading.
    if (isLoadingRepo) return <LoadingSpinner message={`Loading repository ${id}...`} />;
    // Display global error message if the main repository fetch failed.
    if (repoError) return <ErrorMessage message={repoError} />;
    // Display 'not found' message if loading finished without error but no repository data was retrieved.
    if (!repository) return <p>Repository not found.</p>;

    // --- Render the main detail page content if repository data is available ---
    return (
        <div className="detail-page repo-detail"> {/* Main container with specific class */}
            {/* Page Title: Repository Name */}
            <h2>Repository: {repository.full_name}</h2>
             {/* Core Repository Details Section */}
             <p><strong>ID:</strong> {repository.id}</p>
             <p><strong>GitHub ID:</strong> {repository.github_id}</p>
             <p><strong>Language:</strong> {repository.language || 'N/A'}</p>
             <p><strong>Description:</strong> {repository.description || 'N/A'}</p>
             <p><strong>Stars:</strong> {repository.stargazers_count}</p>
             {/* Link to external GitHub page */}
             <p><strong>URL:</strong> <a href={repository.html_url ?? '#'} target="_blank" rel="noopener noreferrer">{repository.html_url}</a></p>
             {/* Display license information with a link if available */}
             {repository.license && (
                 <p>
                    <strong>License:</strong>{' '}
                    {repository.license.url ? (<a href={repository.license.url} target="_blank" rel="noopener noreferrer">{repository.license.name || repository.license.spdx_id}</a>)
                    : (repository.license.name || repository.license.spdx_id || 'Info Available')}
                 </p>
             )}
             {/* Display repository topics as badges if available */}
             {repository.topics && repository.topics.length > 0 && (
                 <div className="topics-list">
                      <strong>Topics:</strong>{' '}
                      {repository.topics.map((topic, index) => (<span key={index} className="topic-badge">{topic}</span>))}
                 </div>
             )}
            {/* GitHub Timestamps */}
            {repository.gh_created_at && <p><small>Created on GitHub: {new Date(repository.gh_created_at).toLocaleString()}</small></p>}
            {repository.gh_updated_at && <p><small>Updated on GitHub: {new Date(repository.gh_updated_at).toLocaleString()}</small></p>}
            {repository.gh_pushed_at && <p><small>Last Push to GitHub: {new Date(repository.gh_pushed_at).toLocaleString()}</small></p>}

            {/* Separator */}
            <hr />

            {/* Render Related Data Sections using helper functions */}
            {renderCitationCounts()}
            {renderLinkedItems( "Linked Scholarly Works", linkedWorks.works, linkedWorks.loading, linkedWorks.error, "/works", "No linked scholarly works found." )}
            {/* --- Added Call to Render Dependencies --- */}
            {renderDependencies(dependencies)}
            {/* --- End Added Call --- */}
            {renderLinkedItems(
                "Repositories Sharing Contributors",
                sharedContribRepos.repos,
                sharedContribRepos.loading,
                sharedContribRepos.error,
                "/repositories",
                "No other repositories found sharing contributors.",
                true // Enable the "Show Shared" button feature
            )}
            {renderLinkedItems( "Repositories Sharing Linked Works", sharedWorksRepos.repos, sharedWorksRepos.loading, sharedWorksRepos.error, "/repositories", "No other repositories found linking to the same works." )}
            {renderAffiliationsList(affiliations)}


            {/* Relationship Graph Section */}
            <div className="detail-section">
                <h4>Relationship Graph</h4>
                {/* Render graph only if there are nodes other than the main one */}
                {graphNodes.length > 1 ? (
                    <GraphDisplay initialNodes={graphNodes} initialEdges={graphEdges} height="600px" />
                ) : (
                    // Message if no relationships were found to visualize
                    <p>No direct relationships (linked works, affiliations) found to visualize.</p>
                )}
            </div>
        </div> // End detail-page container
    );
};

export default RepositoryDetailPage;