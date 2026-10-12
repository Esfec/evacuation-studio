"""Allow both existing test suites to be run from the release root."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for directory in ("01_\u7814\u7a76\u6e90\u7801", "02_\u53ef\u89c6\u5316\u6c99\u76d2"):
    sys.path.insert(0, str(ROOT / directory))
