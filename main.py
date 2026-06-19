#!/usr/bin/env python
"""
Entrypoint for the Instagram Optimizer.
Allows running the application directly from the root directory.
"""
import sys
import os

# Add the current directory to sys.path so the package is importable
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from insta_optimizer.cli import cli

if __name__ == "__main__":
    cli()
