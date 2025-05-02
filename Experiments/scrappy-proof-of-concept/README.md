# MOSSPOC - Map of Open Source Software, Proof of Concept

MOSSPOC is a proof of concept tool for and analyzing GitHub repositories and their associated research publications. It enables researchers and developers to discover connections between open source software repositories and academic research through DOIs (Digital Object Identifiers).

This version of MOSS serves as an initial proof of concept to demonstrate feasability of some core concepts behind MOSS. There are known bugs that may not be made into issues.

Direct development on this exact version of MOSS is paused as we refactor into a more robust architecture. Many of the core features will be preserved. Feel free to hack away, or to join our Wednesday production calls as we design and implement the future architecture.

A more comprehensive vision for MOSS can be found in the MOSS Description.

## Features

- **Repository Ingestion**: Ingest GitHub repositories individually or through keyword searches
- **DOI Extraction**: Automatically extract DOIs from repository READMEs and CITATION.cff files
- **OpenAlex Integration**: Link repositories to academic publications, authors, and institutions
- **Institution Analysis**: Discover repositories associated with specific research institutions
- **Interactive Query Mode**: Run predefined queries to analyze repository data
- **Analysis History**: Track trends and view historical analysis results

## Requirements

- Python 3.7+
- Git
- GitHub Personal Access Token
- Internet access for GitHub and OpenAlex APIs
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/moss.git
cd moss
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your configuration:
```
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_API_BASE_URL=https://api.github.com
OPENALEX_BASE_URL=https://api.openalex.org
DATABASE_URL=sqlite:///moss.db
LOG_LEVEL=INFO
```

## Configuration

### GitHub Token

You need a GitHub Personal Access Token with the following permissions:
- `repo` (Full control of private repositories)
- `read:org` (Read organization information)
- `read:user` (Read user information)

To generate a token, go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens).

### Database Configuration

By default, the application uses SQLite with the database file `moss.db`. To use a different database backend, modify the `DATABASE_URL` in your `.env` file following SQLAlchemy connection string format.

Examples:
- PostgreSQL: `postgresql://username:password@localhost/dbname`
- MySQL: `mysql://username:password@localhost/dbname`

## Usage

### Running the Application

Start the application:
```bash
python main.py
```

### Main Menu Options

The application provides several features through its main menu:

1. **Ingest a single repository**
   - Provide a GitHub repository URL to ingest data
   - Extracts DOIs and fetches associated academic works from OpenAlex

2. **Search and ingest repositories by keyword**
   - Provide keywords to search for repositories on GitHub
   - Batch ingest multiple repositories matching your criteria

3. **Run interactive query mode**
   - Apply filters to find repositories meeting specific criteria
   - Run predefined queries on repository data
   - Analyze relationships between repositories and academic works

4. **Find repositories associated with your institution**
   - Discover repositories affiliated with specific research institutions
   - Apply confidence filters to rank repository associations
   - Analyze institutional contributions to open source software

5. **View analysis history and trends**
   - Review past analyses of repository-institution associations
   - Track changes in confidence scores over time

### Example Workflow

1. Ingest a repository of interest:
```
Main Menu > Option 1 > Enter repository URL
```

2. Find all repositories related to a specific field:
```
Main Menu > Option 2 > Enter keywords (e.g., "bioinformatics, genomics")
```

3. Analyze institutional contributions:
```
Main Menu > Option 4 > Enter institution details
```

## Project Structure

```
moss/
├── clients/             # API clients for GitHub and OpenAlex
├── db/                  # Database configuration and access
├── models/              # SQLAlchemy ORM models
├── queries/             # Predefined query modules
├── services/            # Core business logic
│   ├── acf_filters/     # Association Confidence Filters
│   └── institution_analysis/ # Institution analysis components
├── utils/               # Utility functions
├── config.py            # Central configuration
└── main.py              # Application entry point
```
