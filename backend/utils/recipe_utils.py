# --- START OF FILE recipe_utils.py ---
"""
backend.utils.recipe_utils
--------------------------

Provides utilities for discovering and managing executable "recipe" scripts
within the MOSS project structure.

Recipes are external Python scripts (typically found in the 'contrib' directory)
that perform specific tasks like custom data analysis queries or affiliation
calculations. This module includes functions to:

- Define data structures for holding recipe metadata (name, version, description, parameters).
- Scan specified directories for valid recipe files based on naming conventions.
- Parse recipe files using Abstract Syntax Trees (AST) to extract metadata
  from function docstrings without executing the files directly.
- Manage paths and constants related to recipe locations.
"""

import os
import ast # Abstract Syntax Trees module for parsing Python code structure.
import logging
import re # Regular expressions for filename and docstring parsing.
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Setup logger for this module.
logger = logging.getLogger(__name__)

# Define the project root directory based on this file's location.
# Assumes this file is in backend/utils.
PROJECT_ROOT_UTIL = Path(__file__).resolve().parent.parent.parent

# Define standard locations for contributed recipe scripts, relative to the project root.
# These constants provide centralized access points for recipe discovery functions.
CONTRIB_DIR = PROJECT_ROOT_UTIL / "contrib"
CONTRIB_QUERIES_DIR = CONTRIB_DIR / "queries"                   # Directory for analysis query recipes.
CONTRIB_AFFILIATION_ALGOS_DIR = CONTRIB_DIR / "affiliation_algorithms" # Directory for affiliation algorithm recipes.
# Add other recipe directories here as needed (e.g., CONTRIB_DISCOVERY_ALGOS_DIR).


# --- Metadata Structures ---

class RecipeParameterMetadata:
    """
    Represents metadata for a single parameter expected by a recipe function.

    Stores the parameter's name, its type hint (as a string), and a human-readable
    description, typically extracted from the recipe function's docstring.
    """
    def __init__(self, name: str, type_hint: str, description: str):
        self.name = name                # Parameter name.
        self.type = type_hint           # String representation of the type hint (e.g., 'str', 'int', 'Dict[str, Any]').
        self.description = description  # Description of the parameter's purpose.

    def to_dict(self) -> Dict[str, str]:
        """Serializes the parameter metadata into a dictionary format."""
        return {"name": self.name, "type": self.type, "description": self.description}

class RecipeMetadata:
    """
    Represents metadata for a discovered recipe script.

    Holds information about a recipe, including its name, version, description,
    expected parameters, and its file path relative to the project root. This
    object encapsulates the information needed to display and execute a recipe.
    """
    def __init__(self, name: str, version: str, description: str, parameters: List[RecipeParameterMetadata], file_path: str):
        self.name = name                # Base name of the recipe (extracted from filename).
        self.version = version          # Version string (e.g., 'v1', 'v1.2', extracted from filename).
        self.description = description  # Description of the recipe's purpose (from docstring).
        self.parameters = parameters    # List of required parameters (from docstring).
        # Store the file path using forward slashes for cross-platform consistency.
        self.file_path = str(Path(file_path)).replace("\\", "/") # Relative path from project root.

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the recipe metadata into a dictionary, suitable for API responses."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters], # Serialize parameter list.
            "file_path": self.file_path, # Include relative path for backend lookup during execution.
        }

# --- Helper Functions ---

def _parse_docstring(docstring: Optional[str]) -> Tuple[str, List[RecipeParameterMetadata]]:
    """
    Parses a function docstring adhering to a specific format to extract metadata.

    The expected format is:
    1.  First line: A concise description of the function's purpose.
    2.  Blank line (optional).
    3.  "Params:" section marker.
    4.  Parameter lines: "- param_name: type_hint (description)" for each parameter.

    Args:
        docstring: The docstring string obtained from a function node using `ast.get_docstring`.

    Returns:
        A tuple containing:
        - The extracted description string.
        - A list of `RecipeParameterMetadata` objects representing the parsed parameters.
        Returns default values ("No description provided.", []) if the docstring is empty or None.
    """
    if not docstring:
        return "No description provided.", []

    lines = [line.strip() for line in docstring.strip().split('\n')]
    description = lines[0] if lines else "No description provided."
    parameters: List[RecipeParameterMetadata] = []
    param_section_found = False

    # Iterate through lines after the description.
    for line in lines[1:]:
        line_lower = line.lower().strip()
        if line_lower == "params:":
            param_section_found = True
            continue # Move to the next line after finding "Params:"

        # If inside the params section and the line starts with '-', attempt to parse it.
        if param_section_found and line.startswith("-"):
            # Regex to capture name, type hint, and description within parentheses.
            # Allows for complex type hints (e.g., List[str], Optional[Dict[str, int]]).
            match = re.match(r"-\s*(\w+)\s*:\s*([\w\s.\[\],]+)\s*\((.+)\)", line, re.IGNORECASE)
            if match:
                name, type_hint, desc = match.groups()
                parameters.append(RecipeParameterMetadata(name.strip(), type_hint.strip(), desc.strip()))
            else:
                 # Log a warning if a line in the params section doesn't match the expected format.
                 logger.warning(f"Could not parse recipe parameter line format: '{line}'")
        elif param_section_found and (line_lower.startswith("returns:") or line_lower.startswith("yields:")):
            # Stop parsing parameters if a 'Returns:' or 'Yields:' section is encountered.
            break
        elif param_section_found and not line:
            # Allow blank lines within the parameter section.
            pass

    return description, parameters


# --- Core Discovery Function ---

def discover_recipes(
    recipes_base_dir: Path,
    target_function_name: str = "run_analysis"
) -> List[RecipeMetadata]:
    """
    Scans a specified directory for Python files matching the recipe naming
    convention and extracts metadata using AST parsing.

    Identifies potential recipe files by looking for filenames ending in '_vX.py'
    (e.g., 'my_query_v1.py', 'affiliation_model_v2.1.py'). It then parses
    these files to find a specific function (defined by `target_function_name`)
    and extracts metadata (description, parameters) from its docstring.

    Args:
        recipes_base_dir: The absolute path to the directory to scan for recipe files.
                          This should typically be one of the `CONTRIB_*` directories.
        target_function_name: The exact name of the function within the recipe script
                              that contains the main logic and metadata docstring
                              (e.g., 'run_analysis', 'calculate_affiliations').

    Returns:
        A list of `RecipeMetadata` objects, one for each successfully discovered
        and parsed recipe. Returns an empty list if the directory doesn't exist
        or no valid recipes are found.
    """
    recipes: List[RecipeMetadata] = []
    if not recipes_base_dir.is_dir():
        logger.warning(f"Recipe discovery skipped: Directory not found or is not a directory: {recipes_base_dir}")
        return recipes

    logger.info(f"Scanning for recipes with target function '{target_function_name}' in: {recipes_base_dir}")

    # Iterate through Python files in the specified directory matching the version pattern.
    for file_path in recipes_base_dir.glob("*_v*.py"):
        if not file_path.is_file():
            continue # Skip directories or other non-file items.

        # Use regex to extract the base name and version string from the filename.
        # Expects format: 'name_v1.py', 'name_v1.0.py', etc.
        match = re.match(r"(.+)_v(\d+(?:\.\d+)*)\.py", file_path.name)
        if not match:
            # Skip files that don't match the naming convention (might be helper modules).
            logger.debug(f"Skipping file (does not match recipe naming convention '_vX.py'): {file_path.name}")
            continue

        recipe_name, numeric_version_part = match.groups() # e.g., 'my_query', '1.0'
        full_version_string = f"v{numeric_version_part}" # Prepend 'v' -> 'v1.0'

        logger.debug(f"Processing potential recipe file: {file_path.name}")
        try:
            # Read the source code of the potential recipe file.
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            # Parse the source code into an Abstract Syntax Tree (AST).
            tree = ast.parse(source_code)

            # Traverse the AST to find the definition of the target function.
            func_node = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == target_function_name:
                    func_node = node
                    break # Found the target function, no need to search further.

            if func_node:
                # Extract the docstring from the found function node.
                docstring = ast.get_docstring(func_node)
                # Parse the docstring to get description and parameters.
                description, parameters = _parse_docstring(docstring)

                # Calculate the file path relative to the project root for storage.
                try:
                    relative_path = file_path.relative_to(PROJECT_ROOT_UTIL)
                except ValueError:
                    # This occurs if the file path is somehow outside the project root.
                    logger.error(f"Recipe file {file_path} appears outside the project root {PROJECT_ROOT_UTIL}. Storing absolute path as fallback.")
                    relative_path = file_path # Use absolute path in this edge case.

                # Create and append the RecipeMetadata object.
                recipes.append(RecipeMetadata(
                    name=recipe_name.replace('_', ' ').title(), # Format name nicely
                    version=full_version_string,
                    description=description,
                    parameters=parameters,
                    file_path=str(relative_path) # Store relative path as string.
                ))
                logger.debug(f"Successfully parsed metadata for recipe '{recipe_name}' version '{full_version_string}' (Function: {target_function_name})")
            else:
                 # Log if a file matches the naming convention but lacks the target function.
                 logger.debug(f"No function named '{target_function_name}' found in {file_path.name}, skipping metadata extraction.")

        except FileNotFoundError:
            # Should not happen within the loop but handle defensively.
            logger.error(f"File not found during recipe processing: {file_path}")
        except SyntaxError as e:
            logger.error(f"Syntax error parsing recipe file {file_path}: {e}")
        except Exception as e:
            # Catch any other unexpected errors during file processing or AST parsing.
            logger.exception(f"Unexpected error processing recipe file {file_path}")

    logger.info(f"Discovered {len(recipes)} recipes with target function '{target_function_name}' in {recipes_base_dir}")
    return recipes
# --- END OF FILE recipe_utils.py ---