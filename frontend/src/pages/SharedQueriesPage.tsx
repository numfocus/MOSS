// frontend/src/pages/SharedQueriesPage.tsx ---
import React, { useState, useEffect, useCallback, ChangeEvent, FormEvent, useMemo } from 'react';
// import { Link } from 'react-router-dom'; // Not currently used, can be removed if not needed later
import {
    // Analysis Recipes API functions and types
    getAnalysisRecipes,
    executeAnalysisRecipe,
    type RecipeExecutionResponse, // Use import type as only the type is needed here
    // Affiliation Workflow API functions and types
    getAffiliationAlgorithms,
    getInstitutionAffiliationResults,
    executeAffiliationAlgorithm,
    searchInstitutions,
    getIngestionHistoryContext,
    type InstitutionSummary, // Use import type
    type AffiliationResultResponse, // Use import type
    type AffiliationExecutionResponse, // Use import type
    type IngestionHistoryContextResponse, // Use import type
    // Discovery Workflow API functions and types
    getDiscoveryAlgorithms,
    executeDiscoveryAlgorithm,
    triggerUrlIngestion, // Reuse ingestion trigger from apiClient
    // Shared API Types
    type RecipeMetadataResponse, // Use import type for recipe metadata structure
    type RecipeParameterMetadataResponse, // Use import type for recipe parameter structure
    // DiscoveryExecutionResponse, // Removed unused import
    type DiscoveryExecutionRequest // Use import type for discovery execution request body
} from '../services/apiClient'; // Adjust path as needed for your project structure
import LoadingSpinner, { type LoadingSpinnerProps } from '../components/LoadingSpinner'; // Use import type for component props
import ErrorMessage, { type ErrorMessageProps } from '../components/ErrorMessage'; // Use import type for component props
// --- Use import type for interfaces/types from component props ---
import SimpleTable, { type TableColumn } from '../components/SimpleTable'; // Import table component and its column type definition
// --- End import type ---
import './SharedQueriesPage.css'; // Make sure page-specific CSS is imported

// --- Type Definitions ---

/** Type alias for form parameter state, representing a flexible key-value store. */
type FormParams = Record<string, any>;

/** Defines the possible stages of the multi-step workflow managed by this page. */
type WorkflowStage = 'initial' | 'affiliation_setup' | 'analysis_selection';

/**
 * Interface describing the expected structure of the `data` field within a `RecipeExecutionResponse`.
 * This is used for type guarding when rendering analysis results.
 */
interface NestedResultData {
    /** Optional string indicating the type of the result (e.g., 'table', 'value'). */
    result_type?: string;
    /** The actual result data, can be of any type. */
    data?: any;
    /** Optional notes returned by the recipe, can be a single string or an array of strings. */
    notes?: string[] | string | null;
}

/**
 * `SharedQueriesPage` Component
 *
 * Provides a UI for interacting with predefined analysis recipes and workflows.
 * It supports two main modes:
 * 1. Standard Mode: Select and run any analysis recipe directly, providing parameters.
 * 2. Institution-Centric Workflow: A multi-step process involving:
 *    a. Selecting an institution.
 *    b. Reviewing/calculating repository affiliations for that institution.
 *    c. Optionally discovering and ingesting more related repositories.
 *    d. Proceeding to run analysis recipes specifically on the affiliated repositories.
 *
 * Manages state for recipe/algorithm selection, parameter input, execution status,
 * results display, and workflow progression.
 */
const SharedQueriesPage: React.FC = () => {
    // --- State for Workflow Control ---
    /** Controls the current stage of the UI (initial standard mode, affiliation setup, analysis selection). */
    const [workflowStage, setWorkflowStage] = useState<WorkflowStage>('initial');

    // --- State for Analysis Recipe Workflow (Used in both modes) ---
    /** List of available analysis recipes fetched from the API. */
    const [analysisRecipes, setAnalysisRecipes] = useState<RecipeMetadataResponse[]>([]);
    /** The currently selected analysis recipe metadata. */
    const [selectedAnalysisRecipe, setSelectedAnalysisRecipe] = useState<RecipeMetadataResponse | null>(null);
    /** Stores the parameter values entered by the user for the selected analysis recipe. */
    const [analysisParams, setAnalysisParams] = useState<FormParams>({});
    /** Loading state flag specifically for analysis recipe execution. */
    const [isAnalysisExecuting, setIsAnalysisExecuting] = useState<boolean>(false);
    /** Stores the result object returned after executing an analysis recipe. */
    const [analysisExecutionResult, setAnalysisExecutionResult] = useState<RecipeExecutionResponse | null>(null);
    /** Stores any error message related to analysis recipe execution. */
    const [analysisExecutionError, setAnalysisExecutionError] = useState<string | null>(null);
    /** Loading state flag for fetching the list of analysis recipes initially. */
    const [isAnalysisLoading, setIsAnalysisLoading] = useState<boolean>(true);
    /** Stores any error message related to fetching the list of analysis recipes. */
    const [analysisError, setAnalysisError] = useState<string | null>(null);

    // --- State for Affiliation Workflow (Used in 'affiliation_setup' stage) ---
    /** The search query entered by the user to find an institution. */
    const [institutionQuery, setInstitutionQuery] = useState<string>('');
    /** List of institution search results based on the `institutionQuery`. */
    const [institutionSearchResults, setInstitutionSearchResults] = useState<InstitutionSummary[]>([]);
    /** The currently selected institution object. */
    const [selectedInstitution, setSelectedInstitution] = useState<InstitutionSummary | null>(null);
    /** List of available affiliation algorithms fetched from the API. */
    const [affiliationAlgorithms, setAffiliationAlgorithms] = useState<RecipeMetadataResponse[]>([]);
    /** The currently selected affiliation algorithm metadata. */
    const [selectedAffiliationAlgorithm, setSelectedAffiliationAlgorithm] = useState<RecipeMetadataResponse | null>(null);
    /** Stores the parameter values entered for the selected affiliation algorithm. */
    const [affiliationParams, setAffiliationParams] = useState<FormParams>({});
    /** Loading state flag specifically for affiliation algorithm execution. */
    const [isAffiliationExecuting, setIsAffiliationExecuting] = useState<boolean>(false);
    /** Stores the result object returned after executing an affiliation algorithm. */
    const [affiliationExecutionResult, setAffiliationExecutionResult] = useState<AffiliationExecutionResponse | null>(null);
    /** Stores any error message related to affiliation algorithm execution. */
    const [affiliationExecutionError, setAffiliationExecutionError] = useState<string | null>(null);
    /** Stores the list of calculated affiliation results fetched for the selected institution. */
    const [affiliationResults, setAffiliationResults] = useState<AffiliationResultResponse[]>([]);
    /** Loading state flag for fetching existing affiliation results. */
    const [isAffiliationResultsLoading, setIsAffiliationResultsLoading] = useState<boolean>(false);
    /** Stores any error message related to fetching existing affiliation results. */
    const [affiliationResultsError, setAffiliationResultsError] = useState<string | null>(null);
    /** Stores contextual information about the last relevant ingestion for the selected institution. */
    const [ingestionContext, setIngestionContext] = useState<IngestionHistoryContextResponse | null>(null);
    /** Loading state flag for fetching the ingestion context. */
    const [isIngestionContextLoading, setIsIngestionContextLoading] = useState<boolean>(false);
    /** Stores any error message related to fetching the ingestion context. */
    const [ingestionContextError, setIngestionContextError] = useState<string | null>(null);
    /** The confidence threshold used to filter displayed affiliation results. */
    const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.5);
    /** Loading state flag for fetching the list of affiliation algorithms. */
    const [isAffiliationLoading, setIsAffiliationLoading] = useState<boolean>(false);
    /** Stores any error message related to fetching the list of affiliation algorithms. */
    const [affiliationError, setAffiliationError] = useState<string | null>(null);
    /** Stores the list of repository IDs derived from filtered affiliations, passed to the analysis stage. */
    const [selectedRepositoryIds, setSelectedRepositoryIds] = useState<number[]>([]);

    // --- State for Discovery Workflow (Integrated into 'affiliation_setup' stage) ---
    /** Controls the visibility of the discovery algorithm section. */
    const [showDiscoverySection, setShowDiscoverySection] = useState(false);
    /** List of available discovery algorithms fetched from the API. */
    const [discoveryAlgorithms, setDiscoveryAlgorithms] = useState<RecipeMetadataResponse[]>([]);
    /** Loading state flag for fetching the list of discovery algorithms. */
    const [isDiscoveryAlgosLoading, setIsDiscoveryAlgosLoading] = useState(false);
    /** Stores any error message related to fetching the list of discovery algorithms. */
    const [discoveryAlgosError, setDiscoveryAlgosError] = useState<string | null>(null);
    /** The currently selected discovery algorithm metadata. */
    const [selectedDiscoveryAlgorithm, setSelectedDiscoveryAlgorithm] = useState<RecipeMetadataResponse | null>(null);
    /** Stores the parameter values entered for the selected discovery algorithm. */
    const [discoveryParams, setDiscoveryParams] = useState<FormParams>({});
    /** Loading state flag specifically for discovery algorithm execution. */
    const [isDiscovering, setIsDiscovering] = useState(false);
    /** Stores any error message related to discovery algorithm execution. */
    const [discoveryError, setDiscoveryError] = useState<string | null>(null);
    /** Stores the list of candidate repository URLs returned by the discovery algorithm. */
    const [candidateUrls, setCandidateUrls] = useState<string[] | null>(null);
    /** Stores the selection state (checked/unchecked) for each candidate URL. */
    const [selectedUrlsToIngest, setSelectedUrlsToIngest] = useState<Record<string, boolean>>({});
    /** Loading state flag for triggering the ingestion of selected candidate URLs. */
    const [isIngestingCandidates, setIsIngestingCandidates] = useState(false);
    /** Stores progress messages during the candidate ingestion triggering process. */
    const [ingestionProgress, setIngestionProgress] = useState<string>('');
    /** Stores the success/failure status for each triggered ingestion attempt. */
    const [ingestionResults, setIngestionResults] = useState<Record<string, { success: boolean; message: string }>>({});
    // --- End Discovery State ---

    // --- Helper Functions ---

    /**
     * Parses a combined string value (e.g., from a select option) into its name and version components.
     * Assumes the format "name_vVersion".
     * @param value The combined string value.
     * @returns An object containing the extracted name and version, or nulls if parsing fails.
     */
    const parseNameVersion = (value: string): { name: string | null, version: string | null } => {
        if (!value) return { name: null, version: null };
        // Find the last occurrence of '_v' which separates name and version.
        const separatorIndex = value.lastIndexOf('_v');
        if (separatorIndex === -1) {
            // Log error if the expected format is not found.
            console.error(`Invalid recipe/algorithm value format: ${value}. Expected 'name_vVersion'.`);
            return { name: null, version: null };
        }
        // Extract name and version parts based on the separator index.
        const name = value.substring(0, separatorIndex);
        const version = value.substring(separatorIndex + 1);
        return { name, version };
    };

    // --- Helper Functions for Dynamic List Inputs ---
    // These functions manage state updates for parameters that expect a list of strings.

    /**
     * Updates a specific item within a list parameter in the form state.
     * @param setter The state setter function (e.g., `setAnalysisParams`).
     * @param paramName The name of the list parameter in the state.
     * @param index The index of the item to update within the list.
     * @param newValue The new value for the list item.
     */
    const handleUpdateListItem = (
        setter: React.Dispatch<React.SetStateAction<FormParams>>,
        paramName: string,
        index: number,
        newValue: string
    ) => {
        setter(prevParams => {
            // Get the current list or initialize if it doesn't exist or isn't an array.
            const currentList = Array.isArray(prevParams[paramName]) ? [...prevParams[paramName]] : [];
            // Update the item at the specified index if valid.
            if (index >= 0 && index < currentList.length) {
                currentList[index] = newValue;
            }
            // Return the updated parameters object.
            return { ...prevParams, [paramName]: currentList };
        });
    };

    /**
     * Adds a new empty item to a list parameter in the form state.
     * @param setter The state setter function.
     * @param paramName The name of the list parameter.
     */
    const handleAddListItem = (
        setter: React.Dispatch<React.SetStateAction<FormParams>>,
        paramName: string
    ) => {
        setter(prevParams => {
            // Get the current list or initialize.
            const currentList = Array.isArray(prevParams[paramName]) ? [...prevParams[paramName]] : [];
            // Create a new list with an additional empty string item.
            const newList = [...currentList, ''];
            // Return the updated parameters object.
            return { ...prevParams, [paramName]: newList };
        });
    };

    /**
     * Removes an item from a list parameter in the form state at the specified index.
     * Ensures at least one (potentially empty) input remains if the list becomes empty.
     * @param setter The state setter function.
     * @param paramName The name of the list parameter.
     * @param index The index of the item to remove.
     */
    const handleRemoveListItem = (
        setter: React.Dispatch<React.SetStateAction<FormParams>>,
        paramName: string,
        index: number
    ) => {
        setter(prevParams => {
            // Get the current list or initialize.
            const currentList = Array.isArray(prevParams[paramName]) ? [...prevParams[paramName]] : [];
            // Filter out the item at the specified index.
            let newList = currentList.filter((_, i) => i !== index);
            // If removing the item results in an empty list, reset it to contain one empty string input.
            if (newList.length === 0) {
                newList = [''];
            }
            // Return the updated parameters object.
            return { ...prevParams, [paramName]: newList };
        });
    };

    /**
     * Handles changes for simple (non-list) parameter input fields (text, number, select, checkbox).
     * Updates the corresponding parameter value in the form state.
     * @param setter The state setter function.
     * @param e The change event object from the input element.
     */
    const handleSimpleParamChange = (
        setter: React.Dispatch<React.SetStateAction<FormParams>>,
        e: ChangeEvent<HTMLInputElement | HTMLSelectElement>
    ) => {
        const { name, value, type } = e.target;
        // Handle checkboxes specifically, otherwise use the input value.
        const newValue = type === 'checkbox' ? (e.target as HTMLInputElement).checked : value;
        // Update the state using the input's 'name' attribute as the key.
        setter(prev => ({ ...prev, [name]: newValue }));
    };
    // --- End Dynamic List Helpers ---


    /**
     * Prepares parameter values for API execution based on recipe/algorithm metadata.
     * It trims strings, filters empty items from lists, attempts type coercion (int, float, bool),
     * validates required parameters, and merges extra parameters.
     * @param metadataParams The parameter metadata array from the selected recipe/algorithm.
     * @param currentParams The current parameter values from the component's state.
     * @param exclude An array of parameter names to exclude from the final object (e.g., 'db_conn_str').
     * @param extraParams Additional parameters to merge (e.g., `{ repository_ids: [...] }`).
     * @returns An object containing `paramsToSend` (the prepared parameters) and `error` (a validation error message, or null).
     */
    const prepareParamsForExecution = (
        metadataParams: RecipeParameterMetadataResponse[] | undefined,
        currentParams: FormParams,
        exclude: string[] = [], // Parameters to explicitly exclude (like connection strings)
        extraParams: FormParams = {} // Extra params to add (like repo IDs from workflow)
    ): { paramsToSend: FormParams; error: string | null } => {

        const paramsToSend: FormParams = { ...extraParams }; // Start with extra params
        let errorMessage: string | null = null;
        const requiredParamsList: string[] = []; // Track names of missing/invalid required params
        let missingRequired = false; // Flag if any required param is missing/invalid

        // If no parameters are defined in metadata, return immediately.
        if (!metadataParams) {
            return { paramsToSend, error: null };
        }

        // Iterate over each parameter defined in the metadata.
        metadataParams.forEach(param => {
            // Skip parameters listed in the 'exclude' array.
            if (exclude.includes(param.name)) return;

            // Determine if the parameter is optional based on its type string.
            const isOptional = param.type.startsWith('Optional[') || param.type.includes(' | None') || param.type.includes('Optional');
            // Get the current value from the form state.
            const value = currentParams[param.name];
            // Check if the parameter type indicates a list of strings.
            const isStringListType = (param.type.toLowerCase().includes('list[str]') || param.type.toLowerCase().includes('List[str]') || param.type.includes('[]')) && param.type.toLowerCase().includes('str');

            // --- Handle List Parameters ---
            if (isStringListType) {
                // Filter out empty/whitespace-only strings from the list.
                const filteredList = Array.isArray(value) ? value.filter(item => String(item).trim() !== '') : [];
                // Check if required but the filtered list is empty.
                if (!isOptional && filteredList.length === 0) {
                    missingRequired = true;
                    requiredParamsList.push(`${param.name} (at least one item required)`);
                }
                // Assign the filtered list to the parameters to send.
                paramsToSend[param.name] = filteredList;
            }
            // --- Handle Non-List Parameters ---
            else {
                // Trim whitespace from the string representation of the value.
                const stringValue = String(value ?? '').trim();
                // Check if required but the trimmed value is empty.
                if (!isOptional && stringValue === '') {
                    missingRequired = true;
                    requiredParamsList.push(param.name);
                }
                // Process non-empty values.
                else if (stringValue !== '') {
                    let parsedValue: any = value; // Start with the original value
                    let parseError = false; // Flag for type coercion errors

                    // Attempt type coercion based on the metadata type string.
                    if (param.type === 'int' || param.type === 'Optional[int]') {
                        const numValue = parseInt(stringValue, 10);
                        if (isNaN(numValue)) { // Check if parsing failed
                            parseError = true; requiredParamsList.push(`${param.name} (must be a valid integer)`);
                        } else { parsedValue = numValue; }
                    } else if (param.type === 'float' || param.type === 'Optional[float]') {
                        const floatValue = parseFloat(stringValue);
                        if (isNaN(floatValue)) { // Check if parsing failed
                            parseError = true; requiredParamsList.push(`${param.name} (must be a valid number)`);
                        } else { parsedValue = floatValue; }
                    } else if (param.type === 'bool' || param.type === 'Optional[bool]') {
                        // Coerce 'true'/'false' strings to boolean.
                        if (stringValue.toLowerCase() === 'true') parsedValue = true;
                        else if (stringValue.toLowerCase() === 'false') parsedValue = false;
                        else { // Invalid boolean string
                            parseError = true; requiredParamsList.push(`${param.name} (must be 'true' or 'false')`);
                        }
                    }
                    // Add other type coercions here if needed (e.g., for dates)

                    // If parsing failed for a required parameter, flag it.
                    if (parseError && !isOptional) {
                        missingRequired = true;
                    }
                    // Assign the potentially coerced value.
                    paramsToSend[param.name] = parsedValue;
                }
                // Handle empty/nullish values for optional parameters.
                else {
                    if (!isOptional) {
                        // This case should ideally be caught by the earlier check, but included for robustness.
                        missingRequired = true;
                        requiredParamsList.push(param.name);
                    } else {
                        // Send explicit null for empty optional parameters, which might be expected by the backend.
                         paramsToSend[param.name] = null;
                    }
                }
            }
        });

        // If any required parameters were missing or invalid, construct an error message.
        if (missingRequired) {
            errorMessage = `Please fill in all required parameters correctly: ${requiredParamsList.join(', ')}`;
        }

        // Return the prepared parameters and any validation error message.
        return { paramsToSend, error: errorMessage };
    };


    /**
     * Renders input fields for recipe/algorithm parameters based on metadata.
     * Supports standard input types (text, number) and dynamic list inputs for 'List[str]'.
     * Excludes specified parameters (like 'db_conn_str').
     * @param params The parameter metadata array.
     * @param values The current parameter values from component state.
     * @param paramSetter The state setter function to update parameter values.
     * @param idPrefix A prefix for generating unique input field IDs.
     * @param exclude An array of parameter names to exclude from rendering.
     * @returns An array of JSX elements representing the input fields, or null/message if no parameters.
     */
    // --- Render Parameter Inputs Helper (REVISED for Dynamic Lists) ---
    const renderParameterInputs = (
        params: RecipeParameterMetadataResponse[] | undefined,
        values: FormParams,
        paramSetter: React.Dispatch<React.SetStateAction<FormParams>>,
        idPrefix: string, // Prefix for unique IDs
        exclude: string[] = ['db_conn_str'] // Default excluded params
    ) => {
        if (!params) return null; // No metadata, nothing to render
        // Filter out excluded parameters.
        const userParams = params.filter(p => !exclude.includes(p.name));
        // If no user-facing parameters remain, show a message.
        if (userParams.length === 0) {
            return <p>This recipe/algorithm requires no user-provided parameters.</p>;
        }

        // Map over the user-facing parameters to create input elements.
        return userParams.map((param) => {
            // Determine if optional based on type string.
            const isOptional = param.type.startsWith('Optional[') || param.type.includes(' | None') || param.type.includes('Optional');
            // Determine if it's a list-of-strings type.
            const isStringListType = (param.type.toLowerCase().includes('list[str]') || param.type.toLowerCase().includes('List[str]') || param.type.includes('[]')) && param.type.toLowerCase().includes('str');
            // Base ID for elements related to this parameter.
            const inputIdBase = `${idPrefix}_param_${param.name}`;

            // --- Render Dynamic List Input ---
            if (isStringListType) {
                // Get the current list from state, defaulting to an array with one empty string if not set or empty.
                const currentList: string[] = Array.isArray(values[param.name]) && values[param.name].length > 0
                    ? values[param.name]
                    : [''];

                return (
                    <div key={param.name} className="form-group parameter-input-group list-parameter-group">
                        {/* Label including name, type, required indicator, and description */}
                        <label>
                            {param.name} (<code>{param.type}</code>){!isOptional && <span className="required-indicator">*</span>} : <br/>
                            <small>{param.description}</small>
                        </label>
                        <div className="list-items-container">
                            {/* Render an input field for each item in the list */}
                            {currentList.map((item, index) => (
                                <div key={index} className="list-item-input">
                                    <input
                                        type="text"
                                        id={`${inputIdBase}_${index}`}
                                        value={item}
                                        onChange={(e) => handleUpdateListItem(paramSetter, param.name, index, e.target.value)}
                                        placeholder={`Item ${index + 1}`}
                                        className="list-item-text-input"
                                        aria-label={`${param.name} item ${index + 1}`}
                                    />
                                    {/* Show remove button only if there's more than one item */}
                                    {currentList.length > 1 && (
                                        <button
                                            type="button"
                                            onClick={() => handleRemoveListItem(paramSetter, param.name, index)}
                                            className="remove-item-button small-button"
                                            aria-label={`Remove ${param.name} item ${index + 1}`}
                                            title={`Remove item ${index + 1}`}
                                        >
                                            ×
                                        </button>
                                    )}
                                </div>
                            ))}
                        </div>
                        {/* Button to add a new empty item to the list */}
                        <button
                            type="button"
                            onClick={() => handleAddListItem(paramSetter, param.name)}
                            className="add-item-button small-button"
                        >
                            + Add Item
                        </button>
                        {/* Validation message if required and all items are empty */}
                        {!isOptional && currentList.every(item => String(item).trim() === '') && (
                            <p className="error-message small-text">At least one non-empty item is required for {param.name}.</p>
                        )}
                    </div>
                );
            }
            // --- Render Standard Input (Non-List) ---
            else {
                 // Determine the appropriate HTML input type based on the parameter type string.
                 let inputType: React.HTMLInputTypeAttribute = 'text';
                 let step: string | undefined = undefined; // For numeric inputs
                 if (param.type.includes('int')) { inputType = 'number'; step = '1'; }
                 else if (param.type.includes('float')) { inputType = 'number'; step = 'any'; }
                 else if (param.type.includes('bool')) { inputType = 'text'; } // Expect 'true' or 'false' as text input

                // Use description as placeholder text if available.
                const placeholder = param.description || '';

                return (
                    <div key={param.name} className="form-group parameter-input-group">
                        {/* Label including name, type, and required indicator */}
                        <label htmlFor={inputIdBase}>
                            {param.name} (<code>{param.type}</code>){!isOptional && <span className="required-indicator">*</span>} :
                        </label>
                        <input
                            type={inputType}
                            id={inputIdBase}
                            name={param.name}
                            value={values[param.name] ?? ''} // Use current value or empty string
                            onChange={(e) => handleSimpleParamChange(paramSetter, e)} // Use generic handler
                            placeholder={placeholder}
                            required={!isOptional} // HTML5 required attribute
                            step={step} // Set step for number inputs
                        />
                         {/* Optional help text for specific input types */}
                         {inputType === 'number' && step === 'any' && <small className="help-text"> Use decimal point (.) for fractions.</small>}
                         {param.type.includes('bool') && inputType === 'text' && <small className="help-text"> Enter 'true' or 'false'.</small>}
                    </div>
                );
            }
        });
    };

    // --- Effects ---

    /** Effect to fetch the list of available analysis recipes on component mount. */
    useEffect(() => {
        const fetchRecipes = async () => {
            setIsAnalysisLoading(true); setAnalysisError(null);
            try {
                const fetchedAnalysisRecipes = await getAnalysisRecipes();
                setAnalysisRecipes(fetchedAnalysisRecipes);
            } catch (err) { setAnalysisError(err instanceof Error ? err.message : "Failed to load analysis recipes"); }
            finally { setIsAnalysisLoading(false); }
        };
        fetchRecipes();
    }, []); // Empty dependency array ensures this runs only once on mount.

    /** Callback to fetch the list of available affiliation algorithms. Memoized with useCallback. */
     const fetchAffilAlgos = useCallback(async () => {
        setIsAffiliationLoading(true); setAffiliationError(null); setAffiliationAlgorithms([]);
        try {
            const algos = await getAffiliationAlgorithms();
            setAffiliationAlgorithms(algos);
        } catch (err) { setAffiliationError(err instanceof Error ? err.message : "Failed to load affiliation algorithms"); }
        finally { setIsAffiliationLoading(false); }
     }, []); // No dependencies, function doesn't change.

    /** Callback to fetch the list of available discovery algorithms. Memoized with useCallback. */
    const fetchDiscAlgos = useCallback(async () => {
        setIsDiscoveryAlgosLoading(true); setDiscoveryAlgosError(null); setDiscoveryAlgorithms([]);
        try {
            const algos = await getDiscoveryAlgorithms();
            setDiscoveryAlgorithms(algos);
        } catch (err) { setDiscoveryAlgosError(err instanceof Error ? err.message : "Failed to load discovery algorithms"); }
        finally { setIsDiscoveryAlgosLoading(false); }
    }, []); // No dependencies.

    /**
     * Effect to fetch affiliation and discovery algorithms when entering the 'affiliation_setup' stage.
     * Also cleans up related state when leaving this stage.
     */
    useEffect(() => {
        if (workflowStage === 'affiliation_setup') {
            // Fetch algorithms needed for this stage.
            fetchAffilAlgos();
            fetchDiscAlgos();
        } else {
            // Clean up state related to affiliation/discovery when leaving the setup stage.
            setAffiliationAlgorithms([]);
            setDiscoveryAlgorithms([]);
             setSelectedAffiliationAlgorithm(null); setAffiliationParams({});
             setSelectedDiscoveryAlgorithm(null); setDiscoveryParams({});
             setShowDiscoverySection(false); // Hide the discovery section
        }
    }, [workflowStage, fetchAffilAlgos, fetchDiscAlgos]); // Dependencies: stage and the fetch callbacks.

    /**
     * Effect to trigger institution search based on user input in the `institutionQuery` field.
     * Debounces the API call using `setTimeout`. Clears results if query is too short or institution is selected.
     */
    useEffect(() => {
        // Set up a timer to delay the search API call.
        const handler = setTimeout(async () => {
            // Only search if in the correct stage, query is long enough, and no institution is already selected.
            if (workflowStage === 'affiliation_setup' && institutionQuery.length > 1 && !selectedInstitution) {
                try {
                    // Fetch a limited number of search results.
                    const results = await searchInstitutions(institutionQuery, 0, 10);
                    setInstitutionSearchResults(results);
                } catch (err) { console.error("Institution search failed:", err); setInstitutionSearchResults([]); }
            } else {
                // Clear search results if conditions are not met.
                setInstitutionSearchResults([]);
            }
        }, 500); // 500ms debounce delay.
        // Cleanup function to clear the timeout if the query changes or component unmounts before delay ends.
        return () => clearTimeout(handler);
    }, [institutionQuery, selectedInstitution, workflowStage]); // Dependencies: trigger on query change, selection change, or stage change.

    /** Callback to fetch existing affiliation results for a given institution ID. Memoized. */
    const fetchAffiliationResults = useCallback(async (instId: number) => {
        setIsAffiliationResultsLoading(true); setAffiliationResultsError(null); setAffiliationResults([]);
        try {
            const results = await getInstitutionAffiliationResults(instId);
            setAffiliationResults(results);
        } catch (err) { setAffiliationResultsError(err instanceof Error ? err.message : "Failed to load affiliation results"); }
        finally { setIsAffiliationResultsLoading(false); }
    }, []); // No dependencies.

    /** Callback to fetch ingestion context (e.g., last keyword search time) for an institution name. Memoized. */
    const fetchContext = useCallback(async (instName: string) => {
         setIsIngestionContextLoading(true); setIngestionContextError(null); setIngestionContext(null);
         try {
             // Fetch context based on 'keyword' type and the institution name.
             const contextData = await getIngestionHistoryContext('keyword', instName);
             setIngestionContext(contextData);
         } catch (err) { setIngestionContextError(err instanceof Error ? err.message : "Failed to load ingestion context"); }
         finally { setIsIngestionContextLoading(false); }
    }, []); // No dependencies.

    /**
     * Effect to fetch affiliation results and context when an institution is selected in the affiliation setup stage.
     * Also handles resetting various states when leaving the affiliation setup stage or deselecting the institution.
     * Crucially, it avoids resetting `selectedRepositoryIds` when transitioning *to* the analysis stage.
     */
    // --- UPDATED useEffect hook (with logging comments added previously) ---
    useEffect(() => {
        // Log current state at the beginning of the effect execution.
        //console.log(`[useEffect selectedInstitution/workflowStage] Running. Stage: ${workflowStage}, Institution Selected: ${!!selectedInstitution}`);

        // Condition: Fetch data only if in affiliation setup stage AND an institution is selected.
        if (workflowStage === 'affiliation_setup' && selectedInstitution) {
            //console.log(`[useEffect selectedInstitution/workflowStage] Condition MET (Affiliation Setup + Institution). Fetching results/context for Inst ID: ${selectedInstitution.id}`);
            // Fetch existing affiliation results for the selected institution ID.
            fetchAffiliationResults(selectedInstitution.id);
            // Fetch ingestion context if the institution has a display name.
            if(selectedInstitution.display_name) {
                fetchContext(selectedInstitution.display_name);
            } else {
                // Handle case where institution name is missing.
                //console.warn("[useEffect selectedInstitution/workflowStage] Selected institution has no display name, cannot fetch context.");
                setIngestionContext(null);
                setIngestionContextError("Cannot fetch context: Institution name missing.");
            }
            // NOTE: Do NOT reset selectedRepositoryIds here. They are determined later when proceeding to analysis.
        }
        // Condition: Reset state if NOT in affiliation setup OR no institution is selected.
        else {
            //console.log(`[useEffect selectedInstitution/workflowStage] Condition NOT MET (Stage: ${workflowStage}, Inst Selected: ${!!selectedInstitution}). Running ELSE block to reset state.`);

            // Reset states related to the affiliation/discovery parts of the workflow.
            setAffiliationResults([]);
            setIngestionContext(null);
            setAffiliationResultsError(null);
            setIngestionContextError(null);
            // Reset discovery-related states.
            setShowDiscoverySection(false);
            setCandidateUrls(null);
            setSelectedUrlsToIngest({});
            setDiscoveryParams({});
            setSelectedDiscoveryAlgorithm(null);
            setIngestionProgress('');
            setIngestionResults({});

            // --- Conditional Reset for selectedRepositoryIds ---
            // Reset repository IDs ONLY IF the workflow stage is NOT 'analysis_selection'.
            // This preserves the IDs when transitioning FROM affiliation_setup TO analysis_selection,
            // but clears them if switching back to 'initial' or deselecting the institution.
            if (workflowStage !== 'analysis_selection') {
                 //console.log(`[useEffect selectedInstitution/workflowStage] ELSE block: Resetting selectedRepositoryIds because workflowStage is NOT 'analysis_selection' (it is ${workflowStage}). Current count: ${selectedRepositoryIds.length}`);
                 setSelectedRepositoryIds([]);
            } else {
                 //console.log(`[useEffect selectedInstitution/workflowStage] ELSE block: SKIPPING reset of selectedRepositoryIds because workflowStage IS 'analysis_selection'. Current count: ${selectedRepositoryIds.length}`);
            }
            // --- End CONDITIONAL Reset ---
        }
    // Disable exhaustive-deps lint rule here if dependencies are intentionally managed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedInstitution, workflowStage, fetchAffiliationResults, fetchContext]); // Dependencies: Re-run if selection, stage, or fetch callbacks change.

    // --- Memoized Calculation ---
    /**
     * Memoized calculation of affiliation results filtered by the current `confidenceThreshold`.
     * Avoids re-filtering on every render unless the underlying results or threshold change.
     */
    const filteredAffiliationResults = useMemo(() => {
        // Filter the fetched affiliation results based on the confidence score.
        return affiliationResults.filter(aff => aff.confidence_score >= confidenceThreshold);
    }, [affiliationResults, confidenceThreshold]); // Dependencies: Recalculate only if results or threshold change.

    /**
     * Initializes the parameter state object for a newly selected recipe or algorithm.
     * Sets default values (empty string for scalars, [''] for List[str]).
     * @param parameters The parameter metadata array from the selected recipe/algorithm.
     * @returns An initial `FormParams` object.
     */
    // --- Initialize Parameters Helper (REVISED - No 'default' property access) ---
    const initializeParams = (parameters: RecipeParameterMetadataResponse[] | undefined): FormParams => {
        const initialParams: FormParams = {};
        parameters?.forEach(param => {
            // Check if the parameter type is a list of strings.
            const isStringListType = (param.type.toLowerCase().includes('list[str]') || param.type.toLowerCase().includes('List[str]') || param.type.includes('[]')) && param.type.toLowerCase().includes('str');
            // Set initial value: [''] for string lists, '' for others.
            if (isStringListType) {
                initialParams[param.name] = ['']; // Default for lists is one empty input field
            } else {
                initialParams[param.name] = ''; // Default for non-lists is empty string
            }
        });
        return initialParams;
    };

    // --- Handlers ---

    /**
     * Handles the selection change for the analysis recipe dropdown.
     * Updates the selected recipe state and initializes its parameter state.
     * @param name The name of the selected recipe.
     * @param version The version of the selected recipe.
     */
    // --- UPDATED to initialize params ---
    const handleAnalysisRecipeChange = (name: string, version: string) => {
        const recipe = analysisRecipes.find(r => r.name === name && r.version === version);
        setSelectedAnalysisRecipe(recipe || null);
        // Initialize parameters based on the selected recipe's metadata.
        setAnalysisParams(initializeParams(recipe?.parameters));
        // Reset previous execution results/errors.
        setAnalysisExecutionResult(null); setAnalysisExecutionError(null);
    };

    /**
     * Handles the selection change for the affiliation algorithm dropdown.
     * Updates the selected algorithm state and initializes its parameter state.
     * @param name The name of the selected algorithm.
     * @param version The version of the selected algorithm.
     */
    const handleAffiliationAlgorithmChange = (name: string, version: string) => {
        const algo = affiliationAlgorithms.find(a => a.name === name && a.version === version);
        setSelectedAffiliationAlgorithm(algo || null);
        // Initialize parameters based on the selected algorithm's metadata.
        setAffiliationParams(initializeParams(algo?.parameters));
        // Reset previous execution results/errors.
        setAffiliationExecutionResult(null); setAffiliationExecutionError(null);
    };

     /**
     * Handles selection changes in the discovery algorithm dropdown.
     * Updates the selected algorithm, initializes parameters, and resets discovery results.
     * @param event The change event from the select element.
     */
    const handleSelectedDiscoveryAlgorithmChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        const selectedValue = event.target.value;
        // Reset discovery results when algorithm changes.
        setCandidateUrls(null); setSelectedUrlsToIngest({}); setDiscoveryError(null);

        // If no algorithm is selected (e.g., "-- Select --"), reset state.
        if (!selectedValue) {
            setSelectedDiscoveryAlgorithm(null);
            setDiscoveryParams({});
            return;
        }
        // Parse the selected value (format "name_vVersion")
        const { name, version } = parseNameVersion(selectedValue);
        if (name && version) {
            // Find the corresponding algorithm metadata.
            const algo = discoveryAlgorithms.find(a => a.name === name && a.version === version);
            setSelectedDiscoveryAlgorithm(algo || null);
            // Initialize parameters for the selected algorithm.
            setDiscoveryParams(initializeParams(algo?.parameters));
        }
    };
    // --- End Selection Handlers ---

    /**
     * Handles the execution request for the selected analysis recipe.
     * Prepares parameters using `prepareParamsForExecution`, calls the API,
     * and updates state with results or errors. Handles passing `repository_ids`
     * automatically when in the analysis selection stage.
     * @param event The form submission event object.
     */
    // --- UPDATED to use prepareParamsForExecution ---
    const handleExecuteAnalysisRecipe = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!selectedAnalysisRecipe) return; // Guard against no recipe selected

        setIsAnalysisExecuting(true);
        setAnalysisExecutionError(null);
        setAnalysisExecutionResult(null);

        // Parameters to exclude from user input (handled automatically or sensitive)
        const excludeParams = ['db_conn_str'];
        // Extra parameters to potentially add (like repo IDs from workflow)
        const extraParams: FormParams = {};
        // Check if the recipe expects 'repository_ids' parameter.
        const expectsMultipleRepos = selectedAnalysisRecipe.parameters.some(p => p.name === 'repository_ids');

        // If in the analysis stage, the recipe expects multiple repos, and we have selected IDs,
        // automatically add them to extraParams and exclude from user params.
        if (workflowStage === 'analysis_selection' && expectsMultipleRepos && selectedRepositoryIds.length > 0) {
            excludeParams.push('repository_ids', 'repository_id'); // Exclude single/plural versions
            extraParams['repository_ids'] = selectedRepositoryIds; // Add the list of IDs
        }

        // Prepare parameters, performing validation and type coercion.
        const { paramsToSend, error: prepError } = prepareParamsForExecution(
            selectedAnalysisRecipe.parameters,
            analysisParams, // Current values from state
            excludeParams,  // Params to ignore from form
            extraParams     // Params to add automatically
        );

        // If preparation failed (e.g., missing required fields), show error and stop.
        if (prepError) {
            setAnalysisExecutionError(prepError);
            setIsAnalysisExecuting(false);
            return;
        }

        try {
            //console.log("Executing analysis recipe with params:", paramsToSend);
            // Call the API to execute the recipe.
            const result = await executeAnalysisRecipe(selectedAnalysisRecipe.name, selectedAnalysisRecipe.version, paramsToSend);
            //console.log("Received analysis result:", result);
            setAnalysisExecutionResult(result); // Store the full result object
            // If the backend indicates failure, set an error message.
            if (!result.success) {
                setAnalysisExecutionError(result.error?.message ?? "Recipe execution failed with no details.");
            }
        } catch (err) {
            // Handle network or unexpected errors during the API call.
            setAnalysisExecutionError(err instanceof Error ? err.message : "An unexpected error occurred during execution.");
        } finally {
            // Ensure loading state is turned off.
            setIsAnalysisExecuting(false);
        }
    };

    /**
     * Handles the execution request for the selected affiliation algorithm.
     * Prepares parameters, calls the API with the selected institution ID,
     * and updates state. Refreshes affiliation results on successful completion.
     * @param e The form submission event object.
     */
    const handleExecuteAffiliationAlgorithm = async (e: FormEvent) => {
        e.preventDefault();
        if (!selectedAffiliationAlgorithm || !selectedInstitution) return; // Guard clauses

        setIsAffiliationExecuting(true);
        setAffiliationExecutionError(null);
        setAffiliationExecutionResult(null);

        // Prepare parameters, excluding institution_id and db_conn_str (handled by backend/API wrapper).
        const { paramsToSend, error: prepError } = prepareParamsForExecution(
            selectedAffiliationAlgorithm.parameters,
            affiliationParams,
            ['institution_id', 'db_conn_str'] // Exclude these
        );

        // If preparation failed, show error and stop.
        if (prepError) {
            setAffiliationExecutionError(prepError);
            setIsAffiliationExecuting(false);
            return;
        }

        try {
            //console.log("Executing affiliation algorithm with params:", paramsToSend);
            // Call the API to execute the algorithm for the specific institution.
            const result = await executeAffiliationAlgorithm(
                selectedAffiliationAlgorithm.name,
                selectedAffiliationAlgorithm.version,
                selectedInstitution.id,
                paramsToSend
            );
            setAffiliationExecutionResult(result); // Store the execution status result
            // Check if execution completed successfully according to the backend status.
            if (result.status !== 'COMPLETED') {
                setAffiliationExecutionError(result.message ?? "Affiliation algorithm execution did not complete successfully.");
            } else {
                // If successful, refresh the displayed affiliation results for the institution.
                fetchAffiliationResults(selectedInstitution.id);
            }
        } catch (err) {
            // Handle network or unexpected client-side errors.
            setAffiliationExecutionError(err instanceof Error ? err.message : "An unexpected client error occurred during affiliation execution.");
        } finally {
            // Ensure loading state is turned off.
            setIsAffiliationExecuting(false);
        }
    };

    /**
     * Handles the execution request for the selected discovery algorithm.
     * Prepares parameters, calls the API, and updates state with candidate URLs or errors.
     */
     const handleExecuteDiscovery = async () => {
        if (!selectedDiscoveryAlgorithm) {
            setDiscoveryError("Please select a discovery algorithm.");
            return;
        }
        setIsDiscovering(true);
        setDiscoveryError(null);
        setCandidateUrls(null); // Clear previous candidates
        setSelectedUrlsToIngest({}); // Clear selections
        setIngestionProgress('');
        setIngestionResults({});

        // Prepare parameters, excluding sensitive/backend-handled ones.
        const { paramsToSend, error: prepError } = prepareParamsForExecution(
            selectedDiscoveryAlgorithm.parameters,
            discoveryParams,
            ['db_conn_str', 'github_api_token'] // Exclude these
        );

        // If preparation failed, show error and stop.
        if (prepError) {
            setDiscoveryError(prepError);
            setIsDiscovering(false);
            return;
        }

        try {
            // Construct the request body.
            const requestBody: DiscoveryExecutionRequest = { parameters: paramsToSend };
            //console.log("Executing discovery algorithm with params:", requestBody);
            // Call the API to execute discovery.
            const urls = await executeDiscoveryAlgorithm(
                selectedDiscoveryAlgorithm.name,
                selectedDiscoveryAlgorithm.version,
                requestBody
            );
            setCandidateUrls(urls); // Store the returned candidate URLs
            // Pre-select all returned candidates for ingestion by default.
            setSelectedUrlsToIngest(urls.reduce((acc, url) => ({ ...acc, [url]: true }), {}));

        } catch (error: any) {
            // Handle errors during discovery execution.
            console.error("Discovery execution failed:", error);
            setDiscoveryError(`Failed to execute discovery algorithm: ${error.message || 'Unknown error'}`);
            setCandidateUrls([]); // Set to empty array on error
        } finally {
            // Ensure loading state is turned off.
            setIsDiscovering(false);
        }
    };
    // --- End Execution Handlers ---

    // --- Other Handlers ---

    /**
     * Handles the change event for the workflow mode toggle (checkbox).
     * Switches between 'initial' (standard) and 'affiliation_setup' stages.
     * Resets state relevant to the workflow being exited.
     * @param event The change event object from the checkbox input.
     */
    const handleWorkflowModeChange = (event: ChangeEvent<HTMLInputElement>) => {
        const checked = event.target.checked;
        // Determine the new stage based on checkbox state.
        const newStage = checked ? 'affiliation_setup' : 'initial';
        setWorkflowStage(newStage);
        // Reset state variables related to analysis, affiliation, discovery, and selections
        // to ensure a clean slate when switching modes.
        setSelectedAnalysisRecipe(null); setAnalysisParams({}); setAnalysisExecutionResult(null); setAnalysisExecutionError(null);
        setSelectedInstitution(null); setInstitutionQuery(''); setInstitutionSearchResults([]);
        setSelectedAffiliationAlgorithm(null); setAffiliationParams({}); setAffiliationResults([]); setAffiliationExecutionResult(null); setAffiliationExecutionError(null);
        setIngestionContext(null); setSelectedRepositoryIds([]); // Reset repo IDs when switching mode entirely
        setShowDiscoverySection(false); setCandidateUrls(null); setSelectedUrlsToIngest({});
        setSelectedDiscoveryAlgorithm(null); setDiscoveryParams({}); setDiscoveryError(null);
        setIngestionProgress(''); setIngestionResults({});
    };

    /**
     * Handles the selection of an institution from the search results dropdown.
     * Updates the selected institution state, sets the query input to the institution name,
     * and resets subsequent workflow states (affiliation results, context, discovery, etc.).
     * @param institution The selected `InstitutionSummary` object.
     */
    const handleSelectInstitution = (institution: InstitutionSummary) => {
        setSelectedInstitution(institution);
        // Set input field to selected institution name for display.
        setInstitutionQuery(institution.display_name ?? '');
        setInstitutionSearchResults([]); // Clear the dropdown results
        // Reset states that depend on the selected institution or subsequent steps.
        setAffiliationResults([]); setAffiliationExecutionResult(null); setAffiliationExecutionError(null);
        setIngestionContext(null); setSelectedRepositoryIds([]); setAffiliationParams({}); setSelectedAffiliationAlgorithm(null);
        setShowDiscoverySection(false); setCandidateUrls(null); setSelectedUrlsToIngest({});
        setDiscoveryParams({}); setSelectedDiscoveryAlgorithm(null);
        setIngestionProgress(''); setIngestionResults({});
    };

    /**
     * Handles the action to proceed from the affiliation setup stage to the analysis selection stage.
     * It calculates the repository IDs based on the `filteredAffiliationResults` (which respects the
     * current confidence threshold), updates the `selectedRepositoryIds` state, and changes the
     * `workflowStage` to 'analysis_selection'.
     * Includes direct filtering logic to ensure the latest threshold is used.
     */
    // --- UPDATED handleProceedToAnalysis ---
    const handleProceedToAnalysis = () => {
        //console.log("[handleProceedToAnalysis] START");
        //console.log("  - Current confidenceThreshold:", confidenceThreshold);
        //console.log("  - Current affiliationResults count:", affiliationResults.length);
        //console.log("  - Reading filteredAffiliationResults from useMemo:", filteredAffiliationResults.length);

        // --- Direct filtering to ensure the most up-to-date threshold is applied ---
        // This recalculates based on the current threshold value, avoiding potential staleness from useMemo if dependencies update slowly.
        const directlyFilteredResults = affiliationResults.filter(aff => aff.confidence_score >= confidenceThreshold);
        //console.log("  - Directly filtered results count:", directlyFilteredResults.length);
        // --- End direct filtering ---

        // Extract repository IDs from the (directly) filtered results.
        const repoIds = directlyFilteredResults.map(aff => aff.repository_id);
        //console.log("  - Calculated repoIds count (from direct filter):", repoIds.length);
        //console.log("  - Calculated repoIds (first 10):", repoIds.slice(0, 10));

        if (repoIds.length === 0) {
            // Log if proceeding with zero repositories based on the current filter.
            console.warn("[handleProceedToAnalysis] Proceeding with 0 Repository IDs based on direct filter.");
        }

        // Update the state with the list of repository IDs to be used in the analysis stage.
        //console.log("[handleProceedToAnalysis] Calling setSelectedRepositoryIds with count:", repoIds.length);
        setSelectedRepositoryIds(repoIds);

        // Change the workflow stage to trigger rendering of the analysis selection UI.
        //console.log("[handleProceedToAnalysis] Calling setWorkflowStage('analysis_selection')");
        setWorkflowStage('analysis_selection');

        //console.log("[handleProceedToAnalysis] END");
    };

    /**
     * Handles checkbox changes for selecting/deselecting candidate URLs for ingestion.
     * @param url The candidate URL being selected or deselected.
     * @param isSelected The new selection state (true if checked, false otherwise).
     */
    const handleCandidateSelectionChange = (url: string, isSelected: boolean) => {
      // Update the selection state for the specific URL.
      setSelectedUrlsToIngest(prev => ({ ...prev, [url]: isSelected }));
    };

    /**
     * Handles the action to trigger ingestion for the selected candidate URLs.
     * Iterates through selected URLs, calls the `triggerUrlIngestion` API for each,
     * and updates progress and result states.
     */
    const handleIngestSelectedCandidates = async () => {
        // Get the list of URLs currently marked as selected.
        const urlsToIngest = Object.entries(selectedUrlsToIngest)
            .filter(([_, isSelected]) => isSelected) // Filter for entries where value is true
            .map(([url]) => url); // Extract the URL (key)

        // If no URLs are selected, show a message and stop.
        if (urlsToIngest.length === 0) {
            setIngestionProgress("No URLs selected for ingestion.");
            return;
        }

        // Set loading state and initialize progress/results.
        setIsIngestingCandidates(true);
        setIngestionProgress(`Starting ingestion trigger for ${urlsToIngest.length} URLs...`);
        setIngestionResults({}); // Clear previous results

        let successCount = 0;
        const totalCount = urlsToIngest.length;
        const results: Record<string, { success: boolean; message: string }> = {}; // Store results per URL

        // Loop through each selected URL and trigger ingestion.
        for (let i = 0; i < totalCount; i++) {
            const url = urlsToIngest[i];
            // Update progress message.
            setIngestionProgress(`Triggering ${i + 1}/${totalCount}: ${url}`);
            try {
                // Call the API to trigger ingestion for the URL.
                await triggerUrlIngestion(url);
                // Record success for this URL.
                results[url] = { success: true, message: "Triggered" };
                successCount++;
                 // Optional small delay between triggers if needed.
                 await new Promise(resolve => setTimeout(resolve, 100));
            } catch (error: any) {
                // Handle errors during the trigger API call for a specific URL.
                console.error(`Error triggering ingestion for ${url}:`, error);
                // Record failure for this URL.
                results[url] = { success: false, message: `Error: ${error.message || 'Trigger failed'}` };
            }
        }

        // Update state with the final results and summary progress message.
        setIngestionResults(results);
        setIngestionProgress(`Ingestion trigger process finished. Successfully triggered: ${successCount}/${totalCount}. Monitor system status or discovery chains for actual completion.`);
        setIsIngestingCandidates(false); // Turn off loading state.
        // Optionally reset selections after triggering.
        setSelectedUrlsToIngest(urlsToIngest.reduce((acc, url) => ({ ...acc, [url]: false }), {}));
    };
    // --- End Other Handlers ---


    // --- Result Rendering ---

    /**
     * Renders the results section after an analysis recipe has been executed.
     * Handles loading and error states during execution. Parses the nested result structure
     * returned by the API and attempts to display the data appropriately (e.g., as a table
     * using `SimpleTable` or as formatted JSON for other types).
     * @returns JSX element representing the analysis results area, or null.
     */
    // --- MODIFIED renderAnalysisResults ---
    const renderAnalysisResults = () => {
        // Prepare props for loading spinner and error message components.
        const loadingProps: LoadingSpinnerProps = { message: "Executing analysis recipe..." };
        const errorProps = (msg: string): ErrorMessageProps => ({ message: msg });

        // Display loading spinner if execution is in progress.
        if (isAnalysisExecuting) return <LoadingSpinner {...loadingProps} />;
        // Display error message if execution failed before result object was set.
        if (analysisExecutionError && !analysisExecutionResult) return <ErrorMessage {...errorProps(analysisExecutionError)} />;
        // Return null if no execution has happened or result is cleared.
        if (!analysisExecutionResult) return null;

         // If the result object indicates failure, display the error message from the result.
         if (!analysisExecutionResult.success) {
             return <ErrorMessage message={analysisExecutionResult.error?.message ?? "Recipe execution failed with no details."} />;
         }
         // If execution was successful but no data field exists in the result.
         if (!analysisExecutionResult.data) {
              return <ErrorMessage message="Recipe executed successfully but returned no data." />;
         }

        // Type guard function to check if the data conforms to the expected nested structure.
        const isNestedResultData = (data: any): data is NestedResultData => {
             return typeof data === 'object' && data !== null;
        };

        // Apply the type guard to the received data.
        const nestedResult = isNestedResultData(analysisExecutionResult.data) ? analysisExecutionResult.data : null;

        // If the data doesn't match the expected nested structure, show an error and the raw data.
        if (!nestedResult) {
             console.error("Render Analysis Results: analysisExecutionResult.data is not an object", analysisExecutionResult.data);
             return (
                 <div className="results-container results-area">
                     <h4>Analysis Results</h4>
                     <ErrorMessage message="Unexpected result format received from server." />
                     <p>Raw Data:</p>
                     {/* Display raw data for debugging */}
                     <pre><code>{JSON.stringify(analysisExecutionResult.data, null, 2)}</code></pre>
                 </div>
             );
        }

        // Destructure the fields from the validated nested result data.
        const { result_type: currentResultType, data: actualData, notes } = nestedResult;
        const displayResultType = currentResultType ?? 'N/A'; // Use 'N/A' if result_type is missing

        // --- Dynamically create columns for SimpleTable if result_type is 'table' ---
        let tableColumns: TableColumn[] | null = null; // Use the imported TableColumn type
        const isTableType = currentResultType === 'table';

        if (isTableType) {
            // Check if the actual data is a non-empty array of objects.
            if (Array.isArray(actualData) && actualData.length > 0 && typeof actualData[0] === 'object' && actualData[0] !== null) {
                try {
                    // Generate table columns based on the keys of the first data row.
                    tableColumns = Object.keys(actualData[0]).map(key => ({
                        key: key, // Use the object key as the internal key
                        header: key // Use the object key as the default header text
                    }));
                } catch (e) { console.error("Render Analysis Results: Error preparing table columns:", e); }
            } else if (Array.isArray(actualData) && actualData.length === 0){
                 // Log if the table data is just an empty array.
                 //console.log("Render Analysis Results: Recipe returned an empty table.");
             } else {
                 // Warn if data type is 'table' but data is not in the expected format.
                 console.warn("Render Analysis Results: Table data received, but it's not a non-empty array of objects:", actualData);
             }
        }
        // --- End column generation ---


        // Render the results container.
        return (
            <div className="results-container results-area">
                <h4>Analysis Results</h4>
                {/* Display notes if provided by the recipe */}
                {notes && (
                    <div className="result-notes">
                        <strong>Notes from Recipe:</strong>
                        {/* Handle notes as either a single string or an array */}
                        {Array.isArray(notes) ? (
                            <ul>{notes.map((note, idx) => <li key={idx}>{note}</li>)}</ul>
                        ) : (
                            <p>{notes}</p>
                        )}
                    </div>
                 )}

                <p><strong>Result Type:</strong> {displayResultType}</p>

                {/* Display 'value' type results as formatted JSON */}
                {currentResultType === 'value' && ( <div className="result-value"><pre><code>{JSON.stringify(actualData, null, 2)}</code></pre></div> )}
                {/* Render SimpleTable if type is 'table' and columns/data are valid */}
                {/* --- Pass generated columns and actualData to SimpleTable --- */}
                {isTableType && tableColumns && actualData && ( <SimpleTable columns={tableColumns} data={actualData} /> )}
                {/* --- End SimpleTable invocation update --- */}
                {/* Handle empty table case */}
                {isTableType && !tableColumns && Array.isArray(actualData) && actualData.length === 0 && ( <p>Recipe returned an empty table (0 rows).</p> )}
                {/* Handle invalid table data format */}
                {isTableType && !tableColumns && (!Array.isArray(actualData) || actualData.length > 0) && ( <p>Recipe returned table format, but no valid data was found or data could not be processed for table display.</p> )}
                {/* Handle unknown/other result types by displaying raw data */}
                {currentResultType !== 'table' && currentResultType !== 'value' && ( <div className="result-unknown"> <p>Unknown or unhandled result type encountered ('{currentResultType}'). Displaying raw data:</p> <pre><code>{JSON.stringify(actualData ?? 'No data available', null, 2)}</code></pre> </div> )}
            </div>
        );
    };
    // --- End Modified renderAnalysisResults ---

    /**
     * Renders the table displaying filtered affiliation results for the selected institution.
     * Uses the `SimpleTable` component and handles loading, error, and empty states.
     * Filters results based on the `confidenceThreshold`.
     * @returns JSX element representing the affiliation results table section.
     */
    // Affiliation Results Table Renderer (MODIFIED to use 'columns')
    const renderAffiliationResultsTable = () => {
        const loadingProps: LoadingSpinnerProps = {};
        const errorProps = (msg: string): ErrorMessageProps => ({ message: msg });
        // Show loading spinner while fetching results.
        if (isAffiliationResultsLoading) return <LoadingSpinner {...loadingProps} />;
        // Show error message if fetching failed.
        if (affiliationResultsError) return <ErrorMessage {...errorProps(affiliationResultsError)} />;
        // Show prompt if no institution is selected yet.
        if (!selectedInstitution) return <p className="help-text">Select an institution to view results.</p>;

        // Use the memoized filtered results based on the confidence threshold.
        const displayResults = filteredAffiliationResults;

        // Message if filtering removed all results but some existed initially.
        if (displayResults.length === 0 && affiliationResults.length > 0) {
            return <p>No stored affiliation results meet the current confidence threshold ({confidenceThreshold.toFixed(2)}).</p>;
        }
        // Message if no results were fetched at all.
        else if (affiliationResults.length === 0) {
             return <p>No stored affiliation results found for this institution. You may need to run an affiliation algorithm.</p>;
        }

        // Define the columns for the SimpleTable component explicitly.
        const affilColumns: TableColumn[] = [ // Use the imported TableColumn type
            { key: 'repository_id', header: 'Repo ID' },
            { key: 'repository_name', header: 'Repository Name' },
            { key: 'confidence_score', header: 'Confidence' },
            { key: 'algorithm_name', header: 'Algorithm' },
            { key: 'algorithm_version', header: 'Version' },
            { key: 'calculated_at', header: 'Calculated' },
        ];

        // Map the affiliation result data to the format expected by SimpleTable.
        const tableData = displayResults.map(aff => ({
             repository_id: aff.repository_id,
             repository_name: aff.repository_name ?? 'N/A', // Handle potential null name
             confidence_score: aff.confidence_score.toFixed(3), // Format score
             algorithm_name: aff.algorithm_name,
             algorithm_version: aff.algorithm_version,
             calculated_at: new Date(aff.calculated_at).toLocaleDateString(), // Format date
         }));

        // Render the SimpleTable component with the defined columns and prepared data.
        return <SimpleTable columns={affilColumns} data={tableData} />;
    };

    /**
     * Renders the optional discovery section within the affiliation workflow.
     * Allows selecting and executing discovery algorithms, viewing candidate URLs,
     * selecting candidates, and triggering their ingestion.
     * @returns JSX element for the discovery section, or null if hidden.
     */
    // --- RENDER FUNCTION for Discovery Section ---
    const renderDiscoverySection = () => {
      // Only render if the section is toggled visible.
      if (!showDiscoverySection) return null;

      return (
        <div className="discovery-section workflow-section subsection-box">
          <h4>Discover More Repositories</h4>
           {/* Loading/Error states for fetching discovery algorithms */}
           {isDiscoveryAlgosLoading && <LoadingSpinner message="Loading discovery algorithms..." />}
           {discoveryAlgosError && <ErrorMessage message={discoveryAlgosError} />}
           {!isDiscoveryAlgosLoading && !discoveryAlgosError && discoveryAlgorithms.length === 0 && <p>No discovery algorithms available.</p>}
           {/* Render algorithm selection and execution UI if algorithms are loaded */}
           {!isDiscoveryAlgosLoading && !discoveryAlgosError && discoveryAlgorithms.length > 0 && (
               <>
                  {/* Dropdown to select a discovery algorithm */}
                  <div className="form-group">
                    <label htmlFor="discovery-algorithm-select">Discovery Algorithm:</label>
                    <select
                      id="discovery-algorithm-select"
                      value={selectedDiscoveryAlgorithm ? `${selectedDiscoveryAlgorithm.name}_${selectedDiscoveryAlgorithm.version}` : ""}
                      onChange={handleSelectedDiscoveryAlgorithmChange}
                      // Disable while discovery or ingestion is running
                      disabled={isDiscovering || isIngestingCandidates}
                    >
                      <option value="">-- Select Algorithm --</option>
                      {/* Populate options from fetched algorithms */}
                      {discoveryAlgorithms.map(algo => (
                        <option key={`${algo.name}_${algo.version}`} value={`${algo.name}_${algo.version}`}>
                          {algo.name} (v{algo.version}) - {algo.description}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Render parameter inputs and execution button if an algorithm is selected */}
                  {selectedDiscoveryAlgorithm && (
                    <>
                      <div className="parameter-form">
                          {/* Render parameters, excluding sensitive/backend ones */}
                          {renderParameterInputs(
                              selectedDiscoveryAlgorithm.parameters,
                              discoveryParams,
                              setDiscoveryParams, // Pass the correct state setter
                              "discovery", // ID prefix
                              ['db_conn_str', 'github_api_token'] // Excluded params
                          )}
                      </div>
                      {/* Display discovery execution errors */}
                      {discoveryError && <ErrorMessage message={`${discoveryError}`} />}
                      {/* Button to execute discovery */}
                      <button onClick={handleExecuteDiscovery} disabled={isDiscovering || isIngestingCandidates || !selectedDiscoveryAlgorithm} className="action-button">
                        {isDiscovering ? <LoadingSpinner /> : 'Find Candidate Repositories'}
                      </button>
                    </>
                  )}

                  {/* Loading indicator during discovery execution */}
                  {isDiscovering && <p><LoadingSpinner /> Searching for candidates...</p>}

                  {/* Display candidate results after discovery finishes */}
                  {candidateUrls !== null && !isDiscovering && (
                     <div className="candidate-results">
                         <h5>Candidate Repositories ({candidateUrls.length} found)</h5>
                         {/* Message if no candidates were found */}
                         {candidateUrls.length === 0 && !discoveryError && <p>No candidates found matching the criteria.</p>}
                         {/* Display list of candidates and ingestion controls if candidates exist */}
                         {candidateUrls.length > 0 && (
                            <>
                                <div className="candidate-list">
                                    {/* Map over candidate URLs to create selectable items */}
                                    {candidateUrls.map((url) => (
                                        <div key={url} className="candidate-item">
                                            <input
                                                type="checkbox"
                                                // Generate a safe ID from the URL
                                                id={`candidate-${url.replace(/[^a-zA-Z0-9-_]/g, '')}`}
                                                // Control checked state from `selectedUrlsToIngest`
                                                checked={!!selectedUrlsToIngest[url]}
                                                onChange={(e) => handleCandidateSelectionChange(url, e.target.checked)}
                                                disabled={isIngestingCandidates} // Disable during ingestion
                                            />
                                            <label htmlFor={`candidate-${url.replace(/[^a-zA-Z0-9-_]/g, '')}`}>{url}</label>
                                            {/* Display ingestion status per URL if available */}
                                            {ingestionResults[url] && (
                                                <span className={`ingestion-status ${ingestionResults[url].success ? 'success' : 'error'}`}>
                                                    {ingestionResults[url].success ? ' Triggered.' : ` Error: ${ingestionResults[url].message}`}
                                                </span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                                <p>Select repositories to trigger ingestion into MOSS.</p>
                                {/* Button to trigger ingestion for selected candidates */}
                                <button onClick={handleIngestSelectedCandidates} disabled={isIngestingCandidates || Object.values(selectedUrlsToIngest).every(v => !v)} className="action-button">
                                    {isIngestingCandidates ? <LoadingSpinner /> : `Trigger Ingestion for Selected (${Object.values(selectedUrlsToIngest).filter(v=>v).length})`}
                                </button>
                                {/* Display ingestion progress messages */}
                                {ingestionProgress && <p className="ingestion-progress">{ingestionProgress}</p>}
                                {/* Guidance text for the user */}
                                <p className="guidance-text">
                                    <strong>Guidance:</strong> After ingestion is triggered, monitor system status or discovery chains for completion.
                                    You may need to re-run the affiliation algorithm above to include the newly ingested data before proceeding.
                                </p>
                            </>
                         )}
                     </div>
                  )}
               </>
           )}
        </div> // End discovery-section
      );
    };
    // --- End Discovery Render Function ---


    // --- Render Functions for Workflow Stages ---

    /** Renders the UI components specific to the 'affiliation_setup' stage. */
    const renderAffiliationSetup = () => (
        <div className="affiliation-workflow-section">
            <h3>Affiliation Analysis Workflow</h3>
            {/* --- Step 1: Select Institution --- */}
            <div className="workflow-step">
                <h4>1. Select Institution</h4>
                 <div className="form-group institution-selector">
                    <label htmlFor="institutionQuery">Search & Select Institution:</label>
                     {/* Input field for institution search */}
                     <input type="text" id="institutionQuery" value={institutionQuery} onChange={(e) => { setInstitutionQuery(e.target.value); setSelectedInstitution(null); /* Clear selection on query change */ }} placeholder="Start typing institution name..." disabled={isAffiliationExecuting || isDiscovering || isIngestingCandidates}/>
                     {/* Display selected institution and clear button */}
                     {selectedInstitution && (<span className="selected-institution-display"> Selected: {selectedInstitution.display_name} <button type="button" onClick={() => { setSelectedInstitution(null); setInstitutionQuery(''); }} className="clear-button small-button" disabled={isAffiliationExecuting || isDiscovering || isIngestingCandidates}>(Change)</button></span>)}
                     {/* Dropdown list for search results */}
                     {institutionSearchResults.length > 0 && !selectedInstitution && ( <ul className="search-results-dropdown"> {institutionSearchResults.map(inst => (<li key={inst.id} onClick={() => handleSelectInstitution(inst)}>{inst.display_name} {inst.ror && `(${inst.ror})`}</li>))} </ul> )}
                 </div>
            </div>

            {/* Render subsequent steps only if an institution is selected */}
            {selectedInstitution && (
                <>
                    {/* --- Step 2: Review & Calculate Affiliations --- */}
                    <div className="workflow-step">
                        <h4>2. Review & Calculate Affiliations for: <em>{selectedInstitution.display_name}</em></h4>
                        {/* Display ingestion context information */}
                        <div className="context-hint">
                            {isIngestionContextLoading && <LoadingSpinner message="Loading context..." />}
                            {ingestionContextError && <ErrorMessage message={ingestionContextError} />}
                            {ingestionContext && ( <p> <small> Context: Last relevant ingestion ({ingestionContext.ingestion_type || 'N/A'}) completed: {ingestionContext.last_ingested_at ? new Date(ingestionContext.last_ingested_at).toLocaleString() : 'Never'} </small> </p> )}
                        </div>
                        {/* Display stored affiliation results */}
                        <div className="results-display subsection-box">
                            <h5>Stored Affiliation Results</h5>
                             {/* Confidence threshold slider */}
                             <div className="form-group confidence-threshold">
                                <label htmlFor="confidenceThreshold">Minimum Confidence Threshold:</label>
                                <input type="range" id="confidenceThreshold" min="0" max="1" step="0.05" value={confidenceThreshold} onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))} disabled={affiliationResults.length === 0 || isAffiliationResultsLoading || isDiscovering || isIngestingCandidates} /> <span>{confidenceThreshold.toFixed(2)}</span>
                                <p><small> Showing {filteredAffiliationResults.length} of {affiliationResults.length} total stored results matching threshold. </small></p>
                            </div>
                            {/* Render the affiliation results table */}
                            {renderAffiliationResultsTable()}
                        </div>
                         {/* Section to run/refresh affiliation algorithms */}
                        <div className="algorithm-execution subsection-box">
                            <label htmlFor="affiliationAlgorithmSelect" className="block-label">Run/Refresh Affiliation Algorithm:</label>
                            {/* Loading/Error states for fetching algorithms */}
                            {isAffiliationLoading && <LoadingSpinner message="Loading algorithms..." />}
                            {affiliationError && <ErrorMessage message={affiliationError} />}
                            {!isAffiliationLoading && affiliationAlgorithms.length === 0 && <p>No affiliation algorithms available.</p>}
                            {/* Render algorithm selection and execution form if algorithms are loaded */}
                            {!isAffiliationLoading && affiliationAlgorithms.length > 0 && (
                                <>
                                    {/* Dropdown to select affiliation algorithm */}
                                    <select id="affiliationAlgorithmSelect" value={selectedAffiliationAlgorithm ? `${selectedAffiliationAlgorithm.name}_${selectedAffiliationAlgorithm.version}` : ""} onChange={(e) => { const { name, version } = parseNameVersion(e.target.value); if (name && version) { handleAffiliationAlgorithmChange(name, version); } else { setSelectedAffiliationAlgorithm(null); setAffiliationParams({});} }} disabled={isAffiliationExecuting || isDiscovering || isIngestingCandidates}>
                                        <option value="">-- Select Algorithm --</option>
                                        {affiliationAlgorithms.map(algo => ( <option key={`${algo.name}_${algo.version}`} value={`${algo.name}_${algo.version}`}> {algo.name} v{algo.version} - {algo.description} </option> ))}
                                    </select>
                                    {/* Render parameter inputs and execution button if algorithm is selected */}
                                    {selectedAffiliationAlgorithm && (
                                        <form onSubmit={handleExecuteAffiliationAlgorithm} className="parameter-form subsection-form">
                                            <p>Parameters for {selectedAffiliationAlgorithm.name}:</p>
                                            {/* Render parameters, excluding institution_id and db_conn_str */}
                                            {renderParameterInputs(
                                                selectedAffiliationAlgorithm.parameters,
                                                affiliationParams,
                                                setAffiliationParams, // Pass correct setter
                                                "affil", // ID prefix
                                                ['institution_id', 'db_conn_str'] // Excluded params
                                            )}
                                            {/* Display affiliation execution errors */}
                                            {affiliationExecutionError && <ErrorMessage message={affiliationExecutionError} />}
                                            {/* Button to execute affiliation algorithm */}
                                            <button type="submit" disabled={isAffiliationExecuting || isDiscovering || isIngestingCandidates || !selectedAffiliationAlgorithm} className="action-button">
                                                {isAffiliationExecuting ? <LoadingSpinner /> : `Run ${selectedAffiliationAlgorithm.name}`}
                                            </button>
                                            {/* Display status message from affiliation execution */}
                                            {affiliationExecutionResult && affiliationExecutionResult.status !== 'IDLE' && <p className={`execution-status ${affiliationExecutionResult.status !== 'COMPLETED' ? 'error' : 'success'}`}>{affiliationExecutionResult.message}</p>}
                                        </form>
                                    )}
                                </>
                            )}
                        </div>
                         {/* Integration point for the discovery workflow */}
                         <div className="discovery-integration subsection-box">
                             {/* Button to toggle visibility of the discovery section */}
                             <button onClick={() => setShowDiscoverySection(prev => !prev)} className="discover-toggle-button" disabled={isAffiliationExecuting || isDiscovering || isIngestingCandidates}>
                                {showDiscoverySection ? 'Hide Discovery Section' : 'Discover More Repositories...'}
                             </button>
                             {/* Render the discovery section if toggled visible */}
                             {renderDiscoverySection()}
                         </div>
                    </div>

                    {/* --- Step 3: Proceed to Analysis --- */}
                    <div className="workflow-step">
                        <h4>3. Proceed to Analysis</h4>
                        {/* Button to transition to the analysis selection stage */}
                        <button onClick={handleProceedToAnalysis} disabled={!selectedInstitution || isAffiliationResultsLoading || filteredAffiliationResults.length === 0 || isAffiliationExecuting || isDiscovering || isIngestingCandidates} className="proceed-button">
                             {/* Display count of repositories that will be passed */}
                             Proceed to Analysis Selection ({filteredAffiliationResults.length} Repositories)
                        </button>
                        <p><small>(This will pass repositories meeting the threshold in Step 2 to the analysis step)</small></p>
                    </div>
                </>
            )}
        </div> // End affiliation-workflow-section
    );

    /** Renders the UI components specific to the 'analysis_selection' stage. */
    const renderAnalysisSelection = () => {
        // --- Log state at the START of this render function (for debugging state transitions) ---
        //console.log("[renderAnalysisSelection] Rendering...");
        //console.log("  - Current workflowStage:", workflowStage);
        //console.log("  - Current selectedRepositoryIds count:", selectedRepositoryIds.length);
         // Limit logging actual IDs if the list is very long
        //console.log("  - Current selectedRepositoryIds (first 10):", selectedRepositoryIds.slice(0, 10));
        // --- End Logging ---

        return (
            <div className="analysis-workflow-section">
                <h3>Analysis Recipe Selection</h3>
                {/* Display context: selected institution and repository count */}
                <p>Selected Institution: <strong>{selectedInstitution?.display_name ?? 'N/A'}</strong></p>
                <p>Repositories to Analyze (Confidence ≥ {confidenceThreshold.toFixed(2)}): <strong>{selectedRepositoryIds.length}</strong></p>
                {/* Button to navigate back to the previous stage */}
                <button type="button" onClick={() => setWorkflowStage('affiliation_setup')} className="back-button small-button">Back to Affiliation Setup</button>

                {/* Render content only if the stage is correctly set (redundant check, but safe) */}
                {workflowStage === 'analysis_selection' && (
                    <>
                        {/* Display error message if no repositories met the threshold */}
                        {selectedRepositoryIds.length === 0 && (
                            <ErrorMessage message="No repositories met the confidence threshold to proceed with analysis. Go back to adjust the threshold or run an affiliation algorithm." />
                        )}

                        {/* Loading/Error states for fetching analysis recipes */}
                        {isAnalysisLoading && <LoadingSpinner message="Loading recipes..." />}
                        {analysisError && <ErrorMessage message={analysisError} />}

                        {/* Message if recipes loaded but none are available (and repos were selected) */}
                        {!isAnalysisLoading && !analysisError && analysisRecipes.length === 0 && selectedRepositoryIds.length > 0 && (
                             <p>No analysis recipes found.</p>
                        )}

                        {/* Render recipe selection and execution form if recipes loaded and repositories selected */}
                        {!isAnalysisLoading && !analysisError && analysisRecipes.length > 0 && selectedRepositoryIds.length > 0 && (
                            <form onSubmit={handleExecuteAnalysisRecipe} className="subsection-box">
                                {/* Dropdown to select analysis recipe */}
                                <div className="form-group">
                                    <label htmlFor="recipeSelect">Select Analysis Recipe:</label>
                                    <select id="recipeSelect" value={selectedAnalysisRecipe ? `${selectedAnalysisRecipe.name}_${selectedAnalysisRecipe.version}` : ""} onChange={(e) => {
                                            // Parse selected value and update state
                                            const { name, version } = parseNameVersion(e.target.value);
                                            if (name && version) { handleAnalysisRecipeChange(name, version); }
                                            else { setSelectedAnalysisRecipe(null); setAnalysisParams({}); } // Reset if "-- Select --" chosen
                                        }} disabled={isAnalysisExecuting} >
                                        <option value="">-- Select Recipe --</option>
                                        {analysisRecipes.map(recipe => ( <option key={`${recipe.name}_${recipe.version}`} value={`${recipe.name}_${recipe.version}`}> {recipe.name} v{recipe.version} - {recipe.description} </option> ))}
                                    </select>
                                </div>

                                {/* Render parameters and execution button if a recipe is selected */}
                                {selectedAnalysisRecipe && ( <>
                                    <div className="parameter-form">
                                        <h4>Parameters for {selectedAnalysisRecipe.name}:</h4>
                                        {/* Immediately-invoked function to determine excluded params */}
                                        {(() => {
                                            const baseExclude = ['db_conn_str']; // Always exclude connection string
                                            // Check if the recipe expects 'repository_ids'
                                            const expectsMultipleRepos = selectedAnalysisRecipe.parameters.some(p => p.name === 'repository_ids');
                                            // If yes, and we have selected IDs, exclude 'repository_ids' and 'repository_id' from user input
                                            if (expectsMultipleRepos && selectedRepositoryIds.length > 0) {
                                                baseExclude.push('repository_ids', 'repository_id');
                                            }
                                            // Render parameter inputs with the calculated exclusions
                                            return renderParameterInputs(
                                                selectedAnalysisRecipe.parameters,
                                                analysisParams,
                                                setAnalysisParams, // Pass setter
                                                "analysis", // ID prefix
                                                baseExclude // Pass calculated excluded params
                                            );
                                        })()}
                                            {/* Informational message if repository_ids are being passed automatically */}
                                            {selectedAnalysisRecipe.parameters.some(p => p.name === 'repository_ids') && selectedRepositoryIds.length > 0 && (
                                            <p className="info-text"><small>Note: The selected {selectedRepositoryIds.length} repository IDs will be automatically passed to the 'repository_ids' parameter.</small></p>
                                            )}
                                            {/* Warning message if the recipe expects a single ID but we have multiple */}
                                            {selectedAnalysisRecipe.parameters.some(p => p.name === 'repository_id') && selectedRepositoryIds.length > 0 && (
                                                <p className="warning-text"><small>Warning: This recipe expects a single 'repository_id'. The list of {selectedRepositoryIds.length} selected IDs cannot be automatically used here. Running the recipe might fail or only process the first ID depending on its implementation.</small></p>
                                            )}
                                    </div>
                                        {/* Display analysis execution errors (only if result isn't set yet) */}
                                        {analysisExecutionError && !analysisExecutionResult && <ErrorMessage message={analysisExecutionError} />}
                                        {/* Button to execute analysis */}
                                    <button type="submit" disabled={isAnalysisExecuting || !selectedAnalysisRecipe} className="action-button">
                                        {isAnalysisExecuting ? <LoadingSpinner /> : 'Run Analysis on Selected Repositories'}
                                    </button>
                                    </> )}
                            </form>
                        )}
                    </>
                )}

                {/* Render the analysis results area */}
                {renderAnalysisResults()}
            </div> // End analysis-workflow-section
        );
    };

    /** Renders the UI components specific to the 'initial' stage (standard recipe runner). */
    const renderStandardAnalysis = () => (
        <div className="analysis-workflow-section">
             <h3>Run Standard Analysis Recipe</h3>
             {/* Loading/Error states for fetching analysis recipes */}
             {isAnalysisLoading && <LoadingSpinner message="Loading recipes..." />}
             {analysisError && <ErrorMessage message={analysisError} />}
             {!isAnalysisLoading && !analysisError && analysisRecipes.length === 0 && <p>No analysis recipes found.</p>}

             {/* Render recipe selection and execution form if recipes loaded */}
             {!isAnalysisLoading && !analysisError && analysisRecipes.length > 0 && (
                <form onSubmit={handleExecuteAnalysisRecipe} className="subsection-box">
                    {/* Dropdown to select analysis recipe */}
                    <div className="form-group">
                        <label htmlFor="recipeSelectStd">Select Analysis Recipe:</label>
                        <select id="recipeSelectStd" value={selectedAnalysisRecipe ? `${selectedAnalysisRecipe.name}_${selectedAnalysisRecipe.version}` : ""} onChange={(e) => {
                                // Parse selection and update state
                                const { name, version } = parseNameVersion(e.target.value);
                                if (name && version) { handleAnalysisRecipeChange(name, version); }
                                else { setSelectedAnalysisRecipe(null); setAnalysisParams({}); } // Reset if "-- Select --" chosen
                            }} disabled={isAnalysisExecuting} >
                            <option value="">-- Select Recipe --</option>
                            {analysisRecipes.map(recipe => ( <option key={`${recipe.name}_${recipe.version}`} value={`${recipe.name}_${recipe.version}`}> {recipe.name} v{recipe.version} - {recipe.description} </option> ))}
                        </select>
                    </div>

                    {/* Render parameters and execution button if recipe selected */}
                    {selectedAnalysisRecipe && ( <>
                        <div className="parameter-form">
                            <h4>Parameters for {selectedAnalysisRecipe.name}:</h4>
                            {/* Render parameters, excluding only the connection string */}
                            {renderParameterInputs(
                                selectedAnalysisRecipe.parameters,
                                analysisParams,
                                setAnalysisParams, // Pass setter
                                "analysisStd", // ID prefix
                                ['db_conn_str'] // Excluded params
                            )}
                        </div>
                        {/* Display analysis execution errors (only if result not set) */}
                        {analysisExecutionError && !analysisExecutionResult && <ErrorMessage message={analysisExecutionError} />}
                        {/* Button to execute analysis */}
                        <button type="submit" disabled={isAnalysisExecuting || !selectedAnalysisRecipe} className="action-button">
                            {isAnalysisExecuting ? <LoadingSpinner /> : 'Run Analysis'}
                        </button>
                     </> )}
                </form>
            )}
            {/* Render analysis results area */}
            {renderAnalysisResults()}
        </div> // End analysis-workflow-section
    );

    // --- Main Component Return ---
    return (
        <div className="shared-queries-page">
            <h2>Shared Recipes & Analysis Workflows</h2>
            {/* Workflow mode selection toggle */}
            <div className="workflow-mode-selection form-group">
                 <label className="checkbox-label">
                     <input type="checkbox" checked={workflowStage !== 'initial'} onChange={handleWorkflowModeChange}/>
                     Enable Institution-Centric Workflow (includes affiliation & discovery steps)
                 </label>
                 {/* Show button to switch back only when in workflow mode */}
                 {(workflowStage === 'affiliation_setup' || workflowStage === 'analysis_selection') && (
                     <button type="button" onClick={() => handleWorkflowModeChange({ target: { checked: false } } as ChangeEvent<HTMLInputElement>)} className="switch-workflow-button small-button"> Switch back to Standard Recipe Runner </button>
                 )}
            </div>
            <hr/>

            {/* Render the appropriate section based on the current workflowStage */}
            {workflowStage === 'initial' && renderStandardAnalysis()}
            {workflowStage === 'affiliation_setup' && renderAffiliationSetup()}
            {workflowStage === 'analysis_selection' && renderAnalysisSelection()}

        </div> // End shared-queries-page
    );
};

export default SharedQueriesPage;