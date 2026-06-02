"""
04e_chunk_export.py - Export text chunks (PySpark)
Chay tren: Dataproc Cluster
Submit: gcloud dataproc jobs submit pyspark gs://bigdata-n9-ptit-final/scripts/04e_chunk_export.py \
            --cluster=bigdata-n9-ptit --region=asia-southeast1

Input:  gs://BUCKET/silver/arxiv_silver_plus/
Output: gs://BUCKET/intermediate/chunks_parquet/
Schema: paper_id, chunk_id, section, chunk_text, chunk_uid
"""

import re as re_module
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StructType, StructField, StringType, IntegerType

BUCKET = "bigdata-n9-ptit-final"
INPUT = "gs://{}/silver/arxiv_silver_plus/".format(BUCKET)
OUTPUT = "gs://{}/intermediate/chunks_parquet/".format(BUCKET)
CHUNK_SIZE = 4

spark = SparkSession.builder.appName("Chunk_Export") \
    .config("spark.sql.shuffle.partitions", "200").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

print("[1/3] Doc du lieu...")
df = spark.read.parquet(INPUT)
print("  {} bai".format(df.count()))

chunk_schema = ArrayType(StructType([
    StructField("chunk_id", IntegerType(), False),
    StructField("section", StringType(), True),
    StructField("chunk_text", StringType(), False),
]))

@F.udf(chunk_schema)
def create_chunks(abstract, introduction, body):
    chunks, cid = [], 0
    for sec, text in [("abstract", abstract or ""), ("introduction", introduction or ""), ("body", body or "")]:
        if len(text.strip()) < 50: continue
        sents = [s.strip() for s in re_module.split(r'(?<=[.!?])\s+', text.strip()) if len(s.strip()) >= 20]
        for i in range(0, len(sents), CHUNK_SIZE):
            ct = " ".join(sents[i:i+CHUNK_SIZE]).strip()
            if len(ct) >= 50:
                chunks.append({"chunk_id": cid, "section": sec, "chunk_text": ct})
                cid += 1
    return chunks

print("[2/3] Tao chunks...")
df_out = df.select("paper_id", "abstract", "introduction", "body") \
    .withColumn("chunks", create_chunks("abstract", "introduction", "body"))
df_out = df_out.select("paper_id", F.explode("chunks").alias("c"))
df_out = df_out.select("paper_id", F.col("c.chunk_id").alias("chunk_id"),
    F.col("c.section").alias("section"), F.col("c.chunk_text").alias("chunk_text"))
df_out = df_out.withColumn("chunk_uid", F.concat_ws("_", "paper_id", F.col("chunk_id").cast("string")))

total = df_out.count()
print("  {} chunks".format(total))
df_out.groupBy("section").count().show()

print("[3/3] Luu...")
df_out.write.mode("overwrite").parquet(OUTPUT)
spark.stop()
print("Hoan thanh! {} chunks -> {}".format(total, OUTPUT))
