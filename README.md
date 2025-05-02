# MOSS - Map of Open Source Science

[License: Apache v2](http://www.apache.org/licenses/)

## Overview

MOSS (Map of Open Source Science) is a backend application designed to build a knowledge graph about open source scientific software. It ingests data about repositories (primarily from GitHub), links them to scholarly works (using DOIs and OpenAlex), identifies contributors and institutions, and provides an API to query these relationships. It also supports running custom analysis and discovery algorithms ("recipes").

The system uses a FastAPI web framework for its API, PostgreSQL as the database, Celery for background task processing (like keyword-based discovery and DOI processing), and Redis as the message broker for Celery.

## Key Features

*   **Data Ingestion:**
    *   Ingest GitHub repositories via direct URL.
    *   Discover and ingest repositories based on keyword searches (asynchronous).
*   **Scholarly Linking:**
    *   Extracts DOIs from repository files (e.g., README).
    *   Resolves DOIs and fetches metadata from OpenAlex.
    *   Processes citation networks (references and citations).
*   **Entity Tracking:**
    *   Stores detailed information about Repositories, Owners (Users/Orgs), Contributors.
    *   Stores Scholarly Works, Persons (Authors), Institutions.
    *   Tracks affiliations between authors and institutions.
    *   Tracks dependencies listed in common package files (`requirements.txt`, `package.json`).
    *   Tracks GitHub Issues, Pull Requests, and associated comments.
*   **Provenance:** Uses a `DiscoveryChain` system to track how data was found and linked.
*   **Extensibility:** Supports custom "recipes" for:
    *   Affiliation detection between repositories and institutions.
    *   Data analysis queries.
    *   Repository discovery algorithms.
*   **API:** Provides a RESTful API (built with FastAPI) for interacting with the ingested data and triggering processes.

## Technology Stack

*   **Backend Framework:** FastAPI
*   **Database:** PostgreSQL
*   **ORM:** SQLAlchemy
*   **Migrations:** Alembic
*   **Background Tasks:** Celery
*   **Message Broker / Cache:** Redis
*   **HTTP Client:** Requests
*   **Logging:** Python `logging`, `concurrent-log-handler`
*   **Configuration:** `python-dotenv`
*   **API Clients:** Custom clients for GitHub API v3 and OpenAlex API
*   **Analysis (Optional):** NetworkX, python-louvain

 ## Prerequisites

 Before you begin, ensure you have the following installed on your system:

 1.  **Python:** Version 3.10 or higher is recommended. [Download Python](https://www.python.org/downloads/)
 2.  **pip:** Python's package installer (usually comes with Python).
 3.  **Git:** For cloning the repository. [Download Git](https://git-scm.com/downloads)
 4.  **PostgreSQL:** A running PostgreSQL database server (version 12+ recommended). You'll need the ability to create a database and a user. [Download PostgreSQL](https://www.postgresql.org/download/)
 5.  **Redis:** A running Redis server. Celery uses this to manage background tasks. [Download Redis](https://redis.io/docs/getting-started/installation/) or use Docker.
+6.  **Node.js and npm:** For running the frontend application. Npm usually comes bundled with Node.js. [Download Node.js](https://nodejs.org/) (LTS version recommended). You can check your installation by running `node -v` and `npm -v` in your terminal.

## Setup Instructions

Follow these steps carefully to set up the MOSS backend application:

1.  **Clone the Repository:**
    Open your terminal or command prompt and run:
    ```bash
    git clone https://github.com/numfocus/MOSS.git
    cd moss/
    ```

2.  **Create a Virtual Environment:**
    It's highly recommended to use a virtual environment to isolate project dependencies.
    ```bash
    python -m venv venv
    ```
    *(This creates a `venv` directory in your project folder.)*

3.  **Activate the Virtual Environment:**
    *   **On macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```
    *   **On Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    *(Your terminal prompt should change to indicate the active environment, e.g., `(venv)`).*

4.  **Install Dependencies:**
    Install all the required Python packages listed in `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment Variables (`.env` file):**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   **Edit the `.env` file** using a text editor and fill in the required values:
        *   `DATABASE_URL`: The connection string for your PostgreSQL database.
            *   Format: `postgresql://<user>:<password>@<host>:<port>/<dbname>`
            *   Example: `postgresql://moss_user:your_secure_password@localhost:5432/moss_db`
            *   Make sure the user (`moss_user`) and database (`moss_db`) exist and the user has privileges (see next step).
        *   `GITHUB_API_TOKEN`: Your GitHub Personal Access Token (PAT).
            *   This is needed to interact with the GitHub API (fetching repository info, etc.).
            *   Generate one at: [https://github.com/settings/tokens](https://github.com/settings/tokens) (use "Tokens classic").
            *   Grant the `public_repo` scope for read-only access to public repositories. Keep this token secure!
            *   Example: `ghp_YourGitHubTokenHere`
        *   `OPENALEX_EMAIL`: Your email address.
            *   This is used to identify your requests to the OpenAlex API, placing you in their "polite pool" which might offer better rate limits. It's recommended but the application might work without it (with lower limits).
            *   Example: `your.email@example.com`
        *   `CELERY_BROKER_URL`: URL for your Redis server (used by Celery for task queuing).
            *   Default assumes Redis running locally on default port: `redis://localhost:6379/0` (using database 0). Adjust if your Redis is different.
        *   `CELERY_RESULT_BACKEND_URL`: URL for your Redis server (used by Celery to store task results).
            *   Default: `redis://localhost:6379/1` (using database 1, different from the broker). Adjust if needed.

6.  **Set Up PostgreSQL Database:**
    *   Connect to your PostgreSQL server (e.g., using `psql` or a GUI tool).
    *   Create the database (if it doesn't exist). **Use the name you specified in `.env`**.
        ```sql
        CREATE DATABASE moss_db;
        ```
    *   Create a user and grant privileges. **Use the username and password specified in `.env`**.
        ```sql
        CREATE USER moss_user WITH PASSWORD 'your_secure_password';
        GRANT ALL PRIVILEGES ON DATABASE moss_db TO moss_user;
        -- Optional: Make the user the owner if needed
        -- ALTER DATABASE moss_db OWNER TO moss_user;
        ```
    *   *(**Note:** These are example commands. Adjust them based on your PostgreSQL setup and security practices.)*

7.  **Run Database Migrations:**
    This step creates all the necessary tables in your database based on the application's models. We use Alembic, managed via a script.
    ```bash
    python scripts/setup_db.py
    ```
    *(You should see output indicating migrations are being applied. If this fails, double-check your `DATABASE_URL` in `.env` and ensure PostgreSQL is running and accessible.)*

## Running the Application

The application consists of two main parts that need to run concurrently: the **API Server** and the **Celery Workers**. You will typically run these in separate terminal windows (make sure the virtual environment is activated in each).

1.  **Start the API Server (FastAPI with Uvicorn):**
    This makes the REST API available.
    ```bash
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
    ```
    *   `backend.main:app`: Tells Uvicorn where to find the FastAPI app instance.
    *   `--reload`: Automatically restarts the server when code changes (useful for development). Remove this flag in production.
    *   `--host 0.0.0.0`: Makes the server accessible from other devices on your network (not just `localhost`).
    *   `--port 8000`: Specifies the port the server will listen on.
    *   You should see output indicating the server is running, often including `Application startup complete.`
    *   You can access the API documentation at `http://localhost:8000/docs` in your browser.

2.  **Start the Celery Workers:**
    These processes handle background tasks like keyword discovery and DOI processing. **Make sure Redis is running before starting the workers.**
    ```bash
    celery -A backend.celery_app worker -l info -P eventlet -c 4
    ```
    *   `-A backend.celery_app`: Points to the Celery application instance.
    *   `worker`: Specifies that this process should run as a worker.
    *   `-l info`: Sets the logging level to INFO (can be changed to DEBUG, WARNING, etc.).
    *   `-P eventlet`: (**Optional, Recommended**) Specifies the concurrency pool type. `eventlet` is good for I/O-bound tasks (like API calls). Requires `pip install eventlet`. If omitted, Celery might use a process-based pool.
    *   `-c 4`: (**Optional**) Sets the number of concurrent worker processes/threads to 4. Adjust based on your machine's resources.
    *   You should see output indicating the worker has connected to the broker (Redis) and is ready to receive tasks. Log messages from tasks will appear here.

## Frontend Setup and Running

The frontend application is typically developed and run separately from the backend API.

1.  **Navigate to Frontend Directory:**
    Open a **new terminal window** (separate from the backend server and Celery worker terminals) and navigate into the frontend directory:
    ```bash
    cd frontend/
    ```

2.  **Install Frontend Dependencies:**
    Install the necessary Node.js packages defined in `package.json`:
    ```bash
    npm install
    ```
    *(This command downloads all the libraries the frontend needs. It might take a few minutes the first time.)*

3.  **Configure Frontend Environment (Optional):**
    *   The frontend might require its own environment variables (e.g., the URL of the backend API). Look for a file named `.env.development.local` or similar example files in the `frontend/` directory.
    *   If an example file exists (like `.env.development.local.example`), copy it:
        ```bash
        cp .env.development.local.example .env.development.local
        ```
    *   Edit the `.env.development.local` file and adjust any necessary settings, such as `VITE_API_BASE_URL` if the backend isn't running on `http://localhost:8000`. By default, it should usually point to where the backend API server is running.

4.  **Start the Frontend Development Server:**
    Run the development server script:
    ```bash
    npm run dev
    ```
    *(This command typically starts a local web server for the frontend with features like automatic reloading when you change frontend code.)*

5.  **Access the Frontend:**
    *   Once the server starts, it will usually print a URL in the terminal. Open this URL in your web browser.
    *   Common URLs are `http://localhost:5173` (Vite default) or `http://localhost:3000` (Create React App default). Check the terminal output for the correct one.

**Summary of Running Terminals:**

To run the full MOSS application locally for development, you will typically need **three separate terminals** running concurrently (ensure the Python virtual environment is activated in the backend terminals):

1.  **Terminal 1:** Backend API Server (`uvicorn backend.main:app ...`)
2.  **Terminal 2:** Celery Worker (`celery -A backend.celery_app worker ...`)
3.  **Terminal 3:** Frontend Development Server (`cd frontend && npm run dev`)

*(Remember to have PostgreSQL and Redis running in the background as well).*
## Running Database Migrations Manually

If you make changes to the database models (`backend/data/models/`) later, you will need to:

1.  **Generate a new migration script:**
    ```bash
    alembic revision --autogenerate -m "Short description of changes"
    ```
    *(Review the generated script in `backend/data/migrations/versions/`)*

2.  **Apply the migration:**
    ```bash
    python scripts/setup_db.py
    ```
    *(Alternatively, you can use `alembic upgrade head`)*

## Directory Structure

A high-level overview of the project structure:

*   `moss/`: Project root.
    *   `backend/`: Contains all the backend code (API, services, data layer).
        *   `api/`: FastAPI endpoints and dependencies.
        *   `config/`: Configuration loading (`settings.py`) and logging (`logging_config.py`).
        *   `data/`: Database interaction (models, repositories, migrations).
        *   `external/`: Clients for external APIs (GitHub, OpenAlex).
        *   `schemas/`: Pydantic models for API request/response validation.
        *   `services/`: Business logic layer.
        *   `tasks/`: Celery background task definitions.
        *   `utils/`: Shared utility functions.
    *   `contrib/`: Location for contributed "recipe" scripts (analysis, affiliation, discovery).
    *   `frontend/`: Contains the React frontend code (setup instructions not covered here).
    *   `logs/`: Where log files (`moss_api.log`, `moss_celery.log`) are stored.
    *   `scripts/`: Helper scripts (database setup).

## Configuration Summary (`.env`)

The `.env` file is crucial for configuring the application. Key variables:

*   `DATABASE_URL`: Connection string for PostgreSQL.
*   `GITHUB_API_TOKEN`: Essential for interacting with GitHub.
*   `OPENALEX_EMAIL`: Recommended for better OpenAlex API access.
*   `CELERY_BROKER_URL`: Connection URL for Redis (or other broker).
*   `CELERY_RESULT_BACKEND_URL`: Connection URL for Redis (or other backend).
