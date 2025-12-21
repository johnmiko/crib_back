"""Pytest configuration and fixtures.

Ensures the crib project directory is in the Python path so imports work correctly.
"""

import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
