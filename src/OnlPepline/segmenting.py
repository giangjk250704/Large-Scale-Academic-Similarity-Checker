import re

from config.settings import MIN_SEGMENT_WORDS


def extract_introduction(clean_text):
    pattern_intro = r"(?im)^\s*(1\.|i\.|I\.)?\s*introduction\s*$"
    intro_match = re.search(pattern_intro, clean_text)

    if not intro_match:
        return ""

    start = intro_match.end()

    pattern_next = (
        r"(?im)^\s*((2\.|ii\.|II\.)\s+|related work|background|"
        r"preliminaries|method|methodology|conclusion)\b"
    )
    next_match = re.search(pattern_next, clean_text[start:])

    if next_match:
        end = start + next_match.start()
        return clean_text[start:end].strip()

    return clean_text[start:start + 6000].strip()


def split_sections(clean_text, references_text=""):
    introduction = extract_introduction(clean_text)

    if introduction:
        body = clean_text.replace(introduction, " ", 1).strip()
    else:
        body = clean_text

    return {
        "introduction": introduction,
        "body": body,
        "references": references_text
    }


def split_paragraphs(text):
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def has_inline_citation(text):
    patterns = [
        r"\[\d+(,\s*\d+)*\]",
        r"\([A-Z][A-Za-z]+ et al\.,?\s*\d{4}\)",
        r"\([A-Z][A-Za-z]+,\s*\d{4}\)",
    ]
    return any(re.search(p, text) for p in patterns)


def is_quote_text(text):
    text = text.strip()
    return (
        text.startswith('"') and text.endswith('"')
    ) or (
        text.startswith("'") and text.endswith("'")
    )


def create_segments(section_text, section_name, min_words=MIN_SEGMENT_WORDS):
    segments = []
    paragraphs = split_paragraphs(section_text)

    cursor = 0
    for idx, para in enumerate(paragraphs):
        word_count = len(para.split())

        if word_count < min_words:
            continue

        start = section_text.find(para, cursor)
        end = start + len(para)
        cursor = end

        segments.append({
            "segment_id": f"{section_name}_seg_{idx}",
            "section": section_name,
            "text": para,
            "start_char": start,
            "end_char": end,
            "word_count": word_count,
            "is_reference": section_name.lower() == "references",
            "is_quote": is_quote_text(para),
            "near_citation": has_inline_citation(para),
        })

    return segments


def build_input_segments(sections):
    segments = []

    if sections.get("introduction"):
        segments.extend(create_segments(sections["introduction"], "introduction"))

    if sections.get("body"):
        segments.extend(create_segments(sections["body"], "body"))

    return segments