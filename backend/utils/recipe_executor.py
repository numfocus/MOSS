# --- START OF FILE recipe_executor.py ---
"""
backend.utils.recipe_executor
-----------------------------

Provides a mechanism for executing external Python "recipe" scripts in a secure,
isolated subprocess.

This utility is designed to run user-contributed or dynamically loaded scripts
(e.g., for custom analysis queries or affiliation algorithms) without directly
importing them into the main application process. It handles passing parameters,
database connection strings, and secrets securely, captures output, manages
timeouts, and returns structured results or error information.
"""
import sys
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Setup logger for this module.
logger = logging.getLogger(__name__)

# --- Path Configuration ---
# Determine key paths relative to this file's location for executing the helper script.
_current_dir = Path(__file__).parent
# Assumes this file is in backend/utils, so navigate up two levels for project root.
_project_root = _current_dir.parent.parent
# Path to the intermediary script responsible for loading and running the actual recipe.
_run_script_path = _project_root / "scripts" / "run_recipe_script.py"

# Path to the Python interpreter running the current (main) process.
# This ensures the subprocess uses the same Python environment.
_python_executable = sys.executable

def execute_recipe(
    recipe_path_relative: str,
    recipe_params: Dict[str, Any],
    db_conn_str: str,
    timeout: int = 60,
    script_type: str = "analysis",
    function_name: str = "run_analysis",
    secrets: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Executes a specified recipe Python script in an isolated subprocess.

    Constructs a command line to invoke `scripts/run_recipe_script.py`, passing
    the target recipe's path, parameters (as JSON), database connection string,
    and optional secrets. It captures stdout/stderr, handles timeouts, and parses
    the JSON output from the runner script.

    Args:
        recipe_path_relative: The path to the target recipe script, relative
                              to the project root directory.
        recipe_params: A dictionary containing parameters to be passed to the
                       target function within the recipe script. Must be JSON-serializable.
        db_conn_str: The database connection string for the recipe script to use.
                     Passed securely via command line arguments to the runner script.
        timeout: The maximum allowed execution time for the subprocess in seconds.
                 Defaults to 60 seconds.
        script_type: A string identifying the type or category of the recipe being run
                     (e.g., 'analysis', 'affiliation', 'discovery'). Used for context/logging.
        function_name: The specific function name within the target recipe script
                       that should be executed by the runner.
        secrets: An optional dictionary containing sensitive key-value pairs (e.g., API keys)
                 to be passed securely to the recipe script. Values are masked in logs.

    Returns:
        A dictionary containing the execution result.
        On success: `{"success": True, "data": <recipe_output>}`
        On failure: `{"success": False, "error": {"error": "<ErrorType>", "message": "<details>"}}`
        Possible error types include FileNotFoundError, ParameterSerializationError,
        ExecutionError, TimeoutError, OutputFormatError, OutputDecodeError, SubprocessError.
    """
    # Resolve the absolute path to the target recipe script.
    absolute_recipe_path = _project_root / recipe_path_relative

    # Validate that the recipe script file exists.
    if not absolute_recipe_path.is_file():
        error_msg = f"Recipe script file not found at resolved path: {absolute_recipe_path}"
        logger.error(error_msg)
        return {"success": False, "error": {"error": "FileNotFoundError", "message": f"Recipe script not found: {recipe_path_relative}"}}

    # Serialize the parameters dictionary into a JSON string.
    try:
        params_json = json.dumps(recipe_params)
    except (TypeError, OverflowError) as e:
        # Handle potential errors during JSON serialization (e.g., non-serializable types).
        error_msg = f"Could not serialize recipe parameters to JSON: {e}"
        logger.error(error_msg)
        return {"success": False, "error": {"error": "ParameterSerializationError", "message": f"Could not serialize parameters: {e}"}}

    # --- Construct the Subprocess Command ---
    # Base command includes the Python interpreter, the runner script path,
    # and arguments for the recipe module path, parameters, connection string, etc.
    command = [
        _python_executable,
        str(_run_script_path),
        "--module-path", str(absolute_recipe_path),
        "--params-json", params_json,
        "--db-conn-str", db_conn_str,
        "--script-type", script_type,
        "--function-name", function_name,
    ]

    # Append secret arguments securely if provided.
    # Each key and value is passed as a separate argument pair.
    log_secrets_display = [] # Used for constructing a masked version for logging.
    if secrets:
        for key, value in secrets.items():
            # Append actual key and value to the command list.
            command.extend([f"--secret-key", key, f"--secret-value", value])
            # Append key and masked value for logging purposes.
            log_secrets_display.extend([f"--secret-key", key, f"--secret-value", "[SECRET]"])

    # --- Log Execution Attempt (Masking Sensitive Data) ---
    # Create a version of the command for logging where sensitive information
    # (parameters JSON, DB connection string, secret values) is masked.
    log_command_display = [
        _python_executable,
        str(_run_script_path),
        "--module-path", str(absolute_recipe_path),
        "--params-json", "[PARAMS_JSON]", # Mask serialized parameters.
        "--db-conn-str", "[DB_CONN_STR]", # Mask database connection string.
        "--script-type", script_type,
        "--function-name", function_name,
    ]
    if log_secrets_display:
        log_command_display.extend(log_secrets_display) # Append masked secrets.

    logger.info(f"Executing recipe via subprocess: {' '.join(log_command_display)}")

    # --- Execute the Subprocess ---
    try:
        result = subprocess.run(
            command,
            capture_output=True,    # Capture stdout and stderr streams.
            text=True,              # Decode stdout/stderr as text (UTF-8 by default).
            check=False,            # Do not raise CalledProcessError on non-zero exit codes (handle manually).
            timeout=timeout,        # Set the execution timeout.
            encoding='utf-8',       # Explicitly specify UTF-8 encoding.
            # Security Consideration: Review environment variables passed. By default,
            # the subprocess inherits the parent's environment. Limit if necessary.
            # env=os.environ.copy() # Example: pass current environment (review security).
        )

        # --- Process Subprocess Results ---
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""

        # Log any output from the runner script's stderr stream.
        if stderr:
            logger.warning(f"Recipe runner stderr ({recipe_path_relative}):\n{stderr}")

        # Check the return code of the runner script.
        if result.returncode != 0:
            logger.error(f"Recipe runner script exited with non-zero code: {result.returncode} for {recipe_path_relative}")
            # Attempt to parse stdout for a structured JSON error message from the runner script.
            try:
                error_json = json.loads(stdout)
                # Check if it matches the expected failure structure.
                if isinstance(error_json, dict) and error_json.get("success") is False:
                    logger.error(f"Recipe execution failed (reported by runner): {error_json.get('error', {})}")
                    return error_json # Return the detailed error from the runner.
            except json.JSONDecodeError:
                # If stdout is not JSON, log the raw output (truncated).
                logger.error(f"Recipe runner stdout was not valid JSON error output: {stdout[:500]}...")

            # Return a generic execution error if JSON parsing failed or structure was wrong.
            return {"success": False, "error": {"error": "ExecutionError", "message": f"Script exited with code {result.returncode}. Stderr: {stderr[:500]}...", "script_path": recipe_path_relative}}

        # If return code is 0, proceed assuming success.
        # Attempt to parse the standard output as the JSON result from the recipe.
        try:
            result_json = json.loads(stdout)
            # Validate the basic structure of the successful response.
            if isinstance(result_json, dict) and "success" in result_json:
                if result_json["success"] is True:
                    # Successful execution reported by the runner.
                    logger.info(f"Recipe execution successful: {recipe_path_relative}")
                    return result_json # Return the structured result.
                else:
                    # Handle edge case: runner exited 0 but reported "success": false.
                    logger.error(f"Recipe runner ({recipe_path_relative}) exited 0 but reported success=False: {result_json.get('error', 'No error details provided')}")
                    return result_json # Return the structured error from the runner.
            else:
                 # Runner exited 0, but output format doesn't match expected structure.
                 logger.error(f"Recipe runner ({recipe_path_relative}) exited 0 but output unexpected JSON structure: {stdout[:500]}...")
                 return {"success": False, "error": {"error": "OutputFormatError", "message": "Script exited successfully but output was not in expected format.", "output": stdout[:500]}}

        except json.JSONDecodeError as e:
            # Failed to decode the expected JSON result from stdout.
            logger.error(f"Failed to decode JSON result from recipe runner stdout ({recipe_path_relative}): {e}. Output: {stdout[:500]}...")
            return {"success": False, "error": {"error": "OutputDecodeError", "message": f"Could not decode script output as JSON: {e}", "output": stdout[:500]}}

    # --- Handle Subprocess Exceptions ---
    except subprocess.TimeoutExpired:
        # Subprocess execution exceeded the specified timeout.
        logger.error(f"Recipe execution timed out after {timeout}s: {recipe_path_relative}")
        return {"success": False, "error": {"error": "TimeoutError", "message": f"Execution timed out after {timeout} seconds."}}
    except Exception as e:
        # Catch any other unexpected errors during subprocess management.
        logger.exception(f"Unexpected error running recipe subprocess for {recipe_path_relative}")
        return {"success": False, "error": {"error": "SubprocessError", "message": f"Unexpected error launching or managing subprocess: {e}"}}
# --- END OF FILE recipe_executor.py ---