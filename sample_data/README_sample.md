# Sample Data

> **10 papers** trich xuat tu `bigdata-n9-ptit-final` de minh hoa schema.
> Text cat ngan con 200 ky tu. Khong dung cho production.

## Cau truc

```
sample_data/
├── bronze/
│   └── arxiv_metadata_sample.parquet     # Raw metadata tu ArXiv (10 records)
├── silver/
│   └── arxiv_silver_plus_sample.parquet  # Sau buoc lam sach (10 papers)
├── chunks/
│   └── chunks_sample.parquet             # Chunks van ban (50 chunks)
├── faiss/
│   └── chunk_metadata_sample.parquet     # Mapping chunk → vector index (50 rows)
│   # faiss_index.bin (1.8GB) luu tren GCS, khong dua len GitHub
└── minhash/
    └── schema.json                       # Mo ta cau truc MinHash
    # minhashes.pkl (980MB) + lsh_index.pkl (445MB) luu tren GCS
```

---

## Schema

### `bronze/arxiv_metadata_sample.parquet`
Nguon: `bronze/raw_metadata/arxiv/2026_04_30/arxiv_full_dump.jsonl` (5 GB)

| Column | Type | Ví dụ |
|-|-|-|
| `doc_id` | str | arxiv_0704.0001 |
| `hash_sha256` | str | 096a8b63b63fcc96cc37b3545f43c0f8e3d3638a83801d78c08b55ed20fd |
| `title` | str | Calculation of prompt diphoton production cross sections at  |
| `abstract` | str | A fully differential calculation in perturbative quantum chr |
| `authors` | list[str] | ['C. Balázs', 'E. L. Berger', 'P. M. Nadolsky', 'C. -P. Yuan |
| `language` | str | en |
| `categories` | str | ['hep-ph'] |
| `publish_date` | str | 2008-11-26 |
| `doi` | str | 10.1103/PhysRevD.76.013009 |
| `source_url` | str | https://arxiv.org/abs/0704.0001 |
| `pdf_url` | str | https://arxiv.org/pdf/0704.0001.pdf |
| `local_path_bronze` | str | gs://bigdata-n9-ptit/bronze/arxiv/arxiv_0704.0001.pdf |
| `scraped_at` | str | 2026-04-29T17:19:36.212118Z |

---

### `silver/arxiv_silver_plus_sample.parquet`
Nguon: `silver/arxiv_silver_plus/` (Spark parquet, ~900 MB)

| Column | Type | Ví dụ |
|-|-|-|
| `paper_id` | str | arxiv_0704.0389.pdf |
| `file_path` | str | gs://bigdata-n9-ptit-final/bronze/raw_pdfs/arxiv/arxiv_0704. |
| `raw_text` | str | arXiv:0704.0389v8  [gr-qc]  22 Jul 2011 1 For reference, the |
| `clean_text` | str | 1 For reference, the following erratum corrects the publishe |
| `abstract` | str | We analyze the effect of gravitational radiation reaction on |
| `introduction` | str |  |
| `body` | str | 1 For reference, the following erratum corrects the publishe |
| `word_count_raw` | str | 15366 |
| `word_count_clean` | str | 15193 |
| `title` | str | Evolution of the Carter constant for inspirals into a black  |
| `authors` | list[str] | ['Eanna E. Flanagan' 'Tanja Hinderer'] |
| `categories` | str | ['gr-qc'] |
| `quality_flag` | str | ok |

---

### `chunks/chunks_sample.parquet`
Nguon: `intermediate/chunks_parquet/`

| Column | Type | Ví dụ |
|-|-|-|
| `paper_id` | str | arxiv_0704.0397.pdf |
| `chunk_id` | str | 0 |
| `section` | str | abstract |
| `chunk_text` | str | We propose a measurement protocol to generate path-entangled |

---

### `faiss/chunk_metadata_sample.parquet`
Nguon: `intermediate/faiss_index/chunk_metadata.parquet` (176.7 MB)
Dung kem voi `faiss_index.bin` (1.8 GB, luu tren GCS).

| Column | Type | Ví dụ |
|-|-|-|
| `paper_id` | str | arxiv_0704.0397.pdf |
| `chunk_id` | str | 0 |
| `section` | str | abstract |
| `chunk_text` | str | We propose a measurement protocol to generate path-entangled |
| `index_position` | int | 0 |

---

### `minhash/schema.json`
Mo ta cau truc cua `minhashes.pkl` (980 MB) va `lsh_index.pkl` (445 MB).
Cac file nay luu tren GCS, khong dua len GitHub do qua lon.

---

## Data Lineage

```
[Bronze] arxiv_full_dump.jsonl (5 GB)
    │
    ▼ clean_text (9 buoc)
[Silver] arxiv_silver_plus
    │
    ├──▶ chunk_text ──▶ [Chunks] chunks_parquet
    │                       │
    │              ┌────────┴────────┐
    │              ▼                 ▼
    │        faiss_index.bin    minhashes.pkl
    │           (1.8 GB)          (980 MB)
    │
    └──▶ 05_demo_check_pdf ──▶ Ket qua kiem tra dao van
```
