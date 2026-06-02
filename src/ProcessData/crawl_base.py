import json
import requests
import time
from datetime import datetime
from google.cloud import storage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random

PROJECT_ID = 'bigdataptit2026'
BUCKET_NAME = 'bigdata-n9-ptit-final'

SOURCE_JSONL_PATH = "bronze/raw_metadata/arxiv/2026_04_30/arxiv_full_dump.jsonl"

# PHÂN CÔNG CÔNG VIỆC
START_INDEX = 2000001
END_INDEX   = 2100000

# Khởi tạo GCS Client
client = storage.Client(project=PROJECT_ID)
bucket = client.bucket(BUCKET_NAME)
today_str = datetime.now().strftime('%Y_%m_%d')

# Thiết lập Session HTTP
session = requests.Session()
retry = Retry(connect=5, backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

print(f" KHỞI ĐỘNG BỘ CÀO PDF (Task: Dòng {START_INDEX} -> {END_INDEX})...")
print(f" Nguồn đọc Metadata: gs://{BUCKET_NAME}/{SOURCE_JSONL_PATH}")
print(f" Đích lưu PDF: gs://{BUCKET_NAME}/bronze/raw_pdfs/arxiv/")
print("-" * 60)

# --- 2. HÀM TẢI VÀ ĐẨY THẲNG LÊN GCS
def download_pdf_to_gcs(doc_id, pdf_url):
    """Trả về 1 trong 3 trạng thái: 'SKIPPED', 'SUCCESS', 'ERROR'"""
    destination_blob_name = f"bronze/raw_pdfs/arxiv/{doc_id}.pdf"
    blob = bucket.blob(destination_blob_name)

    # KIỂM TRA CHỐNG TRÙNG LẶP (RESUME)
    if blob.exists():
        return "SKIPPED"

    try:
        response = session.get(pdf_url, headers=headers, timeout=30)

        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            blob.upload_from_string(response.content, content_type='application/pdf')
            return "SUCCESS"
        else:
            print(f"\n Lỗi tải {doc_id}: HTTP {response.status_code}")
            return "ERROR"

    except Exception as e:
        print(f"\n Văng lỗi mạng tại {doc_id}: {e}")
        return "ERROR"

# 3.ĐỌC LUỒNG TỪ GCS
success_count = 0
skipped_count = 0
error_count = 0
total_task = END_INDEX - START_INDEX

source_blob = bucket.blob(SOURCE_JSONL_PATH)

print("\n Đang kết nối tới file trên GCS...")
with source_blob.open("r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i < START_INDEX:
            continue
        if i >= END_INDEX:
            print(f"\n Đã hoàn thành khối lượng công việc được giao (Đến dòng {END_INDEX}).")
            break

        metadata = json.loads(line)
        doc_id = metadata['doc_id']
        pdf_url = metadata.get('pdf_url', '')

        if not pdf_url:
            continue

        # Tiến hành xử lý tải
        status = download_pdf_to_gcs(doc_id, pdf_url)

        current_relative_idx = i - START_INDEX + 1

        # Cập nhật thống kê và in tiến độ
        if status == "SKIPPED":
            skipped_count += 1
            # In đè lên cùng 1 dòng để màn hình log đỡ bị trôi
            print(f"\r⏭ [Tiến độ: {current_relative_idx}/{total_task}] - Bỏ qua: {doc_id} (Đã có sẵn)", end="", flush=True)

        elif status == "SUCCESS":
            success_count += 1
            print(f"\n [Tiến độ: {current_relative_idx}/{total_task}] - Đã tải mới: {doc_id}")
            delay = random.uniform(0.5, 1.5)
            time.sleep(delay)
        elif status == "ERROR":
            error_count += 1
            print(f" [Tiến độ: {current_relative_idx}/{total_task}] - Thất bại: {doc_id}")
            delay = random.uniform(0.5, 1.5)
            time.sleep(delay)

# --- 4. TỔNG KẾT BÁO CÁO ---
print("\n\n" + "="*40)
print(" BÁO CÁO TIẾN ĐỘ TASK")
print("="*40)
print(f"Dải dữ liệu: Từ {START_INDEX} đến {END_INDEX}")
print(f" Tải mới thành công : {success_count} files")
print(f" Bỏ qua (Đã có sẵn): {skipped_count} files")
print(f" Lỗi / Thất bại     : {error_count} files")
print("="*40)