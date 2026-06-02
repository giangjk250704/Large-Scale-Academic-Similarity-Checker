import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.pipeline import run_pipeline
from src.report_html import generate_html_report
from config.settings import REPORT_DIR


def make_json_serializable(obj):
    """Chuyển object về dạng ghi được JSON."""
    try:
        import numpy as np

        if isinstance(obj, (np.integer,)):
            return int(obj)

        if isinstance(obj, (np.floating,)):
            return float(obj)

        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
    except Exception:
        pass

    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]

    return obj


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_check.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    report = run_pipeline(pdf_path)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    output_json = REPORT_DIR / f"{pdf_path.stem}_similarity_report.json"
    output_html = REPORT_DIR / f"{pdf_path.stem}_similarity_report.html"

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(
            make_json_serializable(report),
            f,
            ensure_ascii=False,
            indent=2
        )

    generate_html_report(report, output_html)

    print("Overall Similarity:", round(report["overall_similarity"], 2), "%")
    print("Risk Level:", report["risk_level"])
    print("Candidates:", report["candidate_count"])
    print("Matches:", report["match_count"])
    print("JSON report saved:", output_json)
    print("HTML report saved:", output_html)


if __name__ == "__main__":
    main()