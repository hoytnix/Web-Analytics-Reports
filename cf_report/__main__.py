"""
Entry point for python -m cf_report
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
