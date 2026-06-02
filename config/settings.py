from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BUCKET = "bigdata-n9-ptit-final"

GCS_LSH_INDEX = f"gs://{BUCKET}/intermediate/minhash_index/lsh_index.pkl"
GCS_LOOKUP = f"gs://{BUCKET}/gold/online_paper_lookup"

LOCAL_LSH_INDEX = PROJECT_ROOT / "data" / "cache" / "lsh_index" / "lsh_index.pkl"
LOCAL_LOOKUP_CACHE = PROJECT_ROOT / "data" / "cache" / "lookup_partitions"
INPUT_DIR = PROJECT_ROOT / "data" / "input_pdfs"
REPORT_DIR = PROJECT_ROOT / "data" / "reports"

SHINGLE_K = 5
NUM_PERM = 128
LARGE_PRIME = 2147483647

MIN_SEGMENT_WORDS = 20
SMALL_MATCH_WORDS = 10
NGRAM_THRESHOLD = 0.60
FUZZY_THRESHOLD = 0.85
MAX_CANDIDATES = 50