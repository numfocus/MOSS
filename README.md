# MOSS - Map of Open Source Science

[License: Apache v2](http://www.apache.org/licenses/)

## Overview

MOSS (Map of Open Source Science) is a backend application designed to build a knowledge graph about open source scientific software. It ingests data about repositories (primarily from GitHub), links them to scholarly works (using DOIs and OpenAlex), identifies contributors and institutions, and provides an API to query these relationships. It also supports running custom analysis and discovery algorithms ("recipes").

The system uses a FastAPI web framework for its API, PostgreSQL as the database, Celery for background task processing (like keyword-based discovery and DOI processing), and Redis as the message broker for Celery.

## Key Features

* **Data Ingestion:**
  * Ingest GitHub repositories via direct URL.
  * Discover and ingest repositories based on keyword searches (asynchronous).
* **Scholarly Linking:**
  * Extracts DOIs from repository files (e.g., README).
  * Resolves DOIs and fetches metadata from OpenAlex.
  * Processes citation networks (references and citations).
* **Entity Tracking:**
  * Stores detailed information about Repositories, Owners (Users/Orgs), Contributors.
  * Stores Scholarly Works, Persons (Authors), Institutions.
  * Tracks affiliations between authors and institutions.
  * Tracks dependencies listed in common package files (`requirements.txt`, `package.json`).
  * Tracks GitHub Issues, Pull Requests, and associated comments.
* **Provenance:** Uses a `DiscoveryChain` system to track how data was found and linked.
* **Extensibility:** Supports custom "recipes" for:
  * Affiliation detection between repositories and institutions.
  * Data analysis queries.
  * Repository discovery algorithms.
* **API:** Provides a RESTful API (built with FastAPI) for interacting with the ingested data and triggering processes.

## Technology Stack

* **Backend:** Python + uvicorn + FastAPI
* **Frontend:** Node + React (Vite)
* **Package Managers:** uv + pnpm
* **Database:** PostgreSQL
* **Background Tasks:** Celery
* **Message Broker / Cache:** Redis

* **ORM:** SQLAlchemy
* **Migrations:** Alembic
* **HTTP Client:** Requests
* **Logging:** Python `logging`, `concurrent-log-handler`
* **Configuration:** `python-dotenv`
* **API Clients:** Custom clients for GitHub API v3 and OpenAlex API
* **Analysis (Optional):** NetworkX, python-louvain

## Prerequisites

 Before you begin, ensure you have the following installed on your system:

 1. **Python:** Version 3.13 or higher. [Download Python](https://www.python.org/downloads/)
 2. **uv:** Python's package installer. [uv - Installation](https://docs.astral.sh/uv/getting-started/installation/)
 3. **Git:** For cloning the repository. [Download Git](https://git-scm.com/downloads)
 4. **Node.js and pnpm:** For the frontend. Download Node.js (LTS recommended). pnpm can be installed via various methods. pnpm - Installation
 5. **Docker and Docker Compose:** (Recommended for simplified setup of PostgreSQL and Redis). Install Docker and Docker Compose.
 6. **Alternatively, for manual setup of services:**
    * **PostgreSQL:** Version 12+ recommended. Download PostgreSQL
    * **Redis:** Download Redis

## Setup Instructions

Follow these steps carefully to set up the MOSS backend application:

1. **Clone the Repository:**
    Open your terminal or command prompt and run:

    ```sh
    git clone https://github.com/numfocus/MOSS/
    cd MOSS/
    ```

2. **Install uv**
    As described here: [uv - Installation](https://docs.astral.sh/uv/getting-started/installation/)

    ```sh
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    ```pwsh
    winget install --id=astral-sh.uv  -e
    ```

3. **Install pnpm**
    As described here: [pnpm - Installation](https://pnpm.io/installation)

    ```sh
    curl -fsSL https://get.pnpm.io/install.sh | sh -
    ```

    ```pwsh
    winget install -e --id pnpm.pnpm
    ```

4. **Create a Virtual Environment**:
    Use uv to install setup virtual environment.

    ```sh
    uv python install 3.13 # Install python 
    uv venv # create virtual environment in current folder
    ```

5. **Activate the Virtual Environment:**
    * **On macOS/Linux:**

        ```sh
        source .venv/bin/activate
        ```

    * **On Windows:**

        ```pwsh
        venv\Scripts\activate.bat
        ```

    *(Your terminal prompt should change to indicate the active environment, e.g., `(venv)`).*

6. **Install Dependencies:**
    Install all the required Python packages listed in `pyproject.toml`:

    ```sh
    uv sync
    ```

7. **Configure Environment Variables (`.env` file):**
    * Copy the example environment file:

        ```sh
        cp .env.example .env
        ```

    * **Edit the `.env` file** using a text editor and fill in the required values:
        * **PostgreSQL Configuration (for Docker Compose & App):**
            * `POSTGRES_USER`: Username for PostgreSQL (e.g., `moss_user`). Used by Docker Compose to create the user.
            * `POSTGRES_PASSWORD`: Password for the PostgreSQL user. Used by Docker Compose.
            * `POSTGRES_DB`: Database name (e.g., `moss_db`). Used by Docker Compose to create the database.
            * `POSTGRES_HOST`: Hostname for PostgreSQL (e.g., `localhost` when connecting from your app to the Docker container via mapped port).
            * `POSTGRES_PORT`: Port for PostgreSQL (e.g., `5432`). Used by Docker Compose to map the port.
        * **Redis Configuration (for Docker Compose & App):**
            * `REDIS_HOST`: Hostname for Redis (e.g., `localhost` when connecting from your app to the Docker container via mapped port).
            * `REDIS_PORT`: Port for Redis (e.g., `6379`). Used by Docker Compose to map the port.
        * **Application Connection URLs (used by the Python application):**
            * `DATABASE_URL`: Full connection string for PostgreSQL, used by SQLAlchemy.
                * Example: `postgresql://moss_user:your_secure_password@localhost:5432/moss_db`
                * This URL should be consistent with the `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, and `POSTGRES_PORT` variables.
            * `CELERY_BROKER_URL`: Full URL for your Redis server, used by Celery for task queuing.
                * Example: `redis://localhost:6379/0` (using Redis database 0).
                * This URL should be consistent with `REDIS_HOST` and `REDIS_PORT`.
            * `CELERY_RESULT_BACKEND_URL`: Full URL for your Redis server, used by Celery for storing task results.
                * Example: `redis://localhost:6379/1` (using Redis database 1).
                * This URL should be consistent with `REDIS_HOST` and `REDIS_PORT`.
        * `GITHUB_API_TOKEN`: Your GitHub Personal Access Token (PAT).
            * This is needed to interact with the GitHub API (fetching repository info, etc.).
            * Generate one at: [https://github.com/settings/tokens](https://github.com/settings/tokens) (use "Tokens classic").
            * Grant the `public_repo` scope for read-only access to public repositories. Keep this token secure!
            * Example: `ghp_YourGitHubTokenHere`
        * `OPENALEX_EMAIL`: Your email address.
            * Used for the OpenAlex API "polite pool" for potentially better rate limits. See OpenAlex documentation.
            * Example: `your.email@example.com`
        * `VITE_API_BASE_URL`: URL for the backend API, used by the frontend.
            * Default: `http://localhost:8000/api/v1`.

8. **Set Up PostgreSQL and Redis Services:**

    **Option 1: Using Docker (Recommended)**
    This is the simplest way to get PostgreSQL and Redis running. Ensure Docker and Docker Compose are installed.
    A `docker-compose.yml` file is provided in the project root. It uses the `POSTGRES_*` and `REDIS_*` variables from your `.env` file to configure the services.
    Start the services in detached mode:

    ```sh
    docker-compose up -d
    ```

    This will automatically create the PostgreSQL database and user specified in your `.env` file.
    To stop the services: `docker-compose down`

    **Option 2: Manual Setup**
    If you prefer to manage PostgreSQL and Redis manually:

    **PostgreSQL:**
    * Ensure your PostgreSQL server is running.
    * Connect to your PostgreSQL server (e.g., using `psql` or a GUI tool).
    * Create the database (use the name from `POSTGRES_DB` in `.env`):

        ```sh
        createdb your_db_name # Example: createdb moss_db
        ```

        Or using SQL: `CREATE DATABASE your_db_name;`
    * Create a user and grant privileges (use credentials from `POSTGRES_USER` and `POSTGRES_PASSWORD` in `.env`):

        ```sql
        CREATE USER your_user WITH PASSWORD 'your_password';
        GRANT ALL PRIVILEGES ON DATABASE your_db_name TO your_user;
        -- Optional: ALTER DATABASE your_db_name OWNER TO your_user;
        ```

    * *(**Note:** Adjust commands based on your PostgreSQL setup and security practices.)*

    **Redis:**
    * Ensure your Redis server is running and accessible on the host and port specified in `REDIS_HOST` and `REDIS_PORT` in your `.env` file.

9. **Run Database Migrations:**
    This step creates all the necessary tables in your database based on the application's models. We use Alembic, managed via a script.

    ```sh
    python scripts/setup_db.py
    ```

    *(You should see output indicating migrations are being applied. If this fails, double-check your `.env` configuration and ensure PostgreSQL is running and accessible.)*

10. **Install node and frontent dependencies:**
    Install all the required node packages listed in `package.json`:

    ```sh
    cd frontend/
    pnpm env use --global 24
    pnpm install
    ```

## Running the Application

The application consists of two main parts that need to run concurrently: the **API Server** and the **Celery Workers**. You will typically run these in separate terminal windows (make sure the virtual environment is activated in each).

1. **Start the API Server (FastAPI with Uvicorn):**
    This makes the REST API available.

    ```sh
    ur run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
    ```

    * `backend.main:app`: Tells Uvicorn where to find the FastAPI app instance.
    * `--reload`: Automatically restarts the server when code changes (useful for development). Remove this flag in production.
    * `--host 0.0.0.0`: Makes the server accessible from other devices on your network (not just `localhost`).
    * `--port 8000`: Specifies the port the server will listen on.
    * You should see output indicating the server is running, often including `Application startup complete.`
    * You can access the API documentation at `http://localhost:8000/docs` in your browser.

2. **Start the Celery Workers:**
    These processes handle background tasks like keyword discovery and DOI processing. **Make sure Redis is running before starting the workers.**

    ```sh
    uv run celery -A backend.celery_app worker -l info
    ```

    * `-A backend.celery_app`: Points to the Celery application instance.
    * `worker`: Specifies that this process should run as a worker.
    * `-l info`: Sets the logging level to INFO (can be changed to DEBUG, WARNING, etc.).

3. **Start the Frontend Development Server:**
    Run the development server script:

    ```sh
    pnpm dev
    ```

    *(This command typically starts a local web server for the frontend with features like automatic reloading when you change frontend code.)*

4. **Access the Frontend:**
    * Once the server starts, it will usually print a URL in the terminal. Open this URL in your web browser.
    * Common URLs are `http://localhost:5173` (Vite default).

**Summary of Running Terminals:**

To run the full MOSS application locally for development, you will typically need **three separate terminals** running concurrently (ensure the Python virtual environment is activated in the backend terminals):

1. **Terminal 1:** Backend API Server (`uvicorn backend.main:app ...`)
2. **Terminal 2:** Celery Worker (`celery -A backend.celery_app worker ...`)
3. **Terminal 3:** Frontend Development Server (`cd frontend && npm run dev`)

*(Remember to have PostgreSQL and Redis running in the background as well).*

## Running Database Migrations Manually

If you make changes to the database models (`backend/data/models/`) later, you will need to:

1. **Generate a new migration script:**

    ```sh
    alembic revision --autogenerate -m "Short description of changes"
    ```

    *(Review the generated script in `backend/data/migrations/versions/`)*

2. **Apply the migration:**

    ```sh
    python scripts/setup_db.py
    ```

    *(Alternatively, you can use `alembic upgrade head`)*

## Directory Structure

A high-level overview of the project structure:

* `moss/`: Project root.
  * `backend/`: Contains all the backend code (API, services, data layer).
    * `api/`: FastAPI endpoints and dependencies.
    * `config/`: Configuration loading (`settings.py`) and logging (`logging_config.py`).
    * `data/`: Database interaction (models, repositories, migrations).
    * `external/`: Clients for external APIs (GitHub, OpenAlex).
    * `schemas/`: Pydantic models for API request/response validation.
    * `services/`: Business logic layer.
    * `tasks/`: Celery background task definitions.
    * `utils/`: Shared utility functions.
  * `contrib/`: Location for contributed "recipe" scripts (analysis, affiliation, discovery).
  * `frontend/`: Contains the React frontend code (setup instructions not covered here).
  * `logs/`: Where log files (`moss_api.log`, `moss_celery.log`) are stored.
  * `scripts/`: Helper scripts (database setup).

## Configuration Summary (`.env`)

The `.env` file is crucial for configuring the application. Key variables:

* `DATABASE_URL`: Connection string for PostgreSQL.
* `GITHUB_API_TOKEN`: Essential for interacting with GitHub.
* `OPENALEX_EMAIL`: Recommended for better OpenAlex API access.
* `CELERY_BROKER_URL`: Connection URL for Redis (or other broker).
* `CELERY_RESULT_BACKEND_URL`: Connection URL for Redis (or other backend).
* `VITE_API_BASE_URL`: URL for the backend API
