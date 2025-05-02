This script is very much a work in progress. Contributions are highly encourged.

This script was developed using Large Language Models (LLMs) with extensive human design and prompting. While the code was generated through AI assistance, it was carefully crafted and guided by human expertise to align with the project's objectives. Users are encouraged to thoroughly assess and test the script to ensure it meets their specific needs and complies with all relevant policies and regulations. We disclaim any liability for errors, omissions, or any issues arising from the use of this script.

# University Repository Analysis Script

This script analyzes GitHub repositories associated with a university or keyword. It helps identify repositories affiliated with the university or keyword, evaluates their activity levels, and categorizes them based on various metrics. The script is designed to assist universities in discovering and assessing open source projects developed by their students, faculty, or associated organizations.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage Instructions](#usage-instructions)
- [Scoring System Breakdown](#scoring-system-breakdown)
  - [Association Score](#association-score)
  - [Confidence Score](#confidence-score)
  - [Activity Score](#activity-score)
- [Data Collected](#data-collected)
- [Contributing](#contributing)

---

## Features

- **Search GitHub Repositories**: Searches for repositories using university-specific queries.
- **Analyze Repository Content**: Evaluates repositories for affiliation, activity, and content type.
- **Contributor Analysis**: Examines contributor profiles for university affiliation.
- **Activity Metrics**: Calculates metrics like commits, issues, pull requests, and more.
- **Categorization**: Classifies repositories as Class Projects, Research Projects, Syllabi, or Others.
- **Keyword Matching**: Uses hierarchical keywords from the open alex ontology to determine the domain, field, subfield, and topic.
- **Output**: Generates JSON and CSV files containing analysis.

---

## Installation

1. **Clone the Repository**
2. **Install Dependencies**
3. **Set Up GitHub Authentication**

   - Create a `.env` file in the project root directory.
   - Add your GitHub token to the `.env` file:

     ```env
     GITHUB_TOKEN=your_github_token_here
     ```
---

## Usage Instructions

1. **Run the Script**

   ```bash
   python script_name.py
   ```

2. **Provide User Input**

   The script will prompt you for the following information:

   - **University Name**: (e.g., "University of California, Santa Cruz")
   - **University Acronym**: (e.g., "UCSC")
   - **University Email Domain**: (e.g., "ucsc.edu")
   - **University Website URL**: (e.g., "ucsc.edu")
   - **Additional Queries**: You can add extra search queries or enter 'n' to proceed.
   - **Activity Metric Choice**:
     - Press `1` for the default OSSci Activity Metric.
     - Press `2` to customize your own activity metric weights and time window.

3. **Customize Activity Metrics (Optional)**

   If you choose to set your own activity metric:

   - **Time Window**: Enter the number of months to look back for activity data.
   - **Assign Weights**: Distribute 100% among the available metrics as per your preference.

4. **Limit Processing (Optional)**

   - You can limit the number of repositories to process by using the `--limit` or `-l` flag:

     ```bash
     python script_name.py --limit 10
     ```

5. **View Results**

   - The script will generate two output files:
     - `repository_data_<UNIVERSITY_ACRONYM>.json`
     - `repository_data_<UNIVERSITY_ACRONYM>.csv`
   - These files contain detailed analysis of the repositories.

---

## Scoring System Breakdown

### Association Score

#### What It Represents

The **Association Score** measures the direct relevance of a repository to the university based on the number of search queries it matches. It reflects how many of the predefined search criteria a repository satisfies.

#### How It's Calculated

- **Formula**: `Association Score = Number of Matching Queries`

- **Explanation**: We define a set of search queries that include the university's name, acronym, email domain, and any additional keywords. Each repository is checked against these queries.

- **Calculation Steps**:
  1. **Define Search Queries**: For example:
     - `"University of Example" in:name,description,readme`
     - `"UOE" in:name,description,readme`
     - `"uoe.edu" in:email`
     - Additional user-defined queries
  2. **Search Repositories**: Use GitHub's API to find repositories matching these queries.
  3. **Count Matches**: For each repository, count how many queries it matches.
  4. **Assign Score**: The total number of matching queries becomes the Association Score.

#### Rationale

A higher Association Score indicates a stronger association with the university, as the repository matches more of the university-specific criteria.

---

### Confidence Score

#### What It Represents

The **Confidence Score** estimates the likelihood that a repository is affiliated with the university. It considers various indicators such as mentions of the university in the repository's content, ownership by university organizations, and contributions from university-affiliated individuals.

#### How It's Calculated

- **Formula**: `Confidence Score = (Total Points / 500) * 100`, capped at 100%

- **Explanation**: Points are awarded based on the presence of university identifiers in different parts of the repository and contributor profiles. The total points are normalized to a percentage to obtain the Confidence Score.

- **Calculation Steps**:
  1. **Define University Identifiers**: These include:
     - University name (e.g., "University of Example")
     - University acronym (e.g., "UOE")
     - University email domain (e.g., "uoe.edu")
     - University website URL (e.g., "uoe.edu")
  2. **Assign Point Values**:
     - Repository name and description: 20 points per identifier
     - Repository topics/tags: 20 points per identifier
     - README content: 20 points per identifier
     - Owner's profile (if user): 20 points per identifier
     - Owner's organization details (if organization): 30 points per identifier
     - Contributors' emails: 15 points per match
     - Contributors' profiles: 10 points per match
     - Affiliated repositories of contributors: 5 points per repository
  3. **Search for Identifiers**:
     - **In Repository**:
       - Name and description
       - Topics/tags
       - README content
     - **In Owner Details**:
       - If organization, check organization's name, description, blog, email, and location
       - If user, check user's bio
     - **In Contributors**:
       - Email domains
       - Bio content
       - Affiliation indicators in their other repositories
  4. **Calculate Total Points**: Sum all points from the above steps.
  5. **Normalize Score**: Convert total points to a percentage:
     - `Confidence Score = (Total Points / 500) * 100`
     - Cap the score at 100%

#### Example Calculation

Suppose a repository has the following:

- Repository name mentions "University of Example": +20 points
- README mentions "UOE": +20 points
- Owned by an organization with "uoe.edu" in its email: +30 points
- Two contributors with emails ending in "@uoe.edu": +15 points each
- Total Points: 20 + 20 + 30 + 15 + 15 = 100 points
- Confidence Score: (100 / 500) * 100 = 20%

#### Rationale

The Confidence Score aggregates multiple affiliation signals to provide a probabilistic measure of the repository's connection to the university. Normalizing the score ensures comparability across repositories.

---

### Activity Score

#### What It Represents

The **Activity Score** evaluates the repository's recent development and community engagement. It considers various metrics such as commits, issues, pull requests, and contributor activity within a specified time window.

#### How It's Calculated

- **Formula**:

  ```
  Activity Score = Σ (Normalized Metric Score × Metric Weight)
  ```

  The final score is normalized between 1 and 100.

- **Metrics and Weights**:

  | Metric                             | Default (OSSci) Weight (%) |
  |------------------------------------|--------------------|
  | Recent Commits Count               | 20                 |
  | Active Contributors Count          | 15                 |
  | Recent Issues Opened Count         | 10                 |
  | Recent Issues Closed Count         | 10                 |
  | Average Time to Close Issues       | 5                  |
  | Recent PRs Opened Count            | 10                 |
  | Recent PRs Merged Count            | 10                 |
  | Average Time to Merge PRs          | 5                  |
  | Growth in Stars                    | 5                  |
  | Growth in Forks                    | 5                  |
  | Recent Releases Count              | 5                  |
  | Total Downloads in Time Window     | 5                  |
  | Discussion Activity Count          | 0                  |
  | **Total**                          | **100%**           |

- **Normalization of Metrics**:
  - For metrics where **higher is better**:
    - `Normalized Score = min((Actual Value / Maximum Value), 1) × 100`
  - For metrics where **lower is better** (e.g., average times):
    - `Normalized Score = max(((Maximum Value - Actual Value) / Maximum Value), 0) × 100`

- **Maximum Values for Normalization** (Adjustable):

  | Metric                       | Maximum Value |
  |------------------------------|---------------|
  | Recent Commits Count         | 500           |
  | Active Contributors Count    | 50            |
  | Recent Issues Opened Count   | 100           |
  | Recent Issues Closed Count   | 100           |
  | Average Time to Close Issues | 24 hours      |
  | Recent PRs Opened Count      | 100           |
  | Recent PRs Merged Count      | 100           |
  | Average Time to Merge PRs    | 24 hours      |
  | Growth in Stars              | 1,000         |
  | Growth in Forks              | 500           |
  | Recent Releases Count        | 20            |
  | Total Downloads              | 10,000        |
  | Discussion Activity Count    | 500           |

- **Calculation Steps**:
  1. **Collect Metrics**: Gather activity data within the specified time window (default is 6 months).
  2. **Normalize Each Metric**:
     - Use the formulas above to convert actual values into normalized scores between 0 and 100.
  3. **Apply Weights**:
     - Multiply each normalized score by its corresponding weight.
  4. **Sum Weighted Scores**:
     - Add up all weighted scores to get the preliminary Activity Score.
  5. **Normalize Final Score**:
     - Ensure the Activity Score is between 1 and 100.

#### Example Calculation

Suppose we have the following metrics:

- Recent Commits: 250 (out of 500)
- Active Contributors: 25 (out of 50)
- Recent Issues Opened: 50 (out of 100)
- Recent Issues Closed: 50 (out of 100)
- Average Time to Close Issues: 12 hours (max is 24 hours)
- Recent PRs Opened: 50 (out of 100)
- Recent PRs Merged: 50 (out of 100)
- Average Time to Merge PRs: 12 hours (max is 24 hours)
- Stars Growth: 500 (out of 1,000)
- Forks Growth: 250 (out of 500)
- Recent Releases: 10 (out of 20)
- Total Downloads: 5,000 (out of 10,000)
- Discussion Activity: 250 (out of 500)

**Normalization**:

- Recent Commits Normalized Score: (250 / 500) × 100 = 50
- Active Contributors Normalized Score: (25 / 50) × 100 = 50
- Average Time to Close Issues Normalized Score: ((24 - 12) / 24) × 100 = 50

**Applying Weights**:

- Recent Commits Weighted Score: 50 × 0.20 = 10
- Active Contributors Weighted Score: 50 × 0.15 = 7.5
- Average Time to Close Issues Weighted Score: 50 × 0.05 = 2.5

**Summing Weighted Scores**:

- Total Activity Score = 10 + 7.5 + 2.5 + ... (continue for all metrics)

**Final Score**:

- Sum all weighted scores to get the Activity Score.
- Ensure the score is between 1 and 100.

#### Rationale

The Activity Score provides a composite measure of the repository's vitality and community engagement. By normalizing metrics and applying weights, we ensure that the score reflects both the quantity and quality of activity.

#### Customization

- **Time Window**: Users can adjust the time window for recent activity (e.g., last 3 months, 12 months).
- **Weights**: Users can customize the weights assigned to each metric based on their priorities.

---

## Data Collected

Below is a table of all the data points collected by the script, along with explanations:

| **Data Field**                  | **Description**                                                                                                                                                    |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `repo_number`                   | The index number of the repository in the processing sequence.                                                                                                     |
| `full_name`                     | The full name of the repository (`owner/repo_name`).                                                                                                               |
| `description`                   | The description of the repository provided by the owner.                                                                                                           |
| `domain`                        | The primary domain/category determined from hierarchical keyword matching.                                                                                        |
| `field`                         | The specific field within the domain, based on keyword analysis.                                                                                                   |
| `subfield`                      | The subfield within the field, derived from hierarchical keywords.                                                                                                 |
| `topic`                         | The specific topic within the subfield.                                                                                                                            |
| `matched_keywords`              | List of keywords from the hierarchical dataset that matched the repository content.                                                                                |
| `hierarchical_scores`           | JSON string of scores calculated for domains, fields, subfields, and topics based on keyword matches.                                                              |
| `project_type`                  | Categorization of the repository (e.g., Class Project, Research Project, Syllabus, Other).                                                                         |
| `project_type_scores`           | Scores for each project type category based on keyword matches.                                                                                                    |
| `project_type_matches`          | Specific keywords that matched for each project type category.                                                                                                     |
| `is_scientific`                 | Boolean indicating if the repository is related to scientific research based on keyword analysis.                                                                  |
| `license`                       | The software license under which the repository is distributed.                                                                                                    |
| `last_commit_date`              | The date of the most recent commit to the repository.                                                                                                              |
| `has_readme`                    | Boolean indicating if the repository contains a README file.                                                                                                       |
| `has_code_of_conduct`           | Boolean indicating if the repository contains a Code of Conduct.                                                                                                   |
| `citation.cff`                  | Boolean indicating if the repository contains a `citation.cff` file.                                                                                               |
| `CONTRIBUTING.md`               | Boolean indicating if the repository contains a `CONTRIBUTING.md` file.                                                                                            |
| `GOVERNANCE.md`                 | Boolean indicating if the repository contains a `GOVERNANCE.md` file.                                                                                              |
| `FUNDING.yml`                   | Boolean indicating if the repository contains a `FUNDING.yml` file.                                                                                                |
| `funding.json`                  | Boolean indicating if the repository contains a `funding.json` file.                                                                                               |
| `lead_institution`              | The institution most frequently affiliated with the contributors.                                                                                                  |
| `external_impact`               | Number of contributors not affiliated with the university.                                                                                                         |
| `contributors_count`            | Total number of contributors to the repository.                                                                                                                    |
| `association_score`             | Number of search queries the repository matched, indicating its association with the university.                                                                   |
| `confidence_score`              | Percentage score estimating the likelihood of the repository's affiliation with the university.                                                                    |
| `confidence_matches`            | Details of the matches found for calculating the confidence score.                                                                                                 |
| `queries`                       | List of search queries that the repository matched.                                                                                                                |
| `total_issues`                  | Total number of issues in the repository.                                                                                                                          |
| `open_issues`                   | Number of open issues.                                                                                                                                            |
| `closed_issues`                 | Number of closed issues.                                                                                                                                           |
| `average_time_to_close`         | Average time (in days) it takes to close issues.                                                                                                                   |
| `issue_update_frequency`        | Average number of days between issue updates.                                                                                                                      |
| `external_participants_count`   | Number of external participants (not affiliated with the university) in issue discussions.                                                                         |
| `external_participants`         | List of usernames of external participants.                                                                                                                        |
| `total_prs`                     | Total number of pull requests in the repository.                                                                                                                   |
| `open_prs`                      | Number of open pull requests.                                                                                                                                      |
| `closed_prs`                    | Number of closed pull requests.                                                                                                                                    |
| `average_time_to_merge`         | Average time (in days) it takes to merge pull requests.                                                                                                            |
| `pr_update_frequency`           | Average number of days between pull request updates.                                                                                                               |
| `average_time_to_first_review`  | Average time (in days) to receive the first review on pull requests.                                                                                               |
| `review_to_merge_percentage`    | Percentage of reviewed pull requests that were merged.                                                                                                             |
| `main_language`                 | The primary programming language used in the repository.                                                                                                           |
| `languages_percentages`         | Percentage breakdown of programming languages used.                                                                                                                |
| `stars_count`                   | Number of stars the repository has received.                                                                                                                       |
| `forks_count`                   | Number of times the repository has been forked.                                                                                                                    |
| `watchers_count`                | Number of users watching the repository.                                                                                                                           |
| `open_issues_count`             | Number of open issues (duplicate of `open_issues`, can be consolidated).                                                                                           |
| `total_downloads`               | Total number of downloads across all releases.                                                                                                                     |
| `activity_score`                | Calculated activity score based on recent repository activity.                                                                                                     |
| `recent_commits_count`          | Number of commits made in the recent time window.                                                                                                                  |
| `active_contributors_count`     | Number of contributors active in the recent time window.                                                                                                           |
| `recent_issues_opened_count`    | Number of issues opened in the recent time window.                                                                                                                 |
| `recent_issues_closed_count`    | Number of issues closed in the recent time window.                                                                                                                 |
| `avg_issue_close_time`          | Average time (in hours) to close issues in the recent time window.                                                                                                 |
| `recent_prs_opened_count`       | Number of pull requests opened in the recent time window.                                                                                                          |
| `recent_prs_merged_count`       | Number of pull requests merged in the recent time window.                                                                                                          |
| `avg_pr_merge_time`             | Average time (in hours) to merge pull requests in the recent time window.                                                                                          |
| `stars_growth`                  | Growth in the number of stars in the recent time window (proxy as current total due to API limitations).                                                           |
| `forks_growth`                  | Growth in the number of forks in the recent time window (proxy as current total due to API limitations).                                                           |
| `recent_releases_count`         | Number of releases published in the recent time window.                                                                                                            |
| `total_downloads_recent`        | Total number of downloads in the recent time window.                                                                                                               |
| `discussion_activity_count`     | Total number of comments on issues and pull requests in the recent time window.                                                                                    |

---

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the Repository**
2. **Create a Feature Branch**
3. **Make Changes and Commit**
4. **Push to the Branch**
5. **Open a Pull Request**

---

Feel free to reach out or create an issue if you have any questions or need assistance with using the script.

Contact: jon@numfocus.org
