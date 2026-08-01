from __future__ import annotations

import os
import sys

# Allow: python setup/main.py from repo root
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from setup.onboarding.questionnaire import main


if __name__ == "__main__":
    main()
