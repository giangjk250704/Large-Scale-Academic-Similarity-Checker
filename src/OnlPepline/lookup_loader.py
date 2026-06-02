import subprocess
import shutil
from pathlib import Path

import pandas as pd

from config.settings import LOCAL_LOOKUP_CACHE, GCS_LOOKUP


def find_gcloud_command():
    """Tìm lệnh gcloud trên Windows/Linux."""
    for cmd in ["gcloud", "gcloud.cmd"]:
        path = shutil.which(cmd)
        if path:
            return path

    raise FileNotFoundError(
        "Không tìm thấy gcloud trong PATH. "
        "Hãy mở PowerShell mới hoặc kiểm tra Google Cloud CLI."
    )


def normalize_candidate_id(pid):
    """
    Chuẩn hóa candidate id:
    arxiv_0704.0397.pdf -> 0704.0397
    """
    pid = str(pid).strip()
    pid = pid.replace("arxiv_", "")
    pid = pid.replace(".pdf", "")
    return pid


def get_pid_prefix(pid_norm):
    """
    Lấy pid_prefix từ pid_norm.
    0704.0397 -> 0704
    """
    return pid_norm[:4]


def download_lookup_partition_if_needed(pid_prefix):
    """
    Tải partition online_paper_lookup/pid_prefix=xxxx về local nếu chưa có.
    """
    local_partition_dir = LOCAL_LOOKUP_CACHE / f"pid_prefix={pid_prefix}"

    if local_partition_dir.exists():
        parquet_files = list(local_partition_dir.glob("*.parquet"))
        if parquet_files:
            return local_partition_dir

    local_partition_dir.mkdir(parents=True, exist_ok=True)

    gcloud_cmd = find_gcloud_command()

    gcs_partition_path = f"{GCS_LOOKUP.rstrip('/')}/pid_prefix={pid_prefix}/"

    cmd = [
        gcloud_cmd,
        "storage",
        "cp",
        "--recursive",
        gcs_partition_path,
        str(local_partition_dir)
    ]

    print("Downloading lookup partition:")
    print("From:", gcs_partition_path)
    print("To:", local_partition_dir)

    subprocess.run(cmd, check=True)

    return local_partition_dir


def read_local_parquet_partition(local_partition_dir):
    """
    Đọc tất cả parquet trong partition local.
    """
    parquet_files = list(Path(local_partition_dir).rglob("*.parquet"))

    if not parquet_files:
        return pd.DataFrame()

    dfs = []
    for file in parquet_files:
        dfs.append(pd.read_parquet(file))

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)


def get_candidate_rows_local_cache(candidate_ids, max_rows=100):
    """
    Lấy candidate từ online_paper_lookup bằng local cache.

    Cơ chế:
    LSH trả về candidate_ids
    -> chuẩn hóa thành pid_norm
    -> lấy pid_prefix
    -> tải partition pid_prefix nếu chưa có
    -> đọc local parquet
    -> lọc đúng pid_norm
    """
    if not candidate_ids:
        return pd.DataFrame()

    pid_norms = [normalize_candidate_id(pid) for pid in candidate_ids]
    pid_norms = sorted(set(pid_norms))

    pid_prefixes = sorted(set(
        get_pid_prefix(pid)
        for pid in pid_norms
        if len(pid) >= 4
    ))

    all_dfs = []

    for pid_prefix in pid_prefixes:
        local_dir = download_lookup_partition_if_needed(pid_prefix)
        part_df = read_local_parquet_partition(local_dir)

        if not part_df.empty:
            all_dfs.append(part_df)

    if not all_dfs:
        return pd.DataFrame()

    lookup_df = pd.concat(all_dfs, ignore_index=True)

    if "pid_norm" not in lookup_df.columns:
        raise ValueError(
            "Lookup partition không có cột pid_norm. "
            "Hãy kiểm tra bảng gold/online_paper_lookup đã tạo đúng chưa."
        )

    result_df = lookup_df[
        lookup_df["pid_norm"].astype(str).isin(pid_norms)
    ].head(max_rows)

    return result_df