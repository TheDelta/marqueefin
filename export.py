#!/usr/bin/env python3
"""Marqueefin: your Jellyfin library as one shareable HTML page.

Standard library only. Settings come from flags, then the environment, then .env (here
or next to this script): see --help and .env.example. The code is in marqueefin/."""

from marqueefin.cli import run

if __name__ == "__main__":
    run()
