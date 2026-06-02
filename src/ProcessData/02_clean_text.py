import re
import unicodedata
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage
from io import BytesIO
import pandas as pd

PROJECT = "bigdataptit2026"
BUCKET_NAME = "bigdata-n9-ptit-final"
INPUT_PREFIX = "silver/arxiv_text_parquet/"
OUTPUT_PREFIX = "silver/arxiv_cleaned_parquet/"

client = storage.Client(project=PROJECT)
bucket = client.bucket(BUCKET_NAME)


def clean_arxiv_text(text):
    if not text or not isinstance(text, str):
        return {
            "clean_text": "", "has_references": False,
            "word_count_clean": 0, "reduction_ratio": 0.0, "quality_flag": "empty"
        }

    original_len = len(text.split())

    # Tang 1: Xoa ArXiv header
    text = re.sub(
        r'^arXiv:\S+\s+\[[\w.\-]+\]\s+\d+\s+\w+\s+\d{4}\s*\n',
        '', text, flags=re.MULTILINE)

    # Tang 2: Xoa journal template metadata
    text = re.sub(
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+\d{1,2},?\s+\d{4}\n\d{1,2}:\d{2}\n', '', text)
    text = re.sub(
        r'(?:WSPC|World Scientific|Typeset with|Preprint submitted to|'
        r'Preprint typeset using|Draft version)[^\n]*\n(?:[^\n]{0,60}\n){0,2}',
        '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[A-Z]{2,10}-[\w/\-]+(?:,\s*[A-Z]{2,10}-[\w/\-]+)*\s*\n',
                  '', text, flags=re.MULTILINE)

    # Tang 3: Xoa References (chi trong 40% cuoi bai)
    has_references = False
    total_len = len(text)
    search_start = int(total_len * 0.60)

    ref_match = re.search(
        r'\n\s*(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*\n',
        text[search_start:])
    if ref_match:
        text = text[:search_start + ref_match.start()]
        has_references = True
    else:
        search_strict = int(total_len * 0.75)
        ref_match2 = re.search(
            r'\n(?:\[\d+\]|\d+[\)\.]\s)\s*[A-Z][^.]{15,}\n'
            r'(?:(?:\[\d+\]|\d+[\)\.]\s)\s*.{10,}\n){4,}',
            text[search_strict:])
        if ref_match2:
            text = text[:search_strict + ref_match2.start()]
            has_references = True

    # Tang 4: Xoa so trang
    text = re.sub(r'\n\s*\d{1,3}\s*\n', '\n', text)
    text = re.sub(r'\n\s*\d+/\d+\s*\n', '\n', text)
    text = re.sub(r'\bpage\s+\d+\s+of\s+\d+\b', '', text, flags=re.IGNORECASE)

    # Tang 5: Fix ligatures
    for lig, rep in {'\ufb00':'ff','\ufb01':'fi','\ufb02':'fl',
                     '\ufb03':'ffi','\ufb04':'ffl','\ufb05':'st','\ufb06':'st'}.items():
        text = text.replace(lig, rep)

    # Tang 6: Unicode NFKC
    text = unicodedata.normalize("NFKC", text)

    # Tang 7: Xoa ky tu khong in duoc
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Tang 8: Fix hyphenation cuoi dong
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

    # Tang 9: Xoa email, URL, chuan hoa whitespace
    text = re.sub(r'\[?\w+@[\w.]+\]?\(?mailto:[\w@.]+\)?', '', text)
    text = re.sub(r'\S+@\S+\.\S+', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = text.strip()

    # Quality flag
    clean_wc = len(text.split())
    ratio = clean_wc / original_len if original_len > 0 else 0
    if clean_wc < 300: qf = "empty"
    elif clean_wc < 500: qf = "low_quality"
    elif ratio < 0.3: qf = "over_cleaned"
    else: qf = "ok"

    return {
        "clean_text": text, "has_references": has_references,
        "word_count_clean": clean_wc, "reduction_ratio": round(ratio, 3),
        "quality_flag": qf,
    }


# === CHAY ===
blobs = [b for b in bucket.list_blobs(prefix=INPUT_PREFIX) if b.name.endswith(".parquet")]
print("Tong: {} files".format(len(blobs)))

existing = set(b.name for b in bucket.list_blobs(prefix=OUTPUT_PREFIX))
stats = {"total": 0, "ok": 0, "empty": 0}

for idx, blob in enumerate(blobs):
    out_name = blob.name.replace(INPUT_PREFIX, OUTPUT_PREFIX)
    if out_name in existing:
        continue

    df = pq.read_table(BytesIO(blob.download_as_bytes())).to_pandas()
    rows = []
    for _, row in df.iterrows():
        r = clean_arxiv_text(row["text"])
        rows.append({
            "file_path": row["file_path"],
            "clean_text": r["clean_text"],
            "word_count_raw": row.get("word_count", len(str(row["text"]).split())),
            "word_count_clean": r["word_count_clean"],
            "reduction_ratio": r["reduction_ratio"],
            "has_references": r["has_references"],
            "quality_flag": r["quality_flag"],
        })
        stats["total"] += 1
        stats[r["quality_flag"]] = stats.get(r["quality_flag"], 0) + 1

    out_buf = BytesIO()
    pq.write_table(pa.Table.from_pandas(pd.DataFrame(rows)), out_buf)
    out_buf.seek(0)
    bucket.blob(out_name).upload_from_file(out_buf, content_type="application/octet-stream")

    if (idx + 1) % 10 == 0 or idx == 0:
        print("  {}/{} | rows: {:,}".format(idx + 1, len(blobs), stats["total"]))

print("\nHoan thanh! {:,} bai | ok: {:,} | empty: {:,}".format(
    stats["total"], stats.get("ok", 0), stats.get("empty", 0)))