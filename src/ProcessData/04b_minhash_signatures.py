"""
04b_minhash_signatures.py - Tao MinHash signatures 
Chay tren: Dataproc Cluster
Submit: gcloud dataproc jobs submit pyspark gs://bigdata-n9-ptit-final/scripts/04b_minhash_signatures.py \
            --cluster=bigdata-n9-ptit --region=asia-southeast1

Output: gs://BUCKET/intermediate/minhash_signatures/ (paper_id, signature[128])
"""

import re as re_module
import hashlib
import random
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, IntegerType

BUCKET = "bigdata-n9-ptit-final"
INPUT = "gs://{}/silver/arxiv_silver_plus/".format(BUCKET)
OUTPUT = "gs://{}/intermediate/minhash_signatures/".format(BUCKET)
SHINGLE_K = 5
NUM_PERM = 128
LARGE_PRIME = 2147483647

# Hash params co dinh
random.seed(42)
HASH_A = [random.randint(1, LARGE_PRIME - 1) for _ in range(NUM_PERM)]
HASH_B = [random.randint(0, LARGE_PRIME - 1) for _ in range(NUM_PERM)]

spark = SparkSession.builder.appName("MinHash_Signatures") \
    .config("spark.sql.shuffle.partitions", "200").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

bc_a = spark.sparkContext.broadcast(HASH_A)
bc_b = spark.sparkContext.broadcast(HASH_B)
bc_p = spark.sparkContext.broadcast(LARGE_PRIME)
bc_k = spark.sparkContext.broadcast(SHINGLE_K)
bc_n = spark.sparkContext.broadcast(NUM_PERM)

print("[1/3] Doc du lieu...")
df = spark.read.parquet(INPUT)
df_text = df.select("paper_id", F.coalesce(
    F.concat_ws(" ", F.col("abstract"), F.col("introduction"), F.col("body")),
    F.col("clean_text")).alias("text")
).filter(F.col("text").isNotNull() & (F.length(F.col("text")) > 200))
print("  {} bai".format(df_text.count()))

print("[2/3] Tinh signatures (song song)...")

@F.udf(ArrayType(IntegerType()))
def compute_sig(text):
    if not text: return None
    k = bc_k.value
    words = re_module.findall(r'\w{2,}', text.lower())
    if len(words) < k: return None
    hashes = set()
    for i in range(len(words) - k + 1):
        s = " ".join(words[i:i+k])
        hashes.add(int(hashlib.md5(s.encode()).hexdigest(), 16) % bc_p.value)
    if not hashes: return None
    a, b, p, n = bc_a.value, bc_b.value, bc_p.value, bc_n.value
    sig = []
    for i in range(n):
        mv = p
        for h in hashes:
            v = (a[i] * h + b[i]) % p
            if v < mv: mv = v
        sig.append(mv)
    return sig

df_sigs = df_text.withColumn("signature", compute_sig("text"))
df_sigs = df_sigs.filter(F.col("signature").isNotNull()).select("paper_id", "signature")
print("  {} signatures".format(df_sigs.count()))

print("[3/3] Luu...")
df_sigs.write.mode("overwrite").parquet(OUTPUT)
spark.stop()
print("Hoan thanh! -> {}".format(OUTPUT))
