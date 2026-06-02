from html import escape


def truncate_text(text, max_chars=1200):
    """Cắt ngắn đoạn text để HTML không quá dài."""
    if text is None:
        return ""

    text = str(text)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "..."


def risk_class(risk_level):
    """Map risk level sang CSS class."""
    risk = str(risk_level).lower()

    if "very" in risk or "high" in risk:
        return "high"
    if "medium" in risk:
        return "medium"
    return "low"


def render_top_sources(report):
    """Render bảng nguồn nghi vấn."""
    sources = report.get("top_sources", [])

    rows = ""

    for idx, src in enumerate(sources, start=1):
        contribution = src.get("contribution_percent", 0)
        matched_words = src.get("matched_words", 0)
        paper_id = src.get("source_paper_id", "")
        title = src.get("source_title", "")

        risk = "Very High" if contribution >= 40 else "High" if contribution >= 25 else "Medium" if contribution >= 10 else "Low"
        cls = risk_class(risk)

        arxiv_id = str(paper_id).replace("arxiv_", "").replace(".pdf", "")
        arxiv_abs = f"https://arxiv.org/abs/{arxiv_id}"
        arxiv_pdf = f"https://arxiv.org/pdf/{arxiv_id}"

        rows += f"""
        <tr>
            <td>{idx}</td>
            <td><code>{escape(str(paper_id))}</code></td>
            <td>{escape(str(title))}</td>
            <td class="{cls}">{risk}</td>
            <td>{contribution:.2f}%</td>
            <td>{matched_words}</td>
            <td>
                <a href="{arxiv_abs}" target="_blank">ArXiv</a> |
                <a href="{arxiv_pdf}" target="_blank">PDF</a>
            </td>
        </tr>
        """

    if not rows:
        rows = """
        <tr>
            <td colspan="7">Không có nguồn nghi vấn.</td>
        </tr>
        """

    return f"""
    <h2>1. Các bài báo nghi vấn</h2>
    <table>
        <tr>
            <th>Rank</th>
            <th>Paper ID</th>
            <th>Title</th>
            <th>Risk</th>
            <th>Contribution</th>
            <th>Matched words</th>
            <th>Links</th>
        </tr>
        {rows}
    </table>
    """


def render_filter_summary(report):
    """Render thống kê bộ lọc."""
    filter_summary = report.get("filter_summary", {})
    filter_word_summary = report.get("filter_word_summary", {})

    matches = report.get("matches", [])

    total = filter_summary.get("total_matches", len(matches))
    valid = filter_summary.get(
        "valid_matches",
        len([m for m in matches if not m.get("excluded", False)])
    )
    excluded = filter_summary.get(
        "excluded_matches",
        len([m for m in matches if m.get("excluded", False)])
    )

    reason_counts = filter_summary.get("exclusion_reason_counts", {})

    valid_words_raw = filter_word_summary.get("valid_match_words_raw", 0)
    excluded_words_raw = filter_word_summary.get("excluded_match_words_raw", 0)

    reason_rows = ""

    for reason, count in reason_counts.items():
        reason_rows += f"""
        <tr>
            <td>{escape(str(reason))}</td>
            <td>{count}</td>
        </tr>
        """

    if not reason_rows:
        reason_rows = """
        <tr>
            <td>None</td>
            <td>0</td>
        </tr>
        """

    return f"""
    <h2>2. Filter / Exclusion Summary</h2>

    <div class="summary">
        <div class="card">
            <div>Total Matches</div>
            <div class="metric">{total}</div>
        </div>
        <div class="card">
            <div>Valid Matches</div>
            <div class="metric">{valid}</div>
        </div>
        <div class="card">
            <div>Excluded Matches</div>
            <div class="metric">{excluded}</div>
        </div>
        <div class="card">
            <div>Excluded Words Raw</div>
            <div class="metric">{excluded_words_raw}</div>
        </div>
    </div>

    <table>
        <tr>
            <th>Exclusion reason</th>
            <th>Count</th>
        </tr>
        {reason_rows}
    </table>

    <p>
        <b>Valid match words raw:</b> {valid_words_raw}<br>
        <b>Excluded match words raw:</b> {excluded_words_raw}
    </p>
    """


def render_matches(report, max_matches=50):
    """Render các đoạn match."""
    matches = report.get("matches", [])

    if not matches:
        return """
        <h2>3. Các đoạn tương đồng</h2>
        <p>Không có đoạn tương đồng.</p>
        """

    sorted_matches = sorted(
        matches,
        key=lambda m: m.get("match_score", 0),
        reverse=True
    )

    blocks = ""

    for idx, m in enumerate(sorted_matches[:max_matches], start=1):
        validity = m.get("validity", "VALID")
        excluded = m.get("excluded", False)

        status_class = "excluded" if excluded else "valid"
        reasons = ", ".join(m.get("exclusion_reasons", [])) or "none"

        paper_id = m.get("source_paper_id", "")
        title = m.get("source_title", "")

        arxiv_id = str(paper_id).replace("arxiv_", "").replace(".pdf", "")
        arxiv_abs = f"https://arxiv.org/abs/{arxiv_id}"
        arxiv_pdf = f"https://arxiv.org/pdf/{arxiv_id}"

        input_text = escape(truncate_text(m.get("input_text", "")))
        source_text = escape(truncate_text(m.get("source_text", "")))

        blocks += f"""
        <div class="passage">
            <h3>
                Match #{idx}
                — {escape(str(m.get("match_type", "")))}
                — score {float(m.get("match_score", 0)):.3f}
                — <span class="{status_class}">{validity}</span>
            </h3>

            <p>
                <b>Source:</b>
                <code>{escape(str(paper_id))}</code>
                — {escape(str(title))}
            </p>

            <p>
                <b>Link:</b>
                <a href="{arxiv_abs}" target="_blank">ArXiv</a> |
                <a href="{arxiv_pdf}" target="_blank">PDF</a>
            </p>

            <p>
                <b>Section:</b>
                input={escape(str(m.get("input_section", "")))},
                source={escape(str(m.get("source_section", "")))}
                |
                <b>Words:</b> {m.get("word_count", 0)}
            </p>

            <p>
                <b>N-gram overlap:</b> {float(m.get("ngram_overlap", 0)):.3f}
                |
                <b>Fuzzy:</b> {float(m.get("fuzzy_ratio", 0)):.3f}
            </p>

            <p>
                <b>Exclusion reasons:</b> {escape(reasons)}<br>
                <b>Source cited:</b> {m.get("source_cited", False)}
                |
                <b>Inline cited:</b> {m.get("inline_cited", False)}
                |
                <b>Quoted:</b> {m.get("quoted", False)}
            </p>

            <p><b>Đoạn trong bài upload:</b></p>
            <div class="input">{input_text}</div>

            <p><b>Đoạn trong bài nguồn:</b></p>
            <div class="source">{source_text}</div>
        </div>
        """

    return f"""
    <h2>3. Các đoạn tương đồng</h2>
    {blocks}
    """


def generate_html_report(report, output_path):
    """Sinh HTML similarity report."""
    overall = float(report.get("overall_similarity", 0))
    risk = report.get("risk_level", "Unknown")
    matched_words = report.get("matched_words", 0)
    total_words = report.get("total_words", 0)
    candidates = report.get("candidate_count", 0)
    matches = report.get("match_count", 0)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Detailed Similarity Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 28px;
                line-height: 1.45;
                color: #222;
            }}
            h1, h2 {{
                color: #222;
            }}
            .summary {{
                display: flex;
                gap: 16px;
                flex-wrap: wrap;
                margin-bottom: 20px;
            }}
            .card {{
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px 16px;
                min-width: 180px;
                background: #fafafa;
            }}
            .metric {{
                font-size: 24px;
                font-weight: bold;
                color: #111;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 16px 0;
                font-size: 14px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                vertical-align: top;
            }}
            th {{
                background: #f1f1f1;
            }}
            .passage {{
                background: #fcfcfc;
                border-left: 4px solid #999;
                padding: 10px;
                margin: 12px 0;
            }}
            .input {{
                background: #fff7e6;
                padding: 8px;
                border-radius: 4px;
                white-space: pre-wrap;
            }}
            .source {{
                background: #eef7ff;
                padding: 8px;
                border-radius: 4px;
                white-space: pre-wrap;
            }}
            .high {{
                color: #b00020;
                font-weight: bold;
            }}
            .medium {{
                color: #b26a00;
                font-weight: bold;
            }}
            .low {{
                color: #0b6b0b;
                font-weight: bold;
            }}
            .valid {{
                color: #0b6b0b;
                font-weight: bold;
            }}
            .excluded {{
                color: #777;
                font-weight: bold;
            }}
            a {{
                color: #0645ad;
            }}
            code {{
                background: #eee;
                padding: 2px 4px;
                border-radius: 3px;
            }}
        </style>
    </head>
    <body>

    <h1>Detailed Similarity Report</h1>

    <div class="summary">
        <div class="card">
            <div>Overall Similarity</div>
            <div class="metric">{overall:.2f}%</div>
        </div>
        <div class="card">
            <div>Risk Level</div>
            <div class="metric">{escape(str(risk))}</div>
        </div>
        <div class="card">
            <div>Matched Words</div>
            <div class="metric">{matched_words}/{total_words}</div>
        </div>
        <div class="card">
            <div>Candidates</div>
            <div class="metric">{candidates}</div>
        </div>
        <div class="card">
            <div>Matches</div>
            <div class="metric">{matches}</div>
        </div>
    </div>

    {render_top_sources(report)}
    {render_filter_summary(report)}
    {render_matches(report)}

    </body>
    </html>
    """

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path