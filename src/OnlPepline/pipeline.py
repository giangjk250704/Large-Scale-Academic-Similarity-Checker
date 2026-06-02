from datetime import datetime

from src.extract_pdf import extract_text_from_pdf
from src.clean_text import clean_text_pipeline
from src.segmenting import split_sections, build_input_segments, create_segments
from src.minhash_lsh import (
    load_lsh_index,
    build_query_text_for_lsh,
    query_lsh_candidates,
)
from src.lookup_loader import get_candidate_rows_local_cache
from src.matching import find_matches
from src.filters import (
    apply_citation_exclusion,
    compute_filter_summary,
    compute_filter_word_summary,
)
from src.scoring import (
    compute_similarity_score,
    compute_source_contribution,
    get_risk_level,
)
from config.settings import MAX_CANDIDATES


def build_source_segments_from_candidates(candidate_df):
    all_segments = []

    for _, row in candidate_df.iterrows():
        paper_id = row.get("paper_id", "")
        title = row.get("title", "")

        intro = row.get("introduction", "")
        body = row.get("body", "")
        clean_text = row.get("clean_text", "")

        if not isinstance(body, str) or not body.strip():
            body = clean_text

        sections = {
            "introduction": intro if isinstance(intro, str) else "",
            "body": body if isinstance(body, str) else "",
        }

        for section_name, section_text in sections.items():
            if not section_text.strip():
                continue

            segments = create_segments(section_text, section_name)

            for seg in segments:
                seg["paper_id"] = paper_id
                seg["title"] = title

            all_segments.extend(segments)

    import pandas as pd
    return pd.DataFrame(all_segments)


def run_pipeline(pdf_path):
    lsh = load_lsh_index()

    extract_result = extract_text_from_pdf(pdf_path)

    clean_result = clean_text_pipeline(extract_result["raw_text"])
    clean_text = clean_result["clean_text"]
    references_text = clean_result["references_text"]

    sections = split_sections(clean_text, references_text)
    input_segments = build_input_segments(sections)

    query_text = build_query_text_for_lsh(clean_text, sections)
    candidate_ids, _ = query_lsh_candidates(query_text, lsh, max_candidates=MAX_CANDIDATES)

    candidate_df = get_candidate_rows_local_cache(candidate_ids, max_rows=MAX_CANDIDATES)
    source_segments_df = build_source_segments_from_candidates(candidate_df)

    raw_matches = find_matches(input_segments, source_segments_df)
    checked_matches = apply_citation_exclusion(raw_matches, references_text)

    score_info = compute_similarity_score(clean_text, checked_matches)
    top_sources = compute_source_contribution(clean_text, checked_matches)

    report = {
        "file_path": str(pdf_path),
        "created_at": datetime.now().isoformat(),
        "quality_flag": clean_result["quality_flag"],
        "page_count": extract_result["page_count"],
        "word_count_raw": extract_result["word_count_raw"],
        "word_count_clean": clean_result["word_count_clean"],
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_rows_loaded": len(candidate_df),
        "source_segment_count": len(source_segments_df),
        "input_segment_count": len(input_segments),
        "match_count": len(checked_matches),
        "total_words": score_info["total_words"],
        "matched_words": score_info["matched_words"],
        "overall_similarity": score_info["overall_similarity"],
        "risk_level": get_risk_level(score_info["overall_similarity"]),
        "top_sources": top_sources,
        "matches": checked_matches,
    }

    return report