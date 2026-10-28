"""Repository paths, independent of the shell's working directory."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELS_DIR = ROOT / "models"
TESTS_DIR = ROOT / "tests"
RAW_DATA_DIR = ROOT / "01_data" / "raw"
CHARACTERISTICS_PATH = RAW_DATA_DIR / "chars_final_with_names.parquet"
FEATURE_LIST_PATH = RAW_DATA_DIR / "factor_char_list.csv"
