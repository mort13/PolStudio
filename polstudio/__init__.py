"""PolStudio: offline GUI for the ToFPipeline analysis of FLASH ToF data."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "ToFPipeline"
DEFAULT_CONFIG = PIPELINE_DIR / "config.yaml"
RESULTS_DIR = ROOT / "results"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

__version__ = "0.1.0"
