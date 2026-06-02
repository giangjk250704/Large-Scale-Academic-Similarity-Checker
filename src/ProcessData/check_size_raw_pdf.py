from google.cloud import storage
from google.cloud import storage

# 1. Xác thực (Mọi thành viên trong team đều phải chạy lệnh này khi mở Colab)

project_id = 'bigdataptit2026'
bucket_name = 'bigdata-n9-ptit-final'
client = storage.Client(project=project_id)
bucket = client.bucket(bucket_name)
# Thư mục cần tính (lưu ý có dấu gạch chéo / ở cuối)
prefix = 'bronze/raw_pdfs/arxiv/'

print(f"Đang quét dung lượng thư mục: {prefix}")

total_bytes = 0
file_count = 0

# Duyệt qua tất cả các file có chung "tiền tố" (prefix)
blobs = bucket.list_blobs(prefix=prefix)
for blob in blobs:
    total_bytes += blob.size
    file_count += 1

# Quy đổi Byte sang Gigabyte (GB)
total_gb = total_bytes / (1024 ** 3)

print("-" * 40)
print(f" TỔNG KẾT:")
print(f" Số lượng file: {file_count:,} PDFs" )
print(f" Tổng dung lượng: {total_gb:.2f} GB")
print("-" * 40)