# MOSS - Map of Open Source Science

[License: Apache v2](http://www.apache.org/licenses/)

## Overview

Map of Open Source Science (MOSS) is an open-source application and collaborative effort to model and map the domain of open-source research software and it's intersection with academia and scientific publication. It aims to construct a knowledge graph system and reproducible framework for modeling public repositories, academic publications, and the contributing entities and relationships between them. This is accomplished by structured integration of data obtained through overlapping web traversal and graph construction strategies, grounded on existing schema and ontologies such as using context driven rules such as direct or mentioned DOI linking (`<a>https://doi.org/10.1000/100</a>` vs `<p>https://doi.org/10.1000/100</p>`), and care is taken to conform to existing schema based systems (OpenAlex topics, Schema.org entities)

The Map of Open Source Science (MOSS) is a platform that reveals the hidden connections between research software and academic scholarship. It builds a rich knowledge graph of the research ecosystem by ingesting data about software repositories, scholarly publications, researchers, and institutions. By linking these entities, MOSS helps answer critical questions about the impact, sustainability, and collaborative nature of open source in science.

This repository contains the backend services, API, and frontend application for the MOSS platform. It provides the tools to ingest data from sources like GitHub and OpenAlex, store it in a structured database, and expose it for analysis and exploration.

## Key Features

* **Data Ingestion:**
  * **Repository Ingestion:** Ingest GitHub repositories directly via URL, asynchronously as workers with keyword searches, or discover through connection traversal
* **Scholarly Linking:**
  * **DOI Extraction:** Automatically extracts DOIs from repository files like `README.md` and `CITATION.cff`.
  * **Publication Mapping:** Resolves DOIs using the OpenAlex API to fetch detailed publication metadata.
  * **Citation Traversal:** Recursively processes citation networks (references and citations) to build a deeper graph.
* **Entity Tracking:**
  * **Comprehensive Modeling:** Stores detailed information for repositories, repository owners (users/organizations), contributors, scholarly works, authors, and institutions.
  * **Relationship Tracking:** Models affiliations between authors and institutions, and dependencies from common package manager files (e.g., `requirements.txt`, `package.json`).
* **Data Provenance:**
  * **Discovery Chains:** A robust `DiscoveryChain` system tracks the origin of every piece of data, recording how it was discovered and linked. This ensures transparency and reproducibility.
* **Asynchronous Processing:**
  * **Background Tasks:** Leverages Celery and Redis to handle long-running processes like repository discovery and citation traversal without blocking the API.
* **Modern API:**
  * **FastAPI Backend:** A high-performance RESTful API provides endpoints for triggering ingestion and querying the knowledge graph.
  * **Interactive Docs:** Automatic API documentation is available via Swagger UI and ReDoc.

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

 1. **uv:** Python package manager | [uv - Installation](https://docs.astral.sh/uv/getting-started/installation/)
 2. **pnpm:** Node package manager | [pnpm - Installation](https://pnpm.io/installation)
 3a. **Docker and Docker Compose:** (Recommended for simplified setup of PostgreSQL and Redis). Install Docker and Docker Compose.
 3b. **Alternatively, for manual setup of services:**
    * **PostgreSQL:** Version 12+
    * **Redis:** Version 6+

## Setup

1. **Configure Environment:**
    * Copy `.env.example` to `.env` and add your `GITHUB_API_TOKEN`. This is the only variable you need to change to get started.

    ```sh
    cp .env.example .env
    ```

    * **Edit `.env` and add your GitHub Token.** This is the only variable you need to change to get started.
    * `GITHUB_API_TOKEN`: Your GitHub Personal Access Token (PAT).
      * Generate one at: <https://github.com/settings/tokens> (use "Tokens classic").
      * Grant the `public_repo` scope for read-only access to public repositories.

2. **Start Background Services:**
    This command starts PostgreSQL and Redis using Docker Compose.

    ```sh
    docker compose up -d
    ```

3. **Set up the Database & Frontend:**
    * This command, powered by `poethepoet`, runs database migrations and installs all frontend dependencies. It uses `uv run` to execute `poe` from the virtual environment without needing to activate it.

    ```sh
    uv run poe setup
    ```

4. **Run the Application:**
    * This single command starts the API server, Celery worker, and frontend development server concurrently in one terminal.

    ```sh
    uv run poe start
    ```

    * To stop all services, press `Ctrl+C`.

5. **Access the Application:**
    * The API documentation will be available at `http://localhost:8000/docs`.
    * The frontend will be available at the URL provided by the `pnpm dev` command (usually `http://localhost:5173`).

## Manual Setup & Configuration

### Manual Python Environment Setup

This project uses `poethepoet` for task automation, which simplifies the setup process. The recommended setup above is the easiest path. If you wish to run commands manually, you can inspect the tasks defined in `pyproject.toml` under `[tool.poe.tasks]`.

The manual steps are:

1. **Create Virtual Environment:**

    ```sh
    uv venv
    source .venv/bin/activate
    ```

2. **Install Dependencies:**

    ```sh
    uv sync
    ```

3. **Run Database Migrations:**

    ```sh
    uv run python scripts/setup_db.py
    ```

4. **Install Frontend Dependencies:**

    ```sh
    pnpm --dir frontend install
    ```

5. **Start the Services (in 3 separate terminals):**
    * **Terminal 1: API Server**

      ```sh
      uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
      ```

    * **Terminal 2: Celery Worker**

      ```sh
      uv run celery -A backend.celery_app worker -l info
      ```

    * **Terminal 3: Frontend Server**

      ```sh
      pnpm --dir frontend dev
      ```

### Manual Service Setup (PostgreSQL & Redis)

If you are not using Docker, ensure PostgreSQL and Redis are installed and running, then:

* **PostgreSQL:**
    1. Create a database (e.g., `moss_db`).
    2. Create a user and password (e.g., `moss_user`).
    3. Grant the user privileges on the database.
    4. Update the `POSTGRES_*` variables and the `DATABASE_URL` in your `.env` file to match.
* **Redis:**
    1. Ensure the Redis server is running.
    2. Update `REDIS_HOST`, `REDIS_PORT`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND_URL` in `.env` if your server is not on the default `localhost:6379`.

### Environment Variable Details (`.env`)

The `.env` file is crucial for configuring the application. Here is a detailed breakdown:

* **`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`**: These are used by Docker Compose to initialize the PostgreSQL container. They are also used to construct the `DATABASE_URL`.
* **`REDIS_HOST`, `REDIS_PORT`**: Used by Docker Compose and to construct the Celery URLs.
* **`DATABASE_URL`**: The full connection string for PostgreSQL, used by SQLAlchemy. Must be consistent with the `POSTGRES_*` variables.
* **`CELERY_BROKER_URL`**: The URL for your Redis server (or other message broker) for task queuing.
* **`CELERY_RESULT_BACKEND_URL`**: The URL for your Redis server to store task results.
* **`GITHUB_API_TOKEN`**: **(Required)** Your GitHub Personal Access Token (PAT) for interacting with the GitHub API.
* **`OPENALEX_EMAIL`**: **(Recommended)** Your email address for the OpenAlex API "polite pool" to get better rate limits.
* **`VITE_API_BASE_URL`**: The base URL for the backend API, used by the frontend.

## Manual Database Migrations

If you make changes to the database models (`backend/data/models/`) later, you will need to:

1. **Generate a new migration script:**

    ```sh
    alembic revision --autogenerate -m "Short description of changes"
    ```

    *(Review the generated script in `backend/data/migrations/versions/`)*

2. **Apply the migration:**

    ```sh
    uv run python scripts/setup_db.py
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
