# config.py
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE_URL = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")

# OpenAlex Configuration
OPENALEX_BASE_URL = os.getenv("OPENALEX_BASE_URL", "https://api.openalex.org")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mosspoc.db")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
