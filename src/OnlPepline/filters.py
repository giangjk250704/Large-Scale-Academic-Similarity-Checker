import re

from config.settings import SMALL_MATCH_WORDS


SYMBOL_HEAVY_RATIO = 0.45
MIN_MEANINGFUL_ALPHA_RATIO = 0.35
MAX_SYMBOL_HEAVY_WORDS = 80


def has_inline_citation(text):
    """
    Nhận diện citation inline:
    [1], [1, 2], [1-3], (Smith, 2020), (Smith et al., 2020)
    """
    if not isinstance(text, str):
        return False

    patterns = [
        r"\[\s*\d+(\s*[-,]\s*\d+)*\s*\]",
        r"\([A-Z][A-Za-z\-]+ et al\.,?\s*\d{4}[a-z]?\)",
        r"\([A-Z][A-Za-z\-]+,\s*\d{4}[a-z]?\)",
        r"\([A-Z][A-Za-z\-]+ and [A-Z][A-Za-z\-]+,\s*\d{4}[a-z]?\)",
    ]

    return any(re.search(p, text) for p in patterns)


def normalize_for_reference_match(text):
    """
    Chuẩn hóa references/source để kiểm tra source có được cite không.
    """
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s\.\-:]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def source_is_cited(references_text, source_title="", source_paper_id="", source_url=""):
    """
    Kiểm tra nguồn có xuất hiện trong References/Bibliography không.
    Dựa trên title, arXiv id hoặc URL.
    """
    refs = normalize_for_reference_match(references_text)

    if not refs:
        return False

    title = normalize_for_reference_match(source_title)
    paper_id = str(source_paper_id).lower().strip()
    source_url = str(source_url).lower().strip()

    pid_norm = paper_id.replace("arxiv_", "").replace(".pdf", "").strip()

    # Check title
    if title and len(title) > 20 and title in refs:
        return True

    # Check arXiv id
    if pid_norm and pid_norm in refs:
        return True

    # Check common arXiv formats
    if pid_norm:
        patterns = [
            pid_norm,
            f"arxiv:{pid_norm}",
            f"arxiv {pid_norm}",
            f"https://arxiv.org/abs/{pid_norm}",
            f"https://arxiv.org/pdf/{pid_norm}",
        ]

        for p in patterns:
            if normalize_for_reference_match(p) in refs:
                return True

    # Check URL nếu có
    if source_url and normalize_for_reference_match(source_url) in refs:
        return True

    return False


def is_reference_section(section_name):
    """
    Kiểm tra section có phải References/Bibliography không.
    """
    if not isinstance(section_name, str):
        return False

    section = section_name.lower().strip()

    keywords = [
        "references",
        "bibliography",
        "reference",
        "tài liệu tham khảo",
    ]

    return any(k in section for k in keywords)


def is_reference_like_text(text):
    """
    Nhận diện đoạn giống reference entry.
    Ví dụ:
    [12] Author, Title, Journal, 2020.
    12. Author. Title. Proceedings...
    """
    if not isinstance(text, str):
        return False

    t = text.strip()

    patterns = [
        r"^\[\d+\]\s+.+",
        r"^\d+\.\s+[A-Z].+",
        r".+\bdoi:\s*\S+",
        r".+\barxiv:\s*\d{4}\.\d{4,5}",
        r".+\bjournal\b.+\b\d{4}\b",
        r".+\bproceedings\b.+\b\d{4}\b",
        r".+\bvol\.\s*\d+",
        r".+\bpp\.\s*\d+",
    ]

    return any(re.search(p, t, flags=re.IGNORECASE) for p in patterns)


def is_quote_text(text):
    """
    Kiểm tra đoạn có dạng quote.
    """
    if not isinstance(text, str):
        return False

    t = text.strip()

    if len(t) < 2:
        return False

    quote_pairs = [
        ('"', '"'),
        ("'", "'"),
        ("“", "”"),
        ("‘", "’"),
    ]

    for left, right in quote_pairs:
        if t.startswith(left) and t.endswith(right):
            return True

    return False


def is_metadata_or_boilerplate(text):
    """
    Nhận diện metadata/boilerplate:
    corresponding author, email, funding, copyright, arXiv header...
    """
    if not isinstance(text, str):
        return False

    t = text.lower()

    patterns = [
        r"corresponding author",
        r"email address",
        r"email addresses",
        r"e-mail",
        r"copyright",
        r"all rights reserved",
        r"preprint submitted",
        r"submitted to",
        r"draft version",
        r"this work is supported by",
        r"supported by .* grant",
        r"grant number",
        r"funded by",
        r"acknowledg(e)?ments?",
        r"arxiv:\d{4}\.\d{4,5}",
        r"keywords:",
        r"pacs:",
        r"msc:",
        r"received .* accepted",
        r"available online",
    ]

    return any(re.search(p, t, flags=re.IGNORECASE) for p in patterns)


def symbol_heavy_ratio(text):
    """
    Tỷ lệ ký tự không phải chữ/số/khoảng trắng.
    """
    if not isinstance(text, str) or not text:
        return 0.0

    total = len(text)

    if total == 0:
        return 0.0

    symbol_count = sum(
        1 for ch in text
        if not ch.isalnum() and not ch.isspace()
    )

    return symbol_count / total


def alpha_ratio(text):
    """
    Tỷ lệ chữ cái trong đoạn.
    """
    if not isinstance(text, str) or not text:
        return 0.0

    total = len(text)

    if total == 0:
        return 0.0

    alpha_count = sum(1 for ch in text if ch.isalpha())

    return alpha_count / total


def is_symbol_heavy_short_formula(text, word_count):
    """
    Loại các đoạn ngắn nhiều ký hiệu/công thức.
    """
    sym_ratio = symbol_heavy_ratio(text)
    a_ratio = alpha_ratio(text)

    return (
        word_count <= MAX_SYMBOL_HEAVY_WORDS
        and sym_ratio >= SYMBOL_HEAVY_RATIO
        and a_ratio < MIN_MEANINGFUL_ALPHA_RATIO
    )


def classify_match_exclusion(match, references_text):
    """
    Gán trạng thái VALID / EXCLUDED cho một match.
    """
    reasons = []

    input_text = match.get("input_text", "")
    source_text = match.get("source_text", "")

    input_section = match.get("input_section", "")
    source_section = match.get("source_section", "")

    word_count = int(match.get("word_count", 0))

    source_title = match.get("source_title", "")
    source_paper_id = match.get("source_paper_id", "")
    source_url = match.get("source_url", "")

    inline_cited = (
        bool(match.get("input_near_citation", False))
        or has_inline_citation(input_text)
    )

    quoted = (
        bool(match.get("input_is_quote", False))
        or is_quote_text(input_text)
    )

    source_cited = source_is_cited(
        references_text=references_text,
        source_title=source_title,
        source_paper_id=source_paper_id,
        source_url=source_url,
    )

    # 1. Small match
    if word_count < SMALL_MATCH_WORDS:
        reasons.append("small_match")

    # 2. References / Bibliography
    if is_reference_section(input_section) or is_reference_section(source_section):
        reasons.append("reference_section")

    if is_reference_like_text(input_text):
        reasons.append("reference_like_text")

    # 3. Quote có citation
    if quoted and (inline_cited or source_cited):
        reasons.append("quoted_and_cited")

    # 4. Metadata / boilerplate
    if is_metadata_or_boilerplate(input_text) or is_metadata_or_boilerplate(source_text):
        reasons.append("metadata_or_boilerplate")

    # 5. Symbol-heavy formula
    if is_symbol_heavy_short_formula(input_text, word_count):
        reasons.append("symbol_heavy_short_formula")

    excluded = len(reasons) > 0

    # Hệ số hỗ trợ diễn giải rủi ro, không dùng để loại trừ trực tiếp
    risk_modifier = 1.0

    if source_cited:
        risk_modifier *= 0.70

    if inline_cited:
        risk_modifier *= 0.75

    if quoted:
        risk_modifier *= 0.60

    return {
        "excluded": excluded,
        "exclusion_reasons": reasons,
        "source_cited": source_cited,
        "inline_cited": inline_cited,
        "quoted": quoted,
        "risk_modifier": risk_modifier,
    }


def apply_citation_exclusion(matches, references_text):
    """
    Citation & Exclusion Check kiểu Turnitin-style.

    VALID:
        được tính vào Overall Similarity.

    EXCLUDED:
        không tính vào Overall Similarity nhưng vẫn hiển thị trong report.
    """
    processed = []

    for m in matches:
        info = classify_match_exclusion(m, references_text)

        m["excluded"] = info["excluded"]
        m["exclusion_reasons"] = info["exclusion_reasons"]
        m["source_cited"] = info["source_cited"]
        m["inline_cited"] = info["inline_cited"]
        m["quoted"] = info["quoted"]
        m["risk_modifier"] = info["risk_modifier"]
        m["validity"] = "EXCLUDED" if info["excluded"] else "VALID"

        processed.append(m)

    return processed


def compute_filter_summary(matches):
    """
    Thống kê VALID / EXCLUDED match và lý do loại trừ.
    """
    total_matches = len(matches)
    valid_matches = [m for m in matches if not m.get("excluded", False)]
    excluded_matches = [m for m in matches if m.get("excluded", False)]

    reason_counts = {}

    for m in excluded_matches:
        for reason in m.get("exclusion_reasons", []):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "total_matches": total_matches,
        "valid_matches": len(valid_matches),
        "excluded_matches": len(excluded_matches),
        "exclusion_reason_counts": reason_counts,
    }


def compute_filter_word_summary(matches):
    """
    Đếm số từ của valid/excluded matches theo word_count thô.
    Lưu ý: đây là thống kê thô, không gộp interval.
    """
    valid_words_raw = 0
    excluded_words_raw = 0

    for m in matches:
        wc = int(m.get("word_count", 0))

        if m.get("excluded", False):
            excluded_words_raw += wc
        else:
            valid_words_raw += wc

    return {
        "valid_match_words_raw": valid_words_raw,
        "excluded_match_words_raw": excluded_words_raw,
    }