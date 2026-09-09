"""
Application configuration.

This module loads configuration values from environment variables
and makes them available to the rest of the application.
"""

import os

from dotenv import load_dotenv


# Load variables from the .env file.
load_dotenv()


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")