"""Marqueefin: your Jellyfin library as one shareable HTML page."""

import os

# SemVer; scripts/release.py bumps it, and a release tag must match it
__version__ = "1.0.0"
PROJECT = "Marqueefin"
PROJECT_URL = "https://github.com/TheDelta/marqueefin"  # linked in the page footer ('': no link)
USER_AGENT = f"{PROJECT}/{__version__}"
# The repository (or /app in the image): src/, node_modules/ and .env live there
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
