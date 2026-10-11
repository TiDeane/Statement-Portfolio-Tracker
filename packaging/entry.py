"""Script PyInstaller freezes. Kept tiny so all real code lives in the package."""

import sys

from statement_tracker.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
