// --- CORRECTED FILE: frontend/src/services/apiClient.ts ---
/**
 * API Client Service
 *
 * This module configures and exports an Axios instance for making requests to the MOSS backend API.
 * It also defines TypeScript interfaces for various API request and response payloads,
 * provides a centralized error handling function, and exports functions for interacting
 * with specific API endpoints.
 */
import axios, { AxiosError } from 'axios';

// --- Axios Client Configuration ---

/** Base URL for the MOSS API. Reads from environment variable VITE_API_BASE_URL or defaults to /api/v1. */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/** Configured Axios instance for API requests. */
const apiClient = axios.create({
    baseURL: API_BASE_URL, // Base URL for all requests
    timeout: 60000, // Request timeout in milliseconds (60 seconds)
    headers: {
      'Content-Type': 'application/json', // Default content type for requests
      'Accept': 'application/json',       // Default accepted response type
    },
  });

// --- API Data Structure Interfaces ---

/** Base interface containing common fields potentially present in API responses (ID, timestamps). */
interface BaseResponse {
  /** Unique identifier (can be number or string like UUID). */
  id?: number | string;
  /** ISO 8601 timestamp string for creation time. */
  created_at?: string;
  /** ISO 8601 timestamp string for last update time. */
  updated_at?: string;
}

// --- Summary Interfaces (Used in lists, search results, related items) ---

/** Summary representation of a Repository. */
export interface RepositorySummary extends BaseResponse {
  id: number;
  /** Full name including owner (e.g., "owner/repo"). */
  full_name: string;
  /** Number of stars on GitHub. */
  stargazers_count?: number;
  /** Primary programming language. */
  language?: string | null;
  /** Repository description. */
  description?: string | null;
  /** URL to the repository on GitHub. */
  html_url?: string | null;
}

/** Summary representation of a Work (e.g., publication, dataset). */
// --- ADDED MISSING INTERFACE (Comment refers to previous code state) ---
export interface WorkSummary extends BaseResponse {
  id: number;
  /** Title of the work. */
  title?: string | null;
  /** Digital Object Identifier. */
  doi?: string | null;
  /** Year of publication. */
  publication_year?: number | null;
}
// --- END ADDED (Comment refers to previous code state) ---

/** Summary representation of a Person (e.g., author, contributor). */
export interface PersonSummary extends BaseResponse {
  id: number;
  /** Primary display name. */
  display_name?: string | null;
  /** ORCID identifier. */
  orcid?: string | null;
}

/** Summary representation of an Institution. */
export interface InstitutionSummary extends BaseResponse {
  id: number;
  /** Primary display name. */
  display_name?: string | null;
  /** Research Organization Registry identifier. */
  ror?: string | null;
}

// --- Topic Hierarchy Summary Interfaces (Used within WorkResponse) ---

/** Summary representation of a top-level OpenAlex Domain concept. */
export interface DomainSummary extends BaseResponse {
    id: number;
    openalex_id: string;
    display_name: string;
}

/** Summary representation of an OpenAlex Field concept (level below Domain). */
export interface FieldSummary extends BaseResponse {
    id: number;
    openalex_id: string;
    display_name: string;
}

/** Summary representation of an OpenAlex Subfield concept (level below Field). */
export interface SubfieldSummary extends BaseResponse {
    id: number;
    openalex_id: string;
    display_name: string;
}

/** Summary representation of an OpenAlex Topic concept (level below Subfield). */
export interface TopicSummary extends BaseResponse {
    id: number;
    openalex_id: string;
    display_name: string;
}

/** Represents the primary topic associated with a Work, including its hierarchical context and score. */
export interface PrimaryTopicResponse extends TopicSummary {
    /** Score indicating relevance or confidence (context-dependent). */
    score?: number | null;
    /** Associated Subfield, if any. */
    subfield?: SubfieldSummary | null;
    /** Associated Field, if any. */
    field?: FieldSummary | null;
    /** Associated Domain, if any. */
    domain?: DomainSummary | null;
}

// --- Full Detail Interfaces (Used for detail page responses) ---

/** Detailed representation of a GitHub Owner (User or Organization). */
export interface OwnerResponse extends BaseResponse {
  id: number;
  github_id: number;
  login: string;
  type: string; // e.g., 'User', 'Organization'
  avatar_url?: string | null;
  html_url?: string | null;
}

/** Detailed representation of a Repository Contributor. */
export interface ContributorResponse extends BaseResponse {
    id: number;
    github_id: number;
    login: string;
    type: string; // e.g., 'User', 'Bot'
    avatar_url?: string | null;
    html_url?: string | null;
}

/** Detailed representation of a Repository. */
export interface RepositoryResponse extends RepositorySummary {
  github_id: number;
  name: string; // Repository name only
  homepage?: string | null;
  api_url?: string | null;
  watchers_count?: number;
  forks_count?: number;
  open_issues_count?: number;
  is_fork?: boolean;
  gh_created_at?: string | null;
  gh_updated_at?: string | null;
  gh_pushed_at?: string | null;
  owner_id?: number | null;
  topics?: string[] | null;
  license?: Record<string, any> | null; // Structure can vary
}

/** Detailed representation of a Work. */
export interface WorkResponse extends WorkSummary {
  openalex_id?: string | null;
  type?: string | null; // e.g., 'article', 'dataset'
  cited_by_count?: number | null;
  host_venue_display_name?: string | null;
  openalex_url?: string | null;
  /** The primary associated topic with hierarchy. */
  primary_topic?: PrimaryTopicResponse | null;
  /** List of all associated topics (including primary). */
  topics?: TopicSummary[] | null;
}

/** Detailed representation of a Person. */
export interface PersonResponse extends PersonSummary {
    openalex_id?: string | null;
    /** Alternative names for the person. */
    display_name_alternatives?: string[] | null;
}

/** Detailed representation of an Institution. */
export interface InstitutionResponse extends InstitutionSummary {
    openalex_id?: string | null;
    country_code?: string | null;
    type?: string | null; // e.g., 'education', 'government'
    /** Potential GitHub organization logins associated with the institution. */
    github_organization_logins?: string[] | null;
}

// --- Discovery & Search Interfaces ---

/** Summary representation of a Discovery Chain process. */
export interface DiscoveryChainSummary extends BaseResponse {
  id: string; // UUID
  root_chain_id?: string | null; // UUID of the root chain if part of a larger process
  level?: number | null; // Depth level in the discovery chain
  discovery_type?: string | null; // e.g., 'url', 'keyword'
  status?: string | null; // e.g., 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED'
  started_at?: string | null;
  completed_at?: string | null;
}

/** Response structure for keyword search session status and results. */
export interface KeywordSearchSessionResponse extends BaseResponse {
  id: number;
  keywords_raw: string; // The original keywords used
  status: string; // e.g., 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED'
  results_count?: number | null; // Number of items processed/found
  started_at?: string | null;
  completed_at?: string | null;
}

// --- Surfacing Interfaces (Data derived from relationships) ---

/** Response structure for aggregated citation counts for a repository. */
export interface RepositoryCitationCountResponse {
    repository_id: number;
    /** Sum of cited_by_count from linked works via OpenAlex data. */
    openalex_aggregated_citations: number;
    /** Count of unique citing works discovered within the MOSS database. */
    moss_discovered_citations: number;
}

// --- Shared Recipes / Algorithms Interfaces ---

/** Metadata describing a single parameter for a recipe or algorithm. */
export interface RecipeParameterMetadataResponse {
  name: string; // Parameter name (key)
  type: string; // Expected data type (e.g., 'str', 'int', 'Optional[List[str]]')
  description: string; // Description of the parameter's purpose
}

/** Metadata describing a shared recipe or algorithm. */
export interface RecipeMetadataResponse {
  name: string; // Unique name
  version: string; // Version identifier
  description: string; // Description of what the recipe/algorithm does
  /** List of parameters the recipe/algorithm accepts. */
  parameters: RecipeParameterMetadataResponse[];
  /** Path to the implementation file on the backend (for informational purposes). */
  file_path: string;
}

/** Request body structure for executing a recipe or algorithm. */
export interface RecipeExecutionRequest {
  /** Dictionary of parameter names and their values. */
  parameters: Record<string, any>;
}

/** General response structure after executing a recipe. */
export interface RecipeExecutionResponse {
  /** Boolean indicating if the execution was successful. */
  success: boolean;
  /** The actual result data (structure depends on the recipe). */
  data?: any;
  /** Error details if success is false. */
  error?: {
      /** General error category or type. */
      error?: string;
      /** Specific error message. */
      message?: string;
  };
}

// --- Affiliation Algorithm Specific Interfaces ---

/** Request body structure for executing an affiliation algorithm. */
export interface AffiliationExecutionRequest {
    /** ID of the target institution. */
    institution_id: number;
    /** Dictionary of algorithm-specific parameters. */
    parameters: Record<string, any>;
}

/** Response structure after executing an affiliation algorithm (provides status and counts). */
export interface AffiliationExecutionResponse {
    /** Execution status (e.g., 'STARTED', 'COMPLETED', 'FAILED'). */
    status: string;
    /** Message describing the outcome or status. */
    message: string;
    /** Number of repositories processed during execution. */
    processed_count: number;
    /** Number of new affiliation records created. */
    created_count: number;
    /** Number of existing affiliation records updated. */
    updated_count: number;
}

/** Response structure representing a calculated affiliation between a repository and an institution. */
export interface AffiliationResultResponse extends BaseResponse {
    repository_id: number;
    institution_id: number;
    algorithm_name: string;
    algorithm_version: string;
    /** Calculated score indicating confidence or strength of affiliation. */
    confidence_score: number;
    /** Optional evidence data used by the algorithm (structure varies). */
    evidence?: Record<string, any> | null;
    /** Optional parameters used during this specific calculation. */
    parameters_used?: Record<string, any> | null;
    /** Timestamp when the affiliation was calculated. */
    calculated_at: string; // ISO datetime string
    /** Optional repository name (denormalized for convenience). */
    repository_name?: string | null;
    /** Optional institution name (denormalized for convenience). */
    institution_name?: string | null;
}

// --- Ingestion History Interface ---

/** Response structure providing context about the last relevant ingestion event. */
export interface IngestionHistoryContextResponse {
    /** Type of parameter used for context lookup (e.g., 'keyword', 'url'). */
    param_type: string;
    /** Value of the parameter used for context lookup. */
    param_value: string;
    /** Timestamp of the last ingestion relevant to these parameters. */
    last_ingested_at?: string | null; // ISO datetime string
    /** Type of the last relevant ingestion (e.g., 'keyword_search', 'url_ingestion'). */
    ingestion_type?: string | null;
}

// --- Discovery Algorithm Interfaces ---

/** Expected response type when executing a discovery algorithm (a list of candidate URLs). */
export type DiscoveryExecutionResponse = string[];

// --- Software Dependency Interface ---

/** Response structure representing a software dependency identified in a repository. */
export interface SoftwareDependencyResponse extends BaseResponse {
    id: number;
    repository_id: number;
    /** Name of the dependency package/library. */
    dependency_name: string;
    /** Version constraint specified (e.g., '>=1.0', '==2.5.1'). */
    version_constraint?: string | null;
    /** File where the dependency was found (e.g., 'requirements.txt'). */
    source_file: string;
    /** Type or manager associated with the dependency (e.g., 'pip', 'npm'). */
    dependency_type: string;
    /** Flag indicating if it's a development dependency. */
    is_dev_dependency?: boolean | null;
    created_at: string;
    updated_at: string;
}

// --- Error Handling ---

/**
 * Centralized error handler for API calls made with Axios.
 * Parses Axios errors and other error types to return a user-friendly string message.
 * Logs detailed error information to the console for debugging.
 * @param error The error object caught from an API call.
 * @returns A string message summarizing the error.
 */
export const handleApiError = (error: unknown): string => {
  // Check if it's an Axios-specific error
  if (axios.isAxiosError(error)) {
    // Cast to AxiosError to access response/request properties safely
    const axiosError = error as AxiosError<{ detail?: string | any }>; // Assume detail might be string or other type
    console.error('API Error:', axiosError.response?.status, axiosError.response?.data);

    // Error with a response from the server
    if (axiosError.response) {
      // Check if the response data has a 'detail' field (common in FastAPI errors)
      if (typeof axiosError.response.data?.detail === 'string') {
          // Return the string detail directly
          return axiosError.response.data.detail;
      } else if (Array.isArray(axiosError.response.data?.detail)) {
          // Handle FastAPI validation errors which return 'detail' as an array of objects
          return axiosError.response.data.detail
              .map((err: any) => `${err.loc?.join('.')} - ${err.msg}`) // Format location and message
              .join('; '); // Join multiple validation errors
      } else if (axiosError.response.data?.detail) {
          // If detail is present but not a string or array, stringify it
          return JSON.stringify(axiosError.response.data.detail);
      }
      // Fallback to using HTTP status code and text
      return `Error ${axiosError.response.status}: ${axiosError.response.statusText}`;
    }
    // Error without a response (network issue, timeout, etc.)
    else if (axiosError.request) {
      return 'Network error: No response received from server.';
    }
    // Error during request setup
    else {
      return `Request setup error: ${axiosError.message}`;
    }
  }
  // Handle standard JavaScript Error objects
  else if (error instanceof Error) {
    console.error('Non-API Error:', error);
    return `An unexpected error occurred: ${error.message}`;
  }
  // Handle unknown error types
  else {
    console.error('Unknown Error:', error);
    return 'An unknown error occurred.';
  }
};


// --- API Function Definitions ---
// Each function corresponds to a specific API endpoint.
// They use the configured `apiClient`, handle potential errors using `handleApiError`,
// and return typed responses based on the interfaces defined above.

// ... (All existing API functions remain the same, comments would be repetitive here unless describing specific nuances) ...

// --- Ingestion Endpoints ---
/** Triggers the ingestion process for a single repository URL. */
export const triggerUrlIngestion = async (url: string): Promise<DiscoveryChainSummary> => {
  try {
    const response = await apiClient.post<DiscoveryChainSummary>('/ingest/url', { url });
    return response.data;
  } catch (error) {
    throw new Error(handleApiError(error)); // Throw standardized error message
  }
};

/** Triggers the keyword-based repository discovery and ingestion process. */
export const triggerKeywordIngestion = async (keywords: string): Promise<KeywordSearchSessionResponse> => {
    try {
        const response = await apiClient.post<KeywordSearchSessionResponse>('/ingest/keywords', { keywords });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Fetches the current status of a specific keyword search session. */
export const getKeywordSessionStatus = async (sessionId: number): Promise<KeywordSearchSessionResponse> => {
    try {
        const response = await apiClient.get<KeywordSearchSessionResponse>(`/ingest/keywords/status/${sessionId}`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Retrieval Endpoints (Get single entity by ID) ---
/** Retrieves detailed information for a specific repository by its MOSS ID. */
export const getRepository = async (id: number): Promise<RepositoryResponse> => {
    try {
        const response = await apiClient.get<RepositoryResponse>(`/retrieve/repositories/${id}`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves detailed information for a specific work by its MOSS ID. */
export const getWork = async (id: number): Promise<WorkResponse> => {
    try {
        const response = await apiClient.get<WorkResponse>(`/retrieve/works/${id}`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves detailed information for a specific person by their MOSS ID. */
export const getPerson = async (id: number): Promise<PersonResponse> => {
    try {
        const response = await apiClient.get<PersonResponse>(`/retrieve/persons/${id}`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves detailed information for a specific institution by its MOSS ID. */
export const getInstitution = async (id: number): Promise<InstitutionResponse> => {
    try {
        const response = await apiClient.get<InstitutionResponse>(`/retrieve/institutions/${id}`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves detailed information for a specific contributor by their MOSS ID. */
export const getContributor = async (id: number): Promise<ContributorResponse> => {
    try {
        const response = await apiClient.get<ContributorResponse>(`/retrieve/contributors/${id}`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Surfacing Endpoints (Get related entities) ---
/** Retrieves a list of works linked to a specific repository. */
export const getRepositoryWorks = async (repoId: number): Promise<WorkSummary[]> => {
    try {
        const response = await apiClient.get<WorkSummary[]>(`/surface/repositories/${repoId}/works`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of repositories linked to a specific work. */
export const getWorkRepositories = async (workId: number): Promise<RepositorySummary[]> => {
    try {
        const response = await apiClient.get<RepositorySummary[]>(`/surface/works/${workId}/repositories`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of works that cite a specific work. */
export const getWorkCitations = async (workId: number): Promise<WorkSummary[]> => {
    try {
        const response = await apiClient.get<WorkSummary[]>(`/surface/works/${workId}/citations`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of works referenced by a specific work. */
export const getWorkReferences = async (workId: number): Promise<WorkSummary[]> => {
    try {
        const response = await apiClient.get<WorkSummary[]>(`/surface/works/${workId}/references`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves aggregated citation counts for a specific repository. */
export const getRepositoryCitationCount = async (repoId: number): Promise<RepositoryCitationCountResponse> => {
    try {
        const response = await apiClient.get<RepositoryCitationCountResponse>(`/surface/repositories/${repoId}/citation_count`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of repositories that share contributors with a specific repository. */
export const getRepositoriesSharingContributors = async (repoId: number): Promise<RepositorySummary[]> => {
    try {
        const response = await apiClient.get<RepositorySummary[]>(`/surface/repositories/${repoId}/shared_contributors`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of repositories linked to the same works as a specific repository. */
export const getRepositoriesSharingWorks = async (repoId: number): Promise<RepositorySummary[]> => {
    try {
        const response = await apiClient.get<RepositorySummary[]>(`/surface/repositories/${repoId}/shared_works`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of people whose works cite a specific work. */
export const getWorkCitingPeople = async (workId: number): Promise<PersonSummary[]> => {
    try {
        const response = await apiClient.get<PersonSummary[]>(`/surface/works/${workId}/citing_people`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of institutions whose works cite a specific work. */
export const getWorkCitingInstitutions = async (workId: number): Promise<InstitutionSummary[]> => {
    try {
        const response = await apiClient.get<InstitutionSummary[]>(`/surface/works/${workId}/citing_institutions`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of repositories linked (via works) to a specific institution. */
export const getInstitutionRepositories = async (instId: number): Promise<RepositorySummary[]> => {
    try {
        const response = await apiClient.get<RepositorySummary[]>(`/surface/institutions/${instId}/repositories`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of works associated with a specific person. */
export const getPersonWorks = async (personId: number): Promise<WorkSummary[]> => {
    try {
        const response = await apiClient.get<WorkSummary[]>(`/surface/persons/${personId}/works`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves detailed information about contributors shared between two specific repositories. */
export const getSharedContributorsDetails = async (repoId1: number, repoId2: number): Promise<ContributorResponse[]> => {
    try {
        const response = await apiClient.get<ContributorResponse[]>(`/surface/repositories/${repoId1}/shared_contributors_with/${repoId2}`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves a list of repositories associated with a specific contributor. */
export const getContributorRepositories = async (contributorId: number): Promise<RepositorySummary[]> => {
    try {
        const response = await apiClient.get<RepositorySummary[]>(`/surface/contributors/${contributorId}/repositories`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Shared Recipe/Query Endpoints ---
/** Retrieves metadata for all available analysis recipes. */
export const getAnalysisRecipes = async (): Promise<RecipeMetadataResponse[]> => {
    try {
        const response = await apiClient.get<RecipeMetadataResponse[]>('/shared-recipes/');
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Executes a specific analysis recipe with the provided parameters. */
export const executeAnalysisRecipe = async (
    name: string,
    version: string,
    params: Record<string, any>
): Promise<RecipeExecutionResponse> => {
    try {
        const requestBody: RecipeExecutionRequest = { parameters: params };
        const response = await apiClient.post<RecipeExecutionResponse>(`/shared-recipes/execute/${name}/${version}`, requestBody);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Affiliation Algorithm Endpoints ---
/** Retrieves metadata for all available affiliation algorithms. */
export const getAffiliationAlgorithms = async (): Promise<RecipeMetadataResponse[]> => {
    try {
        const response = await apiClient.get<RecipeMetadataResponse[]>('/affiliation-algorithms/');
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Executes a specific affiliation algorithm for a given institution with provided parameters. */
export const executeAffiliationAlgorithm = async (
    name: string,
    version: string,
    instId: number,
    params: Record<string, any>
): Promise<AffiliationExecutionResponse> => {
    try {
        const requestBody: AffiliationExecutionRequest = { institution_id: instId, parameters: params };
        const response = await apiClient.post<AffiliationExecutionResponse>(`/affiliation-algorithms/execute/${name}/${version}`, requestBody);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves all stored affiliation results for a specific institution. */
export const getInstitutionAffiliationResults = async (instId: number): Promise<AffiliationResultResponse[]> => {
    try {
        const response = await apiClient.get<AffiliationResultResponse[]>(`/surface/institutions/${instId}/affiliation_results`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves stored affiliation results for an institution, filtered by minimum confidence. */
export const getInstitutionAffiliationsFiltered = async (instId: number, minConfidence?: number): Promise<AffiliationResultResponse[]> => {
    try {
        const response = await apiClient.get<AffiliationResultResponse[]>(`/surface/institutions/${instId}/affiliations`, {
            // Pass min_confidence as a query parameter if provided
            params: minConfidence !== undefined ? { min_confidence: minConfidence } : {}
        });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Retrieves stored affiliation results for a repository, filtered by minimum confidence. */
export const getRepositoryAffiliationsFiltered = async (repoId: number, minConfidence?: number): Promise<AffiliationResultResponse[]> => {
    try {
        const response = await apiClient.get<AffiliationResultResponse[]>(`/surface/repositories/${repoId}/affiliations`, {
            // Pass min_confidence as a query parameter if provided
            params: minConfidence !== undefined ? { min_confidence: minConfidence } : {}
        });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Ingestion History Endpoint ---
/** Retrieves context about the last ingestion relevant to a specific parameter type and value. */
export const getIngestionHistoryContext = async (paramType: string, paramValue: string): Promise<IngestionHistoryContextResponse> => {
    try {
        const response = await apiClient.get<IngestionHistoryContextResponse>(`/ingestion-history/context`, {
            params: { param_type: paramType, param_value: paramValue }
        });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Discovery Algorithm Endpoints ---
/** Retrieves metadata for all available discovery algorithms. */
export const getDiscoveryAlgorithms = async (): Promise<RecipeMetadataResponse[]> => {
    try {
        const response = await apiClient.get<RecipeMetadataResponse[]>('/discovery-algorithms/');
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Executes a specific discovery algorithm with provided parameters, returning candidate URLs. */
export const executeDiscoveryAlgorithm = async (
    name: string,
    version: string,
    requestBody: RecipeExecutionRequest // Use the request type directly
): Promise<DiscoveryExecutionResponse> => { // Expects string[]
    try {
        const response = await apiClient.post<DiscoveryExecutionResponse>(`/discovery-algorithms/execute/${name}/${version}`, requestBody);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Dependency Endpoint ---
/** Retrieves a list of software dependencies identified for a specific repository. */
export const getRepositoryDependencies = async (repoId: number): Promise<SoftwareDependencyResponse[]> => {
    try {
        const response = await apiClient.get<SoftwareDependencyResponse[]>(`/surface/repositories/${repoId}/dependencies`);
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

// --- Search Endpoints ---
/** Searches for repositories matching the query string. Supports pagination. */
export const searchRepositories = async (query: string, skip: number = 0, limit: number = 100): Promise<RepositorySummary[]> => {
    try {
        const response = await apiClient.get<RepositorySummary[]>('/search/repositories', {
            params: { q: query, skip, limit } // Pass query and pagination params
        });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Searches for works matching the query string. Supports pagination. */
export const searchWorks = async (query: string, skip: number = 0, limit: number = 100): Promise<WorkSummary[]> => {
    try {
        const response = await apiClient.get<WorkSummary[]>('/search/works', {
            params: { q: query, skip, limit }
        });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Searches for people matching the query string. Supports pagination. */
export const searchPeople = async (query: string, skip: number = 0, limit: number = 100): Promise<PersonSummary[]> => {
    try {
        const response = await apiClient.get<PersonSummary[]>('/search/people', {
            params: { q: query, skip, limit }
        });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};

/** Searches for institutions matching the query string. Supports pagination. */
export const searchInstitutions = async (query: string, skip: number = 0, limit: number = 100): Promise<InstitutionSummary[]> => {
    try {
        const response = await apiClient.get<InstitutionSummary[]>('/search/institutions', {
            params: { q: query, skip, limit }
        });
        return response.data;
    } catch (error) {
        throw new Error(handleApiError(error));
    }
};