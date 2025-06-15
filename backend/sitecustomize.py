import sys
from pathlib import Path

# Determine project root (parent directory of the backend package)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Prepend project root to sys.path if not already present
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Optional: ensure backend package always imports from project root path
BACKEND_PATH = PROJECT_ROOT / "backend"
backend_path_str = str(BACKEND_PATH)
if backend_path_str not in sys.path:
    sys.path.insert(0, backend_path_str) 