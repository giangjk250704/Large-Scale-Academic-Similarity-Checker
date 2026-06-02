from rapidfuzz import fuzz

from config.settings import SHINGLE_K, SMALL_MATCH_WORDS, NGRAM_THRESHOLD, FUZZY_THRESHOLD
from src.minhash_lsh import tokenize_words_offline_style


def get_word_shingles_for_matching(text, k=SHINGLE_K):
    words = tokenize_words_offline_style(text)

    if len(words) < k:
        return set()

    return {
        " ".join(words[i:i + k])
        for i in range(len(words) - k + 1)
    }


def exact_match(a, b):
    norm_a = " ".join(a.lower().split())
    norm_b = " ".join(b.lower().split())
    return norm_a == norm_b


def ngram_overlap(a, b, k=SHINGLE_K):
    A = get_word_shingles_for_matching(a, k)
    B = get_word_shingles_for_matching(b, k)

    if not A:
        return 0.0

    return len(A & B) / len(A)


def fuzzy_ratio(a, b):
    return fuzz.ratio(a, b) / 100.0


def compare_segments(input_seg, source_seg):
    a = input_seg["text"]
    b = source_seg["text"]

    len_a = len(a.split())
    len_b = len(b.split())

    if len_a < SMALL_MATCH_WORDS or len_b < SMALL_MATCH_WORDS:
        return None

    length_ratio = max(len_a, len_b) / max(1, min(len_a, len_b))
    if length_ratio > 3:
        return None

    is_exact = exact_match(a, b)
    overlap = ngram_overlap(a, b)
    fuzzy = fuzzy_ratio(a, b)

    if is_exact:
        match_type = "exact"
        score = 1.0
    elif overlap >= NGRAM_THRESHOLD:
        match_type = "ngram"
        score = overlap
    elif fuzzy >= FUZZY_THRESHOLD:
        match_type = "fuzzy"
        score = fuzzy
    else:
        return None

    return {
        "input_segment_id": input_seg["segment_id"],
        "input_section": input_seg["section"],
        "source_paper_id": source_seg.get("paper_id", ""),
        "source_title": source_seg.get("title", ""),
        "source_segment_id": source_seg.get("segment_id", ""),
        "source_section": source_seg.get("section", ""),
        "match_type": match_type,
        "match_score": score,
        "ngram_overlap": overlap,
        "fuzzy_ratio": fuzzy,
        "input_text": a,
        "source_text": b,
        "input_start": input_seg["start_char"],
        "input_end": input_seg["end_char"],
        "word_count": len_a,
        "input_is_quote": input_seg.get("is_quote", False),
        "input_near_citation": input_seg.get("near_citation", False),
    }


def find_matches(input_segments, source_segments_df):
    matches = []

    if source_segments_df.empty:
        return matches

    source_records = source_segments_df.to_dict("records")

    for input_seg in input_segments:
        for source_seg in source_records:
            match = compare_segments(input_seg, source_seg)
            if match is not None:
                matches.append(match)

    return matches