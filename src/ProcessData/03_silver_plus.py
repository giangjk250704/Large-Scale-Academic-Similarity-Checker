import re
from pyspark.sql import SparkSession, Row
from pyspark.sql.functions import (
    col, udf, split, element_at, regexp_extract, regexp_replace
)
from pyspark.sql.types import StructType, StructField, StringType

BUCKET = "bigdata-n9-ptit-final"

spark = SparkSession.builder \
    .appName("SilverPlus") \
    .config("spark.sql.shuffle.partitions", "400") \
    .config("spark.sql.autoBroadcastJoinThreshold", "50mb") \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# === DOC 3 NGUON ===
print("[1/6] Doc du lieu...")
df_raw = spark.read.parquet("gs://{}/silver/arxiv_text_parquet/".format(BUCKET)) \
    .select("file_path", col("text").alias("raw_text"))

df_clean = spark.read.parquet("gs://{}/silver/arxiv_cleaned_parquet/".format(BUCKET))

df_meta = spark.read.json(
    "gs://{}/bronze/raw_metadata/arxiv/*/arxiv_full_dump.jsonl".format(BUCKET)
).select("doc_id", "title", "authors", "categories", col("abstract").alias("abstract"))

# === JOIN ===
print("[2/6] Join...")
df_joined = df_clean.join(df_raw, on="file_path", how="left")

df_joined = df_joined.withColumn(
    "join_key",
    regexp_replace(
        regexp_extract(col("file_path"), r"(arxiv_[^/]+)\.pdf$", 1),
        r"v\d+$", ""
    )
)

df_joined = df_joined.join(df_meta, df_joined.join_key == df_meta.doc_id, how="left")

total = df_joined.count()
has_title = df_joined.filter(col("title").isNotNull()).count()
print("  Tong: {} | Co title: {} | NULL: {}".format(total, has_title, total - has_title))

# === TACH SECTIONS ===
print("[3/6] Tach sections...")

def split_sections(text):
    if not text:
        return Row(introduction="", body="")
    intro_match = re.search(
        r'\n(?:1\.?\s*|I\.?\s*)?(?:Introduction|INTRODUCTION)\s*\n', text)
    if not intro_match:
        return Row(introduction="", body=text.strip())
    intro_start = intro_match.end()
    next_sec = re.compile(
        r'\n(?:\d+\.?\s+[A-Z][a-z]|II\.?\s+[A-Z]|(?:RELATED WORK|BACKGROUND|'
        r'METHODOLOGY|PROPOSED METHOD|LITERATURE REVIEW|PRELIMINARIES|'
        r'CONCLUSION|MODEL|EXPERIMENT|RESULTS|DISCUSSION|METHODS)\s*\n)')
    m = next_sec.search(text, intro_start)
    if m:
        return Row(introduction=text[intro_start:m.start()].strip(),
                   body=text[m.start():].strip())
    return Row(introduction=text[intro_start:].strip(), body="")

section_schema = StructType([
    StructField("introduction", StringType(), True),
    StructField("body", StringType(), True),
])
split_udf = udf(split_sections, section_schema)
df_joined = df_joined.withColumn("sections", split_udf(col("clean_text")))

# === CHUAN HOA SCHEMA ===
print("[4/6] Chuan hoa schema...")
df_final = df_joined.select(
    element_at(split(col("file_path"), "/"), -1).alias("paper_id"),
    "file_path", "raw_text", "clean_text",
    "abstract",
    col("sections.introduction").alias("introduction"),
    col("sections.body").alias("body"),
    "word_count_raw", "word_count_clean",
    "title", "authors", "categories", "quality_flag",
)

# === LUU ===
print("[5/6] Dem records...")
total_records = df_final.count()

print("[6/6] Ghi GCS...")
output = "gs://{}/silver/arxiv_silver_plus/".format(BUCKET)
df_final.write.mode("overwrite").parquet(output)

print("Hoan thanh! {} records -> {}".format(total_records, output))
for c in ["title", "authors", "categories", "abstract", "introduction"]:
    nc = df_final.filter(col(c).isNull()).count()
    print("  {}: {}/{} NULL ({:.1f}%)".format(c, nc, total_records, 100.0*nc/total_records))

spark.stop()
