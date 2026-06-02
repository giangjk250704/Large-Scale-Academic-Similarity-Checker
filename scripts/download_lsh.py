import subprocess
import shutil
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config.settings import GCS_LSH_INDEX, LOCAL_LSH_INDEX


def find_gcloud_command():
    """Tìm lệnh gcloud trên Windows/Linux."""
    for cmd in ["gcloud", "gcloud.cmd"]:
        path = shutil.which(cmd)
        if path:
            return path

    raise FileNotFoundError(
        "Không tìm thấy gcloud trong PATH. "
        "Hãy mở PowerShell mới sau khi cài Google Cloud CLI."
    )


def main():
    LOCAL_LSH_INDEX.parent.mkdir(parents=True, exist_ok=True)

    if LOCAL_LSH_INDEX.exists():
        print("LSH index already exists:", LOCAL_LSH_INDEX)
        return

    gcloud_cmd = find_gcloud_command()

    cmd = [
        gcloud_cmd,
        "storage",
        "cp",
        GCS_LSH_INDEX,
        str(LOCAL_LSH_INDEX)
    ]

    print("Downloading LSH index...")
    print("From:", GCS_LSH_INDEX)
    print("To:", LOCAL_LSH_INDEX)
    print("Using:", gcloud_cmd)

    subprocess.run(cmd, check=True)

    print("Done:", LOCAL_LSH_INDEX)


if __name__ == "__main__":
    main()