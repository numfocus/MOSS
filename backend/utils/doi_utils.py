# --- START OF FILE doi_utils.py ---
"""
backend.utils.doi_utils
-----------------------

Provides utility functions for working with Digital Object Identifiers (DOIs).

Includes functions for:
- Extracting potential DOI strings from arbitrary text using regular expressions.
- Performing a basic format validation check on a string to see if it resembles a DOI.
"""

import re
from typing import List

# --- Regular Expressions for DOI Handling ---

# DOI_REGEX: A comprehensive regex designed to find DOIs within larger text blocks.
# Key features:
# - Looks for the mandatory '10.' prefix followed by the publisher prefix (4+ digits).
# - Captures the suffix, allowing a wide range of characters typically found in DOIs.
# - Includes non-capturing groups for optional common prefixes (like 'doi:', 'http://doi.org/')
#   to avoid including them in the extracted DOI string itself.
# - Attempts to handle context (like surrounding parentheses or URLs) and avoid capturing
#   common trailing punctuation that isn't part of the DOI.
# - Uses verbose mode (`re.VERBOSE`) for readability and ignores case (`re.IGNORECASE`).
DOI_REGEX = re.compile(
    r"""
    # Optional, non-capturing prefix group: handles common URI schemes and prefixes.
    (?:
        doi: |                             # Matches "doi:" literal
        https?://(?:dx\.)?doi\.org/      # Matches "http(s)://doi.org/" or "http(s)://dx.doi.org/"
    )?
    # Main capturing group for the core DOI string:
    (
        10\.\d{4,9}       # DOI prefix: "10." followed by 4 to 9 digits.
        /                 # Separator between prefix and suffix.
        # Suffix: Allows a broad range of characters commonly found in DOIs.
        # Includes letters, numbers, and symbols like '-', '.', '_', ';', '(', ')', ':', '/'.
        [-._;()/:A-Za-z0-9]+
    )
    # Note: This regex aims for broad capture. Post-processing (stripping trailing chars)
    # is used below to refine the results, as lookaheads can become overly complex
    # and might still miss edge cases or exclude valid characters at the end of a DOI.
    """,
    re.VERBOSE | re.IGNORECASE
)

# SIMPLE_DOI_FORMAT_CHECK: A simpler regex for basic format validation.
# Checks if a string starts with '10.' + 4-9 digits + '/' + at least one character.
# This is NOT exhaustive validation but serves as a quick sanity check. It does not
# guarantee the DOI exists or resolves.
SIMPLE_DOI_FORMAT_CHECK = re.compile(r"^10\.\d{4,9}/.+")


# --- DOI Utility Functions ---

def extract_dois_from_text(text: str) -> List[str]:
    """
    Extracts potential DOI strings from a given block of text using DOI_REGEX.

    The function finds all matches for the DOI pattern and then performs basic
    cleanup by removing common trailing punctuation characters (.,;)]>}) that might
    have been inadvertently captured or are adjacent to the DOI in the source text.
    It returns a list of unique, cleaned DOI strings found.

    Args:
        text: The input string potentially containing DOIs (e.g., README content,
              publication abstracts).

    Returns:
        A sorted list of unique potential DOI strings found in the text,
        with basic trailing punctuation removed. Returns an empty list if
        no potential DOIs are found or if the input text is empty.
    """
    if not text:
        return []

    # Find all potential DOI strings matching the core pattern.
    potential_dois = DOI_REGEX.findall(text)

    # Clean up extracted strings and ensure uniqueness.
    cleaned_dois = set()
    for doi in potential_dois:
        # Iteratively remove trailing punctuation unlikely to be part of the DOI.
        cleaned = doi
        # Define characters to strip from the end.
        # Parentheses, brackets, and angle brackets are sometimes part of DOIs,
        # but often they are part of the surrounding text (e.g., citations).
        # This cleanup favors removing them if they appear at the very end.
        chars_to_strip = '.,;)]}>'
        while cleaned and cleaned[-1] in chars_to_strip:
            cleaned = cleaned[:-1]

        # Add the cleaned DOI to the set if it's not empty after stripping.
        if cleaned:
             # Optional enhancement: Validate format using is_valid_doi_format here?
             # if is_valid_doi_format(cleaned):
             #     cleaned_dois.add(cleaned)
             cleaned_dois.add(cleaned) # Add regardless of strict format for now

    # Return the unique DOIs as a sorted list.
    return sorted(list(cleaned_dois))


def is_valid_doi_format(doi: str) -> bool:
    """
    Performs a basic structural check to see if a string looks like a DOI.

    Uses the SIMPLE_DOI_FORMAT_CHECK regex. This function only checks if the
    string starts with the characteristic '10.prefix/suffix' structure.
    It does *not* verify if the DOI actually exists or can be resolved via
    services like doi.org.

    Args:
        doi: The string to validate.

    Returns:
        True if the string matches the basic DOI format pattern, False otherwise.
    """
    if not doi:
        return False
    # Check if the regex matches the beginning of the string.
    return bool(SIMPLE_DOI_FORMAT_CHECK.match(doi))


# --- Example Usage & Basic Tests ---
# This block executes only when the script is run directly (e.g., python -m backend.utils.doi_utils).
# It provides a simple demonstration and test cases for the functions above.
if __name__ == "__main__":
    test_text = """
    This text includes various DOI formats for testing extraction.
    A standard DOI: 10.1000/xyz123.
    Another one in parentheses (10.1234/abc-def).
    A DOI presented as a URL: https://doi.org/10.5678/gh.ijk, check it out.
    Prefixed with 'doi:': doi:10.9999/lm/no.
    Inside a Markdown link: [link](https://doi.org/10.1111/j.1467-9280.2008.02189.x).
    A complex DOI with punctuation: 10.1016/j.cell.2020.01.014; followed by text.
    DOIs ending with punctuation to test cleanup: 10.1234/endchar., 10.5678/endchar]; 10.9876/endchar)>
    Invalid formats: 9.1000/abc or 10.123/def or just 10.
    URL containing a DOI-like string not at the start: http://example.com/page_with_doi_10.1101/2020.03.19.998019_in_path.
    Not a doi: 123.456/789
    Duplicate: 10.1000/xyz123
    Case variation: DOI:10.5555/TeStInG
    """
    print("--- Testing DOI Extraction ---")
    extracted = extract_dois_from_text(test_text)
    print("Extracted DOIs:")
    if extracted:
        for d in extracted:
            # Also show format validity for each extracted DOI.
            print(f"- {d} (Valid format: {is_valid_doi_format(d)})")
    else:
        print("No DOIs extracted.")

    print("\n--- Testing Format Validation ---")
    test_dois = [
        "10.1000/xyz123",
        "10.123456789/suffix",
        "10.1016/j.cell.2020.01.014",
        "10.123/abc", # Invalid prefix length
        "9.9999/abc", # Invalid start
        "doi:10.1101/12345", # Should be False as it checks the string itself
        "",
        None,
    ]
    for doi_str in test_dois:
        print(f"'{doi_str}': {is_valid_doi_format(str(doi_str))}")
# --- END OF FILE doi_utils.py ---