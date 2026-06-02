# ArXiv Large-Scale Academic Similarity Checker

Hệ thống kiểm tra tương đồng văn bản học thuật trên tập dữ liệu ArXiv quy mô lớn.

Dự án này xây dựng một pipeline xử lý tài liệu PDF đầu vào, trích xuất và làm sạch văn bản, truy vấn chỉ mục MinHash LSH để tìm các tài liệu ứng viên trong kho ArXiv, sau đó thực hiện so khớp chi tiết bằng Exact Matching, N-gram Overlap và Fuzzy Matching. Kết quả cuối cùng là báo cáo HTML hiển thị mức độ tương đồng, nguồn bị khớp và các đoạn văn tương đồng cụ thể.

Hệ thống không tự động kết luận một tài liệu là đạo văn. Kết quả đầu ra là báo cáo tương đồng văn bản nhằm hỗ trợ người dùng hoặc người chấm kiểm tra, đối chiếu và đánh giá lại theo ngữ cảnh học thuật.

---

## 1. Tổng quan dự án

Trong môi trường học thuật, số lượng bài báo khoa học tăng rất nhanh, đặc biệt trên các kho lưu trữ mở như ArXiv. Việc kiểm tra thủ công một tài liệu có sao chép hoặc tái sử dụng nội dung từ tài liệu khác hay không trở nên khó khăn khi dữ liệu đạt đến hàng trăm nghìn hoặc hàng triệu văn bản.

Dự án này giải quyết bài toán kiểm tra tương đồng văn bản trên dữ liệu lớn bằng cách kết hợp:

- Data Lake lưu trữ dữ liệu ArXiv.
- MinHash LSH để tìm nhanh tài liệu ứng viên.
- Exact Matching để phát hiện đoạn copy nguyên văn.
- N-gram Overlap để phát hiện đoạn copy có chỉnh sửa nhẹ.
- Fuzzy Matching để phát hiện thay đổi nhỏ về ký tự, dấu câu hoặc định dạng.
- Citation & Exclusion Check để loại trừ các đoạn không nên tính vào điểm chính.
- HTML Report để hiển thị kết quả trực quan.

Luồng xử lý tổng quát:

```text
PDF input
→ Trích xuất văn bản
→ Làm sạch văn bản
→ Tách tài liệu thành các đoạn
→ Truy vấn MinHash LSH
→ Lấy tài liệu ứng viên từ Gold lookup
→ So khớp Exact / N-gram / Fuzzy
→ Lọc References, quote, metadata, small matches
→ Tính Overall Similarity
→ Sinh báo cáo HTML
```

---

## 2. Thông tin dự án

- **Đề tài:** Hệ thống phát hiện đạo văn trên tập dữ liệu quy mô lớn
- **Tập dữ liệu:** ArXiv scientific papers
- **Quy mô xử lý:** hơn 300.000 bài báo, khoảng 438GB PDF và khoảng 4GB metadata JSONL
- **Hạ tầng lưu trữ:** Google Cloud Storage
- **Bucket:** `bigdata-n9-ptit-final`
- **Project GCP:** `bigdataptit2026`
- **Học phần:** Phân tích Khai phá Dữ liệu lớn
- **Đơn vị:** Khoa Khoa học Máy tính, Học viện Công nghệ Bưu chính Viễn thông

---

## 3. Mục tiêu hệ thống

Hệ thống được xây dựng nhằm hỗ trợ kiểm tra các dạng tương đồng văn bản học thuật sau:

1. **Copy nguyên văn:** tài liệu đầu vào chứa đoạn văn trùng hoàn toàn với nguồn đã lập chỉ mục.
2. **Copy có chỉnh sửa nhẹ:** nội dung bị thay đổi một vài từ, dấu câu hoặc định dạng nhưng vẫn giữ cấu trúc gần giống nguồn.
3. **Near-duplicate document:** bài upload gần như là bản sao của một bài báo đã có trong kho dữ liệu.
4. **Trùng lặp do quote, References hoặc metadata:** được nhận diện và loại trừ khỏi similarity chính nếu không nên tính vào điểm.
5. **Tương đồng cú pháp ở cấp đoạn:** hệ thống chỉ ra chính xác đoạn input nào match với đoạn source nào.

Phiên bản hiện tại tập trung vào **textual similarity** và **near-copy detection**. Các dạng paraphrase sâu hoặc đạo văn ý tưởng có thể được mở rộng bằng semantic retrieval trong các phiên bản sau.

---

## 4. Ý tưởng chính

Nếu so sánh trực tiếp một tài liệu đầu vào với toàn bộ kho dữ liệu ArXiv, chi phí tính toán sẽ rất lớn. Với `N` tài liệu trong kho, việc so sánh brute-force từng cặp văn bản không phù hợp cho dữ liệu lớn.

Vì vậy, hệ thống chia bài toán thành hai giai đoạn:

### 5.1. Candidate Retrieval

Dùng **MinHash LSH** để tìm nhanh các tài liệu có khả năng tương đồng cao với tài liệu đầu vào.

LSH chỉ trả về danh sách `paper_id` ứng viên, ví dụ:

```text
arxiv_0704.0043.pdf
arxiv_0812.1234.pdf
```

LSH không trả về đoạn văn bị trùng và cũng không kết luận tài liệu có vi phạm hay không. Nó chỉ giúp giảm không gian tìm kiếm từ hàng trăm nghìn tài liệu xuống còn một số lượng nhỏ candidate.

### 5.2. Detailed Matching

Sau khi có candidate, hệ thống thực hiện so khớp chi tiết ở cấp đoạn văn bằng ba kỹ thuật:

| Kỹ thuật | Mục tiêu |
|---|---|
| Exact Matching | Phát hiện đoạn copy nguyên văn |
| N-gram Overlap | Phát hiện copy dài có chỉnh sửa nhẹ |
| Fuzzy Matching | Phát hiện thay đổi nhỏ về ký tự, dấu câu, định dạng |

Sau đó, các match được đưa qua bộ lọc Citation & Exclusion Check để xác định match nào được tính vào similarity chính.

---

## 6. Kiến trúc pipeline

```text
PDF input
│
├── extract_pdf.py
│   └── Extract raw text from PDF
│
├── clean_text.py
│   └── Clean text and split References
│
├── segmenting.py
│   └── Split document into input segments
│
├── minhash_lsh.py
│   └── Generate MinHash query and query LSH index
│
├── lookup_loader.py
│   └── Load candidate rows from Gold lookup on GCS
│
├── matching.py
│   └── Exact / N-gram / Fuzzy matching
│
├── filters.py
│   └── Citation & Exclusion Check
│
├── scoring.py
│   └── Compute Overall Similarity and Source Contribution
│
└── report_html.py
    └── Generate detailed HTML Similarity Report
```

---

## 7. Cấu trúc thư mục

```text
plagiarism_checker/
│
├── config/
│   └── settings.py
│
├── data/
│   ├── input_pdfs/
│   ├── reports/
│   └── cache/
│       ├── lsh_index/
│       └── lookup_partitions/
│
├── scripts/
│   ├── download_lsh.py
│   └── run_check.py
│
├── src/
│   ├── clean_text.py
│   ├── extract_pdf.py
│   ├── filters.py
│   ├── lookup_loader.py
│   ├── matching.py
│   ├── minhash_lsh.py
│   ├── pipeline.py
│   ├── report_html.py
│   ├── scoring.py
│   └── segmenting.py
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 8. Công dụng từng file source

| File | Chức năng |
|---|---|
| `extract_pdf.py` | Đọc file PDF và trích xuất text thô theo từng trang |
| `clean_text.py` | Làm sạch text, xóa nhiễu học thuật, tách References |
| `segmenting.py` | Tách document thành introduction/body và tạo các đoạn segment |
| `minhash_lsh.py` | Tạo MinHash signature cho tài liệu input và truy vấn LSH index |
| `lookup_loader.py` | Tải candidate từ Gold lookup trên GCS về local cache |
| `matching.py` | So khớp đoạn bằng Exact, N-gram Overlap và Fuzzy Matching |
| `filters.py` | Loại trừ các match không nên tính điểm chính |
| `scoring.py` | Tính Overall Similarity, Matched Words và Source Contribution |
| `report_html.py` | Sinh báo cáo HTML chi tiết |
| `pipeline.py` | Điều phối toàn bộ quá trình xử lý |

---

## 9. Kiến trúc dữ liệu

Dữ liệu được tổ chức theo mô hình Medallion Architecture.

```text
Bronze
├── raw_metadata/
└── raw_pdfs/

Silver
├── arxiv_text_parquet/
├── arxiv_cleaned_parquet/
└── arxiv_silver_plus/

Gold
├── online_paper_lookup/
├── minhash_signatures/
└── minhash_index/
```

### Bronze Layer

Lưu dữ liệu thô:

- Metadata ArXiv dạng JSONL.
- File PDF gốc tải từ ArXiv.

### Silver Layer

Lưu dữ liệu đã xử lý:

- Text thô trích xuất từ PDF.
- Text đã làm sạch.
- Dataset Silver+ sau khi join raw text, clean text và metadata.

### Gold Layer

Lưu dữ liệu phục vụ truy vấn online:

- `online_paper_lookup/`: bảng lookup theo `paper_id`, partition theo `pid_prefix`.
- `minhash_index/`: LSH index đã build offline.
- `minhash_signatures/`: MinHash signatures của các tài liệu đã lập chỉ mục.

---

## 10. Cài đặt môi trường

### 10.1. Clone repository

```bash
git clone https://github.com/<username>/<repo-name>.git
cd plagiarism_checker
```

### 10.2. Tạo virtual environment

Trên Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Trên Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 10.3. Cài dependencies

```bash
pip install -r requirements.txt
```

Nếu chưa có file `requirements.txt`, có thể dùng:

```text
pymupdf
datasketch
rapidfuzz
pandas
pyarrow
gcsfs
numpy
tqdm
requests
```

---

## 11. Google Cloud Authentication

Hệ thống cần quyền đọc Google Cloud Storage để tải LSH index và lookup partition.

Đăng nhập Google Cloud CLI:

```powershell
gcloud auth login
gcloud config set project bigdataptit2026
gcloud auth application-default login
```

Kiểm tra quyền truy cập bucket:

```powershell
gcloud storage ls gs://bigdata-n9-ptit-final/
```

Nếu lệnh trên liệt kê được dữ liệu, cấu hình GCS đã thành công.

---


Lưu ý quan trọng:

- `NUM_PERM` trong online query phải giống lúc build LSH index.
- `SHINGLE_K` phải giống pipeline offline.
- Cách tạo shingle và hash phải khớp với lúc build index.
- `paper_id` trong LSH phải khớp với `paper_id` trong Gold lookup.

---

## 13. Cách chạy

### 13.1. Tải LSH index về local

Chạy một lần:

```powershell
python scripts\download_lsh.py
```

LSH index sẽ được lưu tại:

```text
data/cache/lsh_index/lsh_index.pkl
```

### 13.2. Đưa PDF cần kiểm tra vào thư mục input

```text
data/input_pdfs/test.pdf
```

### 13.3. Chạy pipeline

```powershell
python scripts\run_check.py data\input_pdfs\test.pdf
```

Hoặc dùng trực tiếp Python trong virtual environment:

```powershell
& D:/bigdatan9-ptit/plagiarism_checker/.venv/Scripts/python.exe `
D:/bigdatan9-ptit/plagiarism_checker/scripts/run_check.py `
D:/bigdatan9-ptit/plagiarism_checker/data/input_pdfs/test.pdf
```

---

## 14. Output

Kết quả được lưu tại:

```text
data/reports/
```

Các file output:

| File | Mô tả |
|---|---|
| `*_similarity_report.json` | Báo cáo dạng JSON |
| `*_similarity_report.html` | Báo cáo HTML trực quan |
| `*_input_highlighted.pdf` | PDF input đã được highlight nếu bật tính năng highlight |

HTML report gồm:

- Overall Similarity
- Risk Level
- Matched Words
- Candidate count
- Top matched sources
- Filter / Exclusion Summary
- Matched passages
- Excluded passages
- Citation status
- Interpretation

---

## 15. Công thức chính

### 15.1. N-gram Overlap

```text
Overlap(input, source) = |Shingles(input) ∩ Shingles(source)| / |Shingles(input)|
```

Công thức này đo tỷ lệ phần văn bản input được bao phủ bởi source.

### 15.2. Overall Similarity

```text
Overall Similarity = Valid Matched Words / Total Words × 100
```

Chỉ các match `VALID` mới được tính vào điểm chính.

### 15.3. Source Contribution

```text
Source Contribution_i = Matched Words From Source_i / Total Words × 100
```

---

## 16. Citation & Exclusion Check

Mỗi match có thể có trạng thái:

```text
VALID
EXCLUDED
```

Chỉ match `VALID` mới được dùng để tính Overall Similarity.

Các lý do loại trừ:

| Reason | Meaning |
|---|---|
| `small_match` | Match quá ngắn, dễ trùng ngẫu nhiên |
| `reference_section` | Match nằm trong References/Bibliography |
| `reference_like_text` | Đoạn giống một mục tài liệu tham khảo |
| `quoted_and_cited` | Đoạn nằm trong quote và có citation |
| `metadata_or_boilerplate` | Metadata như email, funding, copyright |
| `symbol_heavy_short_formula` | Đoạn công thức ngắn chứa nhiều ký hiệu |

Các field được gắn vào từng match:

```text
source_cited
inline_cited
quoted
excluded
exclusion_reasons
validity
```

---

## 17. Diễn giải kết quả

Ví dụ:

```text
Overall Similarity: 91.23%
Matched Words: 8012 / 8782
Risk Level: Very High
Primary Source: arxiv_0704.0043.pdf
```

Cách hiểu đúng:

```text
91.23% số từ trong tài liệu đầu vào có match hợp lệ với nguồn đã lập chỉ mục.
```

Cách hiểu không đúng:

```text
Bài này đạo văn 91.23%.
```

Hệ thống tạo báo cáo tương đồng để hỗ trợ người chấm đánh giá. Similarity cao là dấu hiệu cần kiểm tra, không phải kết luận tuyệt đối.

---

## 18. Trạng thái hiện tại

Phiên bản hiện tại đã hỗ trợ:

- Chạy local trên Windows.
- Tải LSH index từ GCS.
- Cache lookup partition từ GCS về local.
- Query MinHash LSH.
- Exact / N-gram / Fuzzy Matching.
- Citation & Exclusion Check.
- Tính Overall Similarity.
- Tính Source Contribution.
- Sinh JSON report.
- Sinh HTML report.

---

## 19. Hạn chế

- Hệ thống hiện tập trung vào textual similarity và near-copy detection.
- Chưa mạnh với paraphrase sâu hoặc đạo văn ý tưởng.
- Lookup hiện tại partition theo `pid_prefix`, một số partition có thể còn lớn.
- Citation check dựa trên rule-based patterns, chưa phải citation parser hoàn chỉnh.
- Nếu PDF là scan ảnh, cần OCR trước khi extract text.

---

## 20. Hướng phát triển

- Tạo `online_paper_lookup_v2` partition theo `pid_bucket` để lookup nhanh hơn.
- Tạo `source_segments` offline để giảm thời gian segmenting online.
- Highlight trực tiếp đoạn match trên PDF input và PDF nguồn.
- Bổ sung semantic retrieval cho paraphrase mạnh.
- Bổ sung Author Entity Resolution cho self-plagiarism.
- Xây dựng giao diện web upload PDF và xem report.
- Tối ưu matching bằng multiprocessing hoặc inverted index ở cấp segment.

---
