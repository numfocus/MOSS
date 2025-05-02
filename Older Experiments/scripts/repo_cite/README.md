This script is very much a work in progress. Contributions are highly encouraged.

This script was developed using Large Language Models (LLMs) with extensive human design and prompting. While the code was generated through AI assistance, it was carefully crafted and guided by human expertise to align with the project's objectives. Users are encouraged to thoroughly assess and test the script to ensure it meets their specific needs and complies with all relevant policies and regulations. We disclaim any liability for errors, omissions, or any issues arising from the use of this script.

# GitHub and OpenAlex Data Collection Script

This script collects and analyzes data from GitHub repositories and the OpenAlex API. It extracts the DOI (Digital Object Identifier) from a specified GitHub repository, retrieves detailed information about the corresponding academic paper from OpenAlex, and explores the citation network to gather related papers, authors, institutions, topics, and projects. The script aims to create a comprehensive dataset for academic and research purposes.

You can explore a test visualization of this script run on [OpenFold](https://github.com/aqlaboratory/openfold) at: https://kumu.io/jstarr/omsf

**_Note:_** The test visualization is memory intensive and is likely to crash often if run on a machine with under 128gb RAM.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage Instructions](#usage-instructions)
- [Data Collection Process](#data-collection-process)
  - [DOI Extraction](#doi-extraction)
  - [Paper Details Retrieval](#paper-details-retrieval)
  - [Author and Institution Data](#author-and-institution-data)
  - [Citation Network Exploration](#citation-network-exploration)
  - [GitHub Repository Analysis](#github-repository-analysis)
- [Data Collected](#data-collected)
- [Sample Data Schema](#sample-data-schema)
- [Contributing](#contributing)

---

## Features

- **DOI Extraction**: Automatically extracts the DOI from a GitHub repository by searching for it in `CITATION.cff` and `README.md` files.
- **Paper Details Retrieval**: Fetches detailed information about the paper associated with the DOI from OpenAlex.
- **Author and Institution Data**: Processes and stores information about authors and their affiliations.
- **Topic Mapping**: Identifies and records topics (concepts) related to the papers.
- **Citation Network Exploration**: Iteratively gathers papers that cite or are cited by the original paper up to a user-defined depth.
- **GitHub Repository Analysis**: Collects comprehensive data about the repository, including contributors, issues, pull requests, languages used, and recent activity.
- **Data Output**: Saves the collected data into a structured JSON file for further analysis or integration.

---

## Installation

1. **Clone the Repository**
2. **Install Dependencies**
3. **Set Up Environment Variables**
   - Create a `.env` file in the root directory of the project.
   - Add your GitHub personal access token to the `.env` file:

     ```env
     GITHUB_TOKEN=your_personal_access_token_here
     ```

---

## Usage Instructions

1. **Run the Script**

   ```bash
   python repo_cite.py
   ```

2. **Provide User Input**

   The script will prompt you for the following information:

   - **GitHub Repository URL**: Enter the URL of the GitHub repository you want to analyze.
     ```
     Enter GitHub repository URL:
     ```

   - **Email for OpenAlex API** (optional): Provide your email address to increase API rate limits. If not set in the script, you can input it when prompted.

   - **Record Limit** (optional): Specify the number of records to retrieve per API call. Enter an integer or `'all'` to retrieve all available records.
     ```
     Enter number of records to retrieve per API call (integer or 'all') [default is 'all']:
     ```

   - **Maximum Depth for Citation Traversal** (optional): Set the maximum depth for exploring the citation network.
     ```
     Enter maximum depth for citation traversal (integer) [default is 2]:
     ```

     _**NOTE:**_ Any depth greater than 2 runs the risk of producing a file of significant size.

3. **Wait for Data Collection**

   - The script will start collecting data from GitHub and OpenAlex. This may take some time depending on the repository size and the maximum depth set for citation traversal.

4. **View Results**

   - The script will generate an output file named `output_data.json` containing the collected data.
   - If the script is interrupted, partial data will be saved to `output_data_partial.json`.

---

## Data Collection Process

### DOI Extraction

#### What It Does

The script attempts to extract the DOI from the specified GitHub repository by searching for it in:

- `CITATION.cff` file
- `README.md` file

#### How It Works

1. **Access Repository Contents**: Uses the GitHub API to list the contents of the repository.
2. **Search for `CITATION.cff`**: If found, parses the file to extract the DOI.
3. **Search in `README.md`**: If the DOI is not found in `CITATION.cff`, searches the `README.md` for DOI patterns.

#### Rationale

DOIs are often included in repositories to reference associated academic papers. Extracting the DOI allows the script to retrieve detailed paper information from OpenAlex.

---

### Paper Details Retrieval

#### What It Does

Fetches detailed information about the paper associated with the DOI from the OpenAlex API.

#### Data Retrieved

- Paper ID
- Title
- DOI
- Publication Date
- Abstract
- Authors and their affiliations
- Topics (concepts)
- References
- Citations

#### Rationale

Collecting comprehensive paper details enables analysis of the academic work related to the GitHub repository.

---

### Author and Institution Data

#### What It Does

Processes and stores information about:

- Authors
  - Names
  - ORCIDs
  - Affiliated institutions
  - Papers authored
- Institutions
  - Institution IDs
  - Names

#### Rationale

Understanding the authors and their affiliations provides insight into the academic network and potential collaborations.

---

### Citation Network Exploration

#### What It Does

Explores the citation network by:

- Iteratively gathering papers that cite or are cited by the original paper.
- Traversing up to a user-defined maximum depth.

#### How It Works

1. **Initialize Queue**: Starts with the original paper ID.
2. **BFS Traversal**: Uses a queue to perform a breadth-first search of the citation network.
3. **Process Papers**: Fetches and processes each paper, adding new citations to the queue.
4. **Avoid Duplicates**: Keeps track of visited papers to prevent processing the same paper multiple times.

#### Rationale

Exploring the citation network helps in understanding the impact and relevance of the original paper within its academic field.

---

### GitHub Repository Analysis

#### What It Does

Collects comprehensive data about the specified GitHub repository, including:

- Repository details
- Contributors
- Issues and pull requests
- Languages used
- Recent activity (past 60 days)

#### Data Retrieved

- **Repository Details**: Name, description, license, stars, forks, watchers, main language, creation date, last update, last push date.
- **Documentation Presence**: Checks for `README.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `FUNDING.yml`, `funding.json`.
- **Contributors**: Total number of contributors.
- **Issues**: Total issues, open issues, closed issues, average time to close, average time to first response.
- **Pull Requests**: Total pull requests, open and closed PRs, merged PRs, average time to merge, average time to first review, merge percentage.
- **Languages**: Languages used and their percentages.
- **Releases**: Total downloads from releases.
- **Recent Activity**: Commits, active contributors, issues opened and closed, PRs opened and merged.

#### Rationale

Analyzing the GitHub repository provides context about the project's development activity, community engagement, and open-source practices.

---

## Data Collected

Below is a table of all the data points collected by the script, along with explanations:

### From OpenAlex API

| **Data Field**       | **Description**                                                                 |
|----------------------|---------------------------------------------------------------------------------|
| `id`                 | OpenAlex ID of the paper.                                                       |
| `title`              | Title of the paper.                                                             |
| `doi`                | Digital Object Identifier of the paper.                                         |
| `publication_date`   | Date when the paper was published.                                              |
| `abstract`           | Abstract text of the paper.                                                     |
| `type`               | Type of the entity (e.g., `paper`).                                             |
| `authors`            | List of author IDs associated with the paper.                                   |
| `topics`             | List of topic IDs (concepts) related to the paper.                              |
| `cited_by`           | List of paper IDs that cite this paper.                                         |
| `references`         | List of paper IDs that this paper references.                                   |
| `people`             | List of author dictionaries with their details.                                 |
| `institutions`       | List of institution dictionaries with their details.                            |
| `topics`             | List of topic dictionaries with their details.                                  |

### From GitHub API

| **Data Field**                      | **Description**                                                                                       |
|-------------------------------------|-------------------------------------------------------------------------------------------------------|
| `name`                              | Name of the repository.                                                                               |
| `description`                       | Description of the repository.                                                                        |
| `license`                           | License under which the repository is distributed.                                                    |
| `stars`                             | Number of stars the repository has received.                                                          |
| `forks`                             | Number of times the repository has been forked.                                                       |
| `watchers`                          | Number of users watching the repository.                                                              |
| `main_language`                     | Primary programming language used in the repository.                                                  |
| `created_at`                        | Creation date of the repository.                                                                      |
| `updated_at`                        | Last update date of the repository.                                                                   |
| `pushed_at`                         | Date when the repository was last pushed to.                                                          |
| `has_readme`                        | Boolean indicating if the repository contains a `README.md` file.                                     |
| `has_code_of_conduct`               | Boolean indicating if the repository contains a `CODE_OF_CONDUCT.md` file.                            |
| `documentation_files`               | Dictionary indicating the presence of documentation files like `CITATION.cff`, `CONTRIBUTING.md`, etc. |
| `num_contributors`                  | Total number of contributors to the repository.                                                       |
| `total_issues`                      | Total number of issues in the repository.                                                             |
| `open_issues`                       | Number of open issues.                                                                                |
| `closed_issues`                     | Number of closed issues.                                                                              |
| `avg_time_to_close_issues`          | Average time (in hours) to close issues.                                                              |
| `avg_time_to_first_response_issue`  | Average time (in hours) to receive the first response on issues.                                      |
| `total_pull_requests`               | Total number of pull requests in the repository.                                                      |
| `open_pull_requests`                | Number of open pull requests.                                                                         |
| `closed_pull_requests`              | Number of closed pull requests.                                                                       |
| `merged_pull_requests`              | Number of merged pull requests.                                                                       |
| `avg_time_to_merge_pr`              | Average time (in hours) to merge pull requests.                                                       |
| `avg_time_to_first_review_pr`       | Average time (in hours) to receive the first review on pull requests.                                 |
| `pr_merge_percentage`               | Percentage of pull requests that were merged.                                                         |
| `languages`                         | Dictionary of programming languages used and their byte counts.                                       |
| `language_percentages`              | Dictionary of programming languages and their usage percentages.                                      |
| `total_downloads`                   | Total number of downloads from releases.                                                              |
| `recent_commits`                    | Number of commits made in the recent time window (past 60 days).                                      |
| `recent_active_contributors`        | Number of contributors active in the recent time window.                                              |
| `recent_issues_opened`              | Number of issues opened in the recent time window.                                                    |
| `recent_issues_closed`              | Number of issues closed in the recent time window.                                                    |
| `recent_pulls_opened`               | Number of pull requests opened in the recent time window.                                             |
| `recent_pulls_merged`               | Number of pull requests merged in the recent time window.                                             |
| `url`                               | URL of the GitHub repository.                                                                         |

---

## Sample Data Schema

Below is a sample of the data structure generated by the script, containing one example of each entity: **Project**, **Paper**, **Person**, **Topic**, and **Institution**.

### Project

```json
{
  "name": "example-repo",
  "description": "An example GitHub repository.",
  "license": "MIT",
  "stars": 42,
  "forks": 10,
  "watchers": 5,
  "main_language": "Python",
  "created_at": "2021-01-01T00:00:00Z",
  "updated_at": "2021-06-01T00:00:00Z",
  "pushed_at": "2021-05-31T00:00:00Z",
  "has_readme": true,
  "has_code_of_conduct": false,
  "documentation_files": {
    "CITATION.cff": true,
    "CONTRIBUTING.md": false,
    "GOVERNANCE.md": false,
    "FUNDING.yml": false,
    "funding.json": false
  },
  "num_contributors": 3,
  "total_issues": 15,
  "open_issues": 5,
  "closed_issues": 10,
  "avg_time_to_close_issues": 48.0,
  "avg_time_to_first_response_issue": 12.0,
  "total_pull_requests": 8,
  "open_pull_requests": 2,
  "closed_pull_requests": 6,
  "merged_pull_requests": 4,
  "avg_time_to_merge_pr": 36.0,
  "avg_time_to_first_review_pr": 24.0,
  "pr_merge_percentage": 50.0,
  "languages": {
    "Python": 50000,
    "JavaScript": 15000
  },
  "language_percentages": {
    "Python": 76.92,
    "JavaScript": 23.08
  },
  "total_downloads": 1200,
  "recent_commits": 25,
  "recent_active_contributors": 2,
  "recent_issues_opened": 4,
  "recent_issues_closed": 6,
  "recent_pulls_opened": 3,
  "recent_pulls_merged": 2,
  "url": "https://github.com/example-user/example-repo"
}
```

### Paper

```json
{
  "id": "https://openalex.org/W1234567890",
  "title": "An Example Research Paper",
  "doi": "10.1234/example.doi",
  "publication_date": "2020-12-15",
  "abstract": "This is an example abstract of a research paper.",
  "type": "paper",
  "authors": [
    "https://openalex.org/A123456789",
    "https://openalex.org/A987654321"
  ],
  "topics": [
    "https://openalex.org/C123456789",
    "https://openalex.org/C987654321"
  ],
  "cited_by": [
    "https://openalex.org/W0987654321"
  ],
  "references": [
    "https://openalex.org/W1122334455",
    "https://openalex.org/W5566778899"
  ]
}
```

### Person

```json
{
  "id": "https://openalex.org/A123456789",
  "name": "Dr. Jane Smith",
  "orcid": "https://orcid.org/0000-0001-2345-6789",
  "affiliations": [
    "https://openalex.org/I123456789"
  ],
  "type": "person",
  "papers_authored": [
    "https://openalex.org/W1234567890",
    "https://openalex.org/W0987654321"
  ]
}
```

### Topic

```json
{
  "id": "https://openalex.org/C123456789",
  "name": "Artificial Intelligence",
  "type": "topic"
}
```

### Institution

```json
{
  "id": "https://openalex.org/I123456789",
  "name": "Example University",
  "type": "institution"
}
```

---

## Contributing

Contributions are highly encouraged! Please follow these steps:

1. **Fork the Repository**
2. **Create a Feature Branch**
3. **Make Changes and Commit**
4. **Push to Your Branch**
5. **Open a Pull Request**

---

Feel free to reach out or create an issue if you have any questions or need assistance with using the script.

Contact: jon@numfocus.org
