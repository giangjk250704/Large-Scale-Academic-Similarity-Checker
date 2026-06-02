from collections import defaultdict


def merge_intervals(intervals):
    if not intervals:
        return []

    intervals = sorted(intervals)
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]

        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def count_words_in_intervals(text, intervals):
    total = 0

    for start, end in intervals:
        total += len(text[start:end].split())

    return total


def compute_similarity_score(clean_text, matches):
    valid_intervals = []

    for m in matches:
        if not m.get("excluded", False):
            valid_intervals.append((m["input_start"], m["input_end"]))

    merged = merge_intervals(valid_intervals)

    total_words = len(clean_text.split())
    matched_words = count_words_in_intervals(clean_text, merged)

    similarity = matched_words / total_words * 100 if total_words else 0.0

    return {
        "total_words": total_words,
        "matched_words": matched_words,
        "overall_similarity": similarity,
        "matched_intervals": merged
    }


def compute_source_contribution(clean_text, matches):
    total_words = len(clean_text.split())
    source_intervals = defaultdict(list)

    for m in matches:
        if not m.get("excluded", False):
            source_id = m.get("source_paper_id", "")
            source_intervals[source_id].append((m["input_start"], m["input_end"]))

    contributions = []

    for source_id, intervals in source_intervals.items():
        merged = merge_intervals(intervals)
        words = count_words_in_intervals(clean_text, merged)

        sample_match = next(
            m for m in matches
            if m.get("source_paper_id", "") == source_id
        )

        contributions.append({
            "source_paper_id": source_id,
            "source_title": sample_match.get("source_title", ""),
            "matched_words": words,
            "contribution_percent": words / total_words * 100 if total_words else 0
        })

    contributions.sort(key=lambda x: x["contribution_percent"], reverse=True)

    return contributions


def get_risk_level(similarity_score):
    if similarity_score < 10:
        return "Low"
    if similarity_score < 25:
        return "Medium"
    if similarity_score < 40:
        return "High"
    return "Very High"