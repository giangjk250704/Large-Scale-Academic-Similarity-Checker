"""
01_extract_text.py - Bóc text từ PDF (Tối ưu cho VM, Chống sập mạng)
Input:  gs://BUCKET/bronze/raw_pdfs/arxiv/
Output: gs://BUCKET/silver/arxiv_text_parquet/
"""

import fitz
import pyarrow as pa
import pyarrow.parquet as pq
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from google.cloud import storage
from io import BytesIO
import os, glob, time, shutil

# === CẤU HÌNH ===
PROJECT = "bigdataptit2026"
BUCKET_NAME = "bigdata-n9-ptit-final"
PDF_PREFIX = "bronze/raw_pdfs/arxiv/"
OUTPUT_PREFIX = "silver/arxiv_text_parquet/"
LOCAL_DIR = "/tmp/pdfs_batch/"

DOWNLOAD_BATCH = 10000   # Tải 10.000 file mỗi mẻ (Tránh tràn đĩa)
PARQUET_BATCH = 5000     # Gom 5.000 file vào 1 file Parquet (Chuẩn Big Data)
MAX_WORKERS = os.cpu_count()  # Lấy full số lõi CPU của máy ảo

fitz.TOOLS.mupdf_display_errors(False)
client = storage.Client(project=PROJECT)
bucket = client.bucket(BUCKET_NAME)

# === [1/4] QUÉT DANH SÁCH PDF ===
print("[1/4] Đang quét danh sách PDF trên Bucket...")
t0 = time.time()
all_blobs = list(bucket.list_blobs(prefix=PDF_PREFIX))
pdf_blobs = [b for b in all_blobs if b.name.endswith(".pdf")]
total = len(pdf_blobs)
print("  Tổng cộng: {:,} file PDF".format(total))

# === [2/4] ĐỌC CHECKPOINT (Lấy file đã xử lý) ===
print("[2/4] Đang đọc Checkpoint...")
processed_paths = set()
existing_parts = list(bucket.list_blobs(prefix=OUTPUT_PREFIX))
parquet_blobs = [b for b in existing_parts if b.name.endswith(".parquet")]

if parquet_blobs:
    print("  Đọc {} file parquet cũ để tìm file đã làm...".format(len(parquet_blobs)))
    for i, blob in enumerate(parquet_blobs):
        try:
            buf = BytesIO(blob.download_as_bytes())
            table = pq.read_table(buf, columns=["file_path"])
            for fp in table.column("file_path").to_pylist():
                processed_paths.add(fp)
        except:
            pass
        if (i + 1) % 50 == 0:
            print("    {}/{} file parquet...".format(i + 1, len(parquet_blobs)))

print("  Đã xử lý trước đó: {:,} file".format(len(processed_paths)))

# Lọc bỏ PDF đã xử lý
pending_blobs = []
for b in pdf_blobs:
    fp = "gs://{}/{}".format(BUCKET_NAME, b.name)
    if fp not in processed_paths:
        pending_blobs.append(b)

print("  CÒN LẠI: {:,} file CẦN XỬ LÝ".format(len(pending_blobs)))
print("  (Thời gian quét: {:.0f}s)".format(time.time() - t0))

if not pending_blobs:
    print("\nKhông còn file nào cần xử lý. Hoàn thành!")
    exit()

# === HÀM TRÍCH XUẤT TEXT CHẠY ĐA LÕI CPU ===
def extract_one(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc).strip()
        doc.close()
        wc = len(text.split())
        if wc <= 10:
            return None
        return {
            "filename": os.path.basename(pdf_path),
            "text": text,
            "word_count": wc,
        }
    except:
        return None

# === [3/4] XỬ LÝ THEO TỪNG BATCH ===
print("\n[3/4] BẮT ĐẦU XỬ LÝ...")
t1 = time.time()
part_counter = len(parquet_blobs)  # Đánh số tiếp tục từ file parquet cuối
total_extracted = 0
total_pending = len(pending_blobs)

for dl_start in range(0, total_pending, DOWNLOAD_BATCH):
    dl_batch = pending_blobs[dl_start:dl_start + DOWNLOAD_BATCH]
    dl_end = min(dl_start + DOWNLOAD_BATCH, total_pending)

    # Dọn dẹp & tạo lại thư mục tạm
    if os.path.exists(LOCAL_DIR):
        shutil.rmtree(LOCAL_DIR)
    os.makedirs(LOCAL_DIR, exist_ok=True)

    print("\n  >>> MẺ DOWNLOAD {}-{} / {} <<<".format(dl_start, dl_end, total_pending))
    td = time.time()

    # --- HÀM TẢI BẰNG THREADPOOL (RẤT ỔN ĐỊNH) ---
    def download_blob(blob):
        dest_path = os.path.join(LOCAL_DIR, os.path.basename(blob.name))
        try:
            blob.download_to_filename(dest_path)
            return True
        except Exception:
            return False

    # Dùng 32 luồng mạng để kéo file về máy ảo
    with ThreadPoolExecutor(max_workers=32) as dl_pool:
        dl_results = list(dl_pool.map(download_blob, dl_batch))
    
    success_dls = sum(1 for r in dl_results if r)
    print("  Đã tải thành công: {}/{} file (Mất {:.0f}s)".format(success_dls, len(dl_batch), time.time() - td))

    # Tạo mapping để ghép đường dẫn GCS
    path_map = {b.name.split("/")[-1]: "gs://{}/{}".format(BUCKET_NAME, b.name) for b in dl_batch}

    # Bóc text từ các file PDF vừa tải về
    local_pdfs = sorted(glob.glob(LOCAL_DIR + "*.pdf"))
    print("  Đang bóc text {} file...".format(MAX_WORKERS, len(local_pdfs)))

    for pq_start in range(0, len(local_pdfs), PARQUET_BATCH):
        pq_batch = local_pdfs[pq_start:pq_start + PARQUET_BATCH]

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as ex:
            results = [r for r in ex.map(extract_one, pq_batch) if r]

        if results:
            rows = []
            for r in results:
                gcs_path = path_map.get(r["filename"], "")
                if gcs_path:
                    rows.append({
                        "file_path": gcs_path,
                        "text": r["text"],
                        "word_count": r["word_count"],
                    })

            if rows:
                table = pa.table({
                    "file_path": [r["file_path"] for r in rows],
                    "text": [r["text"] for r in rows],
                    "word_count": [r["word_count"] for r in rows],
                })
                buf = BytesIO()
                pq.write_table(table, buf)
                buf.seek(0)
                
                part_name = "{}part-{:05d}.parquet".format(OUTPUT_PREFIX, part_counter)
                bucket.blob(part_name).upload_from_file(buf, content_type="application/octet-stream")
                part_counter += 1
                total_extracted += len(rows)

    # Dọn sạch ổ cứng sau khi xong 1 mẻ 10.000 file
    shutil.rmtree(LOCAL_DIR, ignore_errors=True)

    # Tính toán tiến độ
    elapsed = time.time() - t1
    done = min(dl_end, total_pending)
    speed = done / elapsed if elapsed > 0 else 0
    eta = (total_pending - done) / speed / 60 if speed > 0 else 0
    print("  Tiến độ: {:,}/{:,} ({:.1f}%) | Tốc độ: {:.0f} file/s | ETA: {:.0f} phút | Đã bóc: {:,} file".format(
        done, total_pending, 100.0 * done / total_pending, speed, eta, total_extracted))

# === [4/4] TỔNG KẾT ===
print("\n[4/4] Dọn dẹp cuối...")
shutil.rmtree(LOCAL_DIR, ignore_errors=True)

total_time = time.time() - t0
print("\n" + "=" * 60)
print("DONEE!")
print("  Tổng PDF gốc:   {:,}".format(total))
print("  Đã làm trước đó:{:,}".format(len(processed_paths)))
print("  Vừa bóc mới:    {:,}".format(total_extracted))
print("  Thời gian chạy: {:.0f} phút".format(total_time / 60))
print("  Đầu ra Parquet: gs://{}/{}".format(BUCKET_NAME, OUTPUT_PREFIX))