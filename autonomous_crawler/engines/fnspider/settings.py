from pathlib import Path


AFFIX_FOLDERS = "SubsidiaryDir"
REQUEST_TIME_OUT = 30000
REQUEST_RETRY = 3

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PACKAGE_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = str(RUNTIME_DIR / "fnspider_cache")
OUT_PATH = str(RUNTIME_DIR / "fnspider_goods")
