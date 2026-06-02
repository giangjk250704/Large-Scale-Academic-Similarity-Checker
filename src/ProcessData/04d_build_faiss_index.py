"""
04d_build_faiss_index.py - Build FAISS Index (Embedding)
Input:  gs://BUCKET/intermediate/chunks_parquet/
Output: gs://BUCKET/intermediate/faiss_index/
        - faiss_index.bin, chunk_metadata.parquet, index_config.json
"""

import os, json, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.fs as pafs

BUCKET = "bigdata-n9-ptit-final"
CHUNKS_INPUT = "bigdata-n9-ptit-final/intermediate/chunks_parquet"
MODEL_NAME = "allenai/specter"
EMBEDDING_DIM = 768
BATCH_SIZE = 128
SECTIONS_TO_EMBED = ["abstract"]  # Chi abstract cho toc do; None = tat ca

gcs = pafs.GcsFileSystem()

print("[1/6] Doc chunks...")
t0 = time.time()
df_chunks = pq.read_table(CHUNKS_INPUT, filesystem=gcs).to_pandas()
print("  Tong: {} chunks".format(len(df_chunks)))

if SECTIONS_TO_EMBED:
    df_chunks = df_chunks[df_chunks["section"].isin(SECTIONS_TO_EMBED)].reset_index(drop=True)
    print("  Sau loc {}: {}".format(SECTIONS_TO_EMBED, len(df_chunks)))

df_chunks = df_chunks.dropna(subset=["chunk_text"])
df_chunks = df_chunks[df_chunks["chunk_text"].str.len() > 20].reset_index(drop=True)
print("  {:.0f}s".format(time.time() - t0))

print("\n[2/6] Load model...")
import torch
from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device).eval()
print("  Device: {}".format(device))

print("\n[3/6] Embed {} chunks...".format(len(df_chunks)))
t1 = time.time()
texts = df_chunks["chunk_text"].tolist()
all_emb = []
total_b = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
for i in range(0, len(texts), BATCH_SIZE):
    bn = i // BATCH_SIZE + 1
    if bn % 100 == 0 or bn == 1 or bn == total_b:
        el = time.time() - t1
        sp = i / el if el > 0 else 0
        eta = (len(texts) - i) / sp / 60 if sp > 0 else 0
        print("  {}/{} | {:.0f}/s | ETA {:.0f}m".format(bn, total_b, sp, eta))
    inputs = tokenizer(texts[i:i+BATCH_SIZE], padding=True, truncation=True,
                       max_length=512, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model(**inputs)
    all_emb.append(out.last_hidden_state[:, 0, :].cpu().numpy())

embeddings = np.vstack(all_emb).astype(np.float32)
print("  Shape: {}, {:.0f} phut".format(embeddings.shape, (time.time()-t1)/60))

print("\n[4/6] Build FAISS index...")
import faiss
faiss.normalize_L2(embeddings)
n = embeddings.shape[0]
if n < 100000:
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    idx_type = "IndexFlatIP"
else:
    nlist = min(int(np.sqrt(n)), 4096)
    quantizer = faiss.IndexFlatIP(EMBEDDING_DIM)
    index = faiss.IndexIVFFlat(quantizer, EMBEDDING_DIM, nlist, faiss.METRIC_INNER_PRODUCT)
    index.train(embeddings)
    idx_type = "IndexIVFFlat(nlist={})".format(nlist)
index.add(embeddings)
print("  {} | {} vectors".format(idx_type, index.ntotal))

print("\n[5/6] Test...")
d, idx = index.search(embeddings[0:1], 5)
for r, (dist, ix) in enumerate(zip(d[0], idx[0])):
    row = df_chunks.iloc[ix]
    print("  [{}] {:.4f} | {} | {}...".format(r+1, dist, row["paper_id"], row["chunk_text"][:60]))

print("\n[6/6] Luu GCS...")
faiss.write_index(index, "/tmp/faiss_index.bin")
df_meta = df_chunks[["paper_id","chunk_id","section","chunk_text"]].copy()
df_meta["index_position"] = range(len(df_meta))
df_meta.to_parquet("/tmp/chunk_metadata.parquet", index=False)
config = {"model": MODEL_NAME, "dim": EMBEDDING_DIM, "n": int(n),
          "type": idx_type, "sections": SECTIONS_TO_EMBED}
with open("/tmp/index_config.json", "w") as f: json.dump(config, f)

os.system("gsutil cp /tmp/faiss_index.bin gs://{}/intermediate/faiss_index/".format(BUCKET))
os.system("gsutil cp /tmp/chunk_metadata.parquet gs://{}/intermediate/faiss_index/".format(BUCKET))
os.system("gsutil cp /tmp/index_config.json gs://{}/intermediate/faiss_index/".format(BUCKET))

print("Hoan thanh! {:.0f} phut | {} vectors".format((time.time()-t0)/60, n))
