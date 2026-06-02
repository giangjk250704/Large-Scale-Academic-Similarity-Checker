import re
import unicodedata


def remove_arxiv_header(text):
    pattern = r"arXiv:\d{4}\.\d{4,5}v?\d*\s*\[[^\]]+\]\s*\d{1,2}\s+\w+\s+\d{4}"
    return re.sub(pattern, " ", text, flags=re.IGNORECASE)


def remove_journal_metadata(text):
    patterns = [
        r"Preprint submitted to.*",
        r"Draft version.*",
        r"Submitted to.*",
        r"Copyright.*",
    ]

    for pattern in patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    return text


def split_references(text):
    lower_text = text.lower()
    search_start = int(len(text) * 0.55)

    candidates = []
    for marker in ["references", "bibliography"]:
        idx = lower_text.find(marker, search_start)
        if idx != -1:
            candidates.append(idx)

    if not candidates:
        return text, ""

    ref_start = min(candidates)
    return text[:ref_start], text[ref_start:]


def remove_page_numbers(text):
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
    text = re.sub(r"page\s+\d+\s+of\s+\d+", " ", text, flags=re.IGNORECASE)
    return text


def fix_ligatures(text):
    replacements = {
        "ﬀ": "ff",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "st",
    }

    for src, dst in replacements.items():
        text = text.replace(src, dst)

    return text


def clean_text_pipeline(raw_text):
    text = raw_text

    text = remove_arxiv_header(text)
    text = remove_journal_metadata(text)
    text, references_text = split_references(text)
    text = remove_page_numbers(text)
    text = fix_ligatures(text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    word_count_clean = len(text.split())

    if word_count_clean >= 500:
        quality_flag = "ok"
    elif word_count_clean >= 300:
        quality_flag = "low_quality"
    else:
        quality_flag = "empty"

    return {
        "clean_text": text,
        "references_text": references_text,
        "word_count_clean": word_count_clean,
        "quality_flag": quality_flag,
        "has_references": bool(references_text.strip())
    }