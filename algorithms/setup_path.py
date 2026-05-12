import sys
import os

# Add the project root directory to Python path so that
# 'from algorithms.xxx' imports work regardless of CWD
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
