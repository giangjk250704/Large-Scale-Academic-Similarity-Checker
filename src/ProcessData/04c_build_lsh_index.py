"""
04c_build_lsh_index.py - Build datasketch LSH index

Input:  gs://BUCKET/intermediate/minhash_signatures/
Output: gs://BUCKET/intermediate/minhash_index/
        - lsh_index.pkl, minhashes.pkl, config.json
"""

import os, time, pickle, json
import pandas as pd
import numpy as np
from datasketch import MinHash, MinHashLSH

BUCKET = "bigdata-n9-ptit-final"
SIGS_LOCAL = "/tmp/minhash_sigs/"
OUTPUT_LOCAL = "/tmp/minhash_index/"
GCS_OUTPUT = "gs://{}/intermediate/minhash_index/".format(BUCKET)
NUM_PERM = 128
LSH_THRESHOLD = 0.5

# === [1/4] Download signatures ===
print("[1/4] Download signatures tu GCS...")
t0 = time.time()
os.makedirs(SIGS_LOCAL, exist_ok=True)
os.system("gsutil -m cp 'gs://{}/intermediate/minhash_signatures/*.parquet' {}".format(BUCKET, SIGS_LOCAL))

df = pd.read_parquet(SIGS_LOCAL)
print("  {} bai, {:.0f}s".format(len(df), time.time() - t0))

# === [2/4] Tao MinHash objects ===
print("\n[2/4] Tao MinHash objects...")
t1 = time.time()
minhashes = {}
for i, row in df.iterrows():
    if i % 50000 == 0:
        print("  {}/{}".format(i, len(df)))
    m = MinHash(num_perm=NUM_PERM)
    m.hashvalues = np.array(row["signature"], dtype=np.uint64)
    minhashes[row["paper_id"]] = m
print("  {} objects, {:.0f}s".format(len(minhashes), time.time() - t1))

# === [3/4] Build LSH index ===
print("\n[3/4] Build LSH index (threshold={})...".format(LSH_THRESHOLD))
t2 = time.time()
lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
for pid, mh in minhashes.items():
    lsh.insert(pid, mh)
print("  {:.0f}s".format(time.time() - t2))

# Test
test_pid = list(minhashes.keys())[0]
result = lsh.query(minhashes[test_pid])
print("\n  Test: {} -> {} matches".format(test_pid, len(result)))
for r in sorted(result)[:5]:
    if r != test_pid:
        sim = minhashes[test_pid].jaccard(minhashes[r])
        print("    {} | Jaccard={:.4f}".format(r, sim))

# === [4/4] Save + upload GCS ===
print("\n[4/4] Luu va upload GCS...")
os.makedirs(OUTPUT_LOCAL, exist_ok=True)

lsh_path = os.path.join(OUTPUT_LOCAL, "lsh_index.pkl")
with open(lsh_path, "wb") as f:
    pickle.dump(lsh, f)
print("  lsh_index.pkl: {:.1f} MB".format(os.path.getsize(lsh_path) / 1024 / 1024))

mh_path = os.path.join(OUTPUT_LOCAL, "minhashes.pkl")
with open(mh_path, "wb") as f:
    pickle.dump(minhashes, f)
print("  minhashes.pkl: {:.1f} MB".format(os.path.getsize(mh_path) / 1024 / 1024))

with open(os.path.join(OUTPUT_LOCAL, "config.json"), "w") as f:
    json.dump({"num_perm": NUM_PERM, "threshold": LSH_THRESHOLD, "n_papers": len(minhashes)}, f)

os.system("gsutil -m cp {}* {}".format(OUTPUT_LOCAL, GCS_OUTPUT))

print("\n[HOAN THANH] {:.0f} phut | {} papers -> {}".format(
    (time.time() - t0) / 60, len(minhashes), GCS_OUTPUT))