import pytest
from repo_cite import (
    process_paper_data,
    PAPERS_DICT,
    AUTHORS_DICT,
    INSTITUTIONS_DICT,
    TOPICS_DICT,
)

# Sample paper data mimicking an OpenAlex response.
sample_paper_data = {
    "id": "https://openalex.org/W123456789",
    "title": "Test Paper Title",
    "doi": "10.1234/testdoi",
    "publication_date": "2020-01-01",
    "abstract_inverted_index": {
        "Test": [1],
        "paper": [2],
        "abstract": [3]
    },
    "concepts": [
        {"id": "C1", "display_name": "Concept 1"}
    ],
    "authorships": [
        {
            "author": {"id": "A1", "display_name": "Author One", "orcid": "0000-0001-2345-6789"},
            "institutions": [
                {"id": "I1", "display_name": "Institution One"}
            ]
        }
    ],
    "referenced_works": ["https://openalex.org/W987654321"]
}

@pytest.fixture(autouse=True)
def clear_globals():
    """Ensure global dictionaries are cleared before each test."""
    PAPERS_DICT.clear()
    AUTHORS_DICT.clear()
    INSTITUTIONS_DICT.clear()
    TOPICS_DICT.clear()
    yield

def test_process_paper_data():
    process_paper_data(sample_paper_data)
    
    # Verify that the paper is added to the global PAPERS_DICT.
    assert sample_paper_data["id"] in PAPERS_DICT
    paper_node = PAPERS_DICT[sample_paper_data["id"]]
    assert paper_node["title"] == "Test Paper Title"
    
    # The abstract_inverted_index should be converted to a space‐delimited abstract.
    expected_abstract = "Test paper abstract"
    assert paper_node["abstract"] == expected_abstract
    
    # Check that topics are processed.
    assert "C1" in paper_node["topics"]
    assert "C1" in TOPICS_DICT
    topic_node = TOPICS_DICT["C1"]
    assert topic_node["name"] == "Concept 1"
    
    # Check that authors and institutions have been added.
    assert "A1" in AUTHORS_DICT
    author_node = AUTHORS_DICT["A1"]
    assert "I1" in author_node["affiliations"]
    assert "I1" in INSTITUTIONS_DICT
    
    # Check that referenced works are captured.
    assert "https://openalex.org/W987654321" in paper_node["references"]
