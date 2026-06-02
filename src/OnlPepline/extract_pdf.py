import fitz


def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)

    page_texts = []
    for page_idx, page in enumerate(doc):
        text = page.get_text("text")
        page_texts.append({
            "page": page_idx + 1,
            "text": text
        })

    raw_text = "\n".join(item["text"] for item in page_texts)

    return {
        "raw_text": raw_text,
        "page_texts": page_texts,
        "page_count": len(page_texts),
        "word_count_raw": len(raw_text.split())
    }