"""Vision backend for opencode — Qwen3-VL + PDF intelligence.

Modes:
  describe <file>          — auto: pypdf for text PDF, Qwen3-VL for scanned/images
  ask <cache_id> <q>       — follow-up question on cached image
  review <file> <context>  — UI/UX audit with optional image enhancement
  pdf-table <file> [--csv|--xlsx] [--output <path>]  — extract tables
  pdf-create <text> --output <file>  — create PDF from text

Cache: .opencode/cache/vision/<cache_id>.png
Env:   OPENROUTER_API_KEY
"""

import sys
import os
import json
import base64
import hashlib
import tempfile
import shutil
from pathlib import Path

import httpx
from pypdf import PdfReader

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

# ── env loading ──────────────────────────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.exists():
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                if key not in os.environ:
                    os.environ[key] = val.strip()

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen3-vl-235b-a22b-instruct"
CACHE_DIR = Path.home() / ".config/opencode/cache/vision"

# ── prompts ──────────────────────────────────────────────────────
DESCRIBE_PROMPT = """You are a precise visual analyst. Describe this image in detail.

If this is a document (invoice, contract, form, letter):
- Extract ALL visible text verbatim where possible
- Note the layout: headers, tables, columns, signatures, stamps
- Mention any numbers, dates, names, amounts precisely

If this is a screenshot, UI, or diagram:
- Describe the layout and structure
- List all visible elements: buttons, text fields, images, labels
- Note colors, fonts, sizing issues if visible

If this is a photo or general image:
- Describe what is shown, who/what is in it
- Note important details, text if any

Be thorough. Do NOT summarize — include ALL visible information."""

REVIEW_PROMPT = """You are a professional UI/UX auditor. Analyze this screenshot of a web page.

Context about expected design:
{context}

Find ALL issues in these categories:

1. LAYOUT BUGS — misaligned elements, overlaps, incorrect spacing, broken grids,
   elements outside viewport, wrong stacking order
2. VISUAL DEFECTS — wrong colors, missing styles, font issues, poor contrast,
   unreadable text, broken images, inconsistent styling
3. CONTENT PROBLEMS — missing text/buttons/sections, truncated content,
   incorrect hierarchy, typos, wrong copy
4. RESPONSIVE ISSUES — elements not fitting viewport, horizontal overflow,
   elements too small/large for their context

For each issue specify:
- ELEMENT: which part of the page (e.g., "hero section heading", "nav bar logo")
- PROBLEM: what exactly is wrong
- FIX: specific CSS/HTML change needed (e.g., "add display: flex to .card-container")

List from most to least critical. If no issues found, say "PASS — no issues detected."

Be specific and actionable. Each fix should be something a developer can implement immediately."""

# ── helpers ──────────────────────────────────────────────────────

def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _cache_key(path: str) -> str:
    h = hashlib.md5()
    h.update(os.path.abspath(path).encode())
    return h.hexdigest()[:12]


def _call_vision_api(image_b64: str, prompt: str, max_tokens: int = 2000) -> str:
    resp = httpx.post(
        BASE_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        return f"API Error: {data['error']}"
    return data["choices"][0]["message"]["content"]


def _pdf_to_images(pdf_path: str) -> list[str]:
    if convert_from_path is None:
        raise RuntimeError("pdf2image not installed. Run: pip install pdf2image")
    images = convert_from_path(pdf_path, dpi=200)
    paths = []
    tmpdir = Path(tempfile.mkdtemp(prefix="vision_pdf_"))
    for i, img in enumerate(images):
        p = tmpdir / f"page_{i + 1}.png"
        img.save(str(p), "PNG")
        paths.append(str(p))
    return paths


def _enhance_image(path: str) -> str:
    """Sharpen image for better text readability in vision analysis."""
    try:
        import cv2
        import numpy as np
        img = cv2.imread(path)
        if img is None:
            return path
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(img, -1, kernel)
        out = path.replace(".png", "_enhanced.png").replace(".jpg", "_enhanced.png")
        cv2.imwrite(out, sharpened)
        return out
    except ImportError:
        return path

# ── PDF text extraction (pypdf) ─────────────────────────────────

def _try_extract_pdf_text(pdf_path: str) -> tuple[bool, str]:
    """Returns (has_text, extracted_text)."""
    reader = PdfReader(pdf_path)
    pages_text = []
    total_chars = 0
    for i, page in enumerate(reader.pages):
        t = page.extract_text()
        if t:
            clean = t.strip()
            if len(clean) > 30:
                pages_text.append(f"--- Page {i + 1}/{len(reader.pages)} ---\n{clean}")
                total_chars += len(clean)
    if total_chars > 100:
        return True, f"[source: pypdf, pages: {len(reader.pages)}]\n\n" + "\n\n".join(pages_text)
    return False, ""


# ── modes ────────────────────────────────────────────────────────

def cmd_describe(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    suffix = path.suffix.lower()

    # PDF: try pypdf first, fall back to vision
    if suffix == ".pdf":
        has_text, text = _try_extract_pdf_text(str(path))
        if has_text:
            return text
        return _describe_pdf_vision(str(path))

    # Image: send to vision
    img_b64 = _encode_image(str(path))
    cid = _cache_key(str(path))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        shutil.copy(str(path), str(CACHE_DIR / f"{cid}.png"))

    result = _call_vision_api(img_b64, DESCRIBE_PROMPT)
    return f"[cache_id: {cid}]\n{result}"


def _describe_pdf_vision(pdf_path: str) -> str:
    """Fallback: convert PDF to images, send to Qwen3-VL."""
    page_paths = _pdf_to_images(pdf_path)
    if not page_paths:
        return "ERROR: could not extract pages from PDF"

    cid = _cache_key(pdf_path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for i, p in enumerate(page_paths):
        img_b64 = _encode_image(p)
        shutil.copy(p, str(CACHE_DIR / f"{cid}_p{i + 1}.png"))

        prompt = f"Page {i + 1} of {len(page_paths)}.\n\n{DESCRIBE_PROMPT}"
        r = _call_vision_api(img_b64, prompt, max_tokens=3000)
        results.append(f"--- Page {i + 1}/{len(page_paths)} ---\n{r}")

    return f"[cache_id: {cid}, pages: {len(page_paths)}, source: qwen3-vl]\n" + "\n\n".join(results)


def cmd_ask(cache_id: str, question: str) -> str:
    cache_files = sorted(CACHE_DIR.glob(f"{cache_id}*"))
    if not cache_files:
        return f"ERROR: no cached images for id '{cache_id}'. Run vision-describe first."

    results = []
    for cf in cache_files:
        img_b64 = _encode_image(str(cf))
        r = _call_vision_api(img_b64, question, max_tokens=1500)
        if len(cache_files) > 1:
            label = cf.stem.replace(cache_id, "").lstrip("_p")
            results.append(f"[page {label}] {r}" if label else r)
        else:
            results.append(r)

    return "\n\n".join(results)


def cmd_review(file_path: str, context: str) -> str:
    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    # Enhance image for better text readability
    enhanced = _enhance_image(str(path))
    img_b64 = _encode_image(enhanced)

    prompt = REVIEW_PROMPT.format(context=context)
    return _call_vision_api(img_b64, prompt, max_tokens=2500)


def cmd_pdf_table(file_path: str, fmt: str = "csv", output: str = None) -> str:
    """Extract tables from PDF using pdfplumber."""
    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    import pdfplumber

    all_tables = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for j, table in enumerate(tables):
                if table and len(table) > 0:
                    all_tables.append((i + 1, j + 1, table))

    if not all_tables:
        return "No tables found in this PDF."

    if not output:
        stem = path.stem
        ext = ".csv" if fmt == "csv" else ".xlsx"
        output = f"{stem}_tables{ext}"

    import pandas as pd

    if fmt == "csv":
        # Save each table to a separate sheet/CSV
        if len(all_tables) == 1:
            _, _, table = all_tables[0]
            df = pd.DataFrame(table[1:], columns=table[0]) if table else pd.DataFrame()
            df.to_csv(output, index=False)
        else:
            base = output.replace(".csv", "")
            saved = []
            for pi, ti, table in all_tables:
                fname = f"{base}_p{pi}t{ti}.csv"
                df = pd.DataFrame(table[1:], columns=table[0]) if len(table) > 1 else pd.DataFrame(table)
                df.to_csv(fname, index=False)
                saved.append(fname)
            return f"Extracted {len(all_tables)} tables:\n" + "\n".join(f"  {s}" for s in saved)
        return f"Table saved: {output}"

    elif fmt == "xlsx":
        import pandas as pd
        with pd.ExcelWriter(output) as writer:
            for pi, ti, table in all_tables:
                sheet_name = f"p{pi}t{ti}"
                if len(table) > 1:
                    df = pd.DataFrame(table[1:], columns=table[0])
                else:
                    df = pd.DataFrame(table)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        return f"Extracted {len(all_tables)} tables → {output}"

    return f"ERROR: unknown format '{fmt}'. Use csv or xlsx."


def cmd_pdf_create(text: str, output: str) -> str:
    """Create a PDF from plain text using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    out_path = Path(output)
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()

    # Add a monospace style for code blocks
    styles.add(ParagraphStyle('Mono', parent=styles['Normal'], fontName='Courier'))

    story = []
    for line in text.split("\n"):
        line = line.rstrip()
        if not line:
            story.append(Spacer(1, 6))
            continue

        # Detect markdown-like headers
        if line.startswith("# ") and len(line) > 2:
            story.append(Paragraph(line[2:], styles['Heading1']))
        elif line.startswith("## ") and len(line) > 3:
            story.append(Paragraph(line[3:], styles['Heading2']))
        elif line.startswith("### ") and len(line) > 4:
            story.append(Paragraph(line[4:], styles['Heading3']))
        elif line.startswith("- "):
            story.append(Paragraph("• " + line[2:], styles['Normal']))
        elif line.startswith("```"):
            pass  # skip code block markers
        else:
            story.append(Paragraph(line, styles['Normal']))

    doc.build(story)
    return f"PDF created: {out_path.resolve()}"


# ── CLI ──────────────────────────────────────────────────────────

USAGE = """Usage:
  vision.py describe <file>
  vision.py ask <cache_id> <question>
  vision.py review <screenshot> <design_context>
  vision.py pdf-table <file> [--csv|--xlsx] [--output <path>]
  vision.py pdf-create <text> --output <file>"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    if not API_KEY and sys.argv[1] not in ("pdf-table", "pdf-create", "describe"):
        print("ERROR: OPENROUTER_API_KEY environment variable is not set.")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "describe" and len(sys.argv) >= 3:
        print(cmd_describe(sys.argv[2]))
    elif mode == "ask" and len(sys.argv) >= 4:
        print(cmd_ask(sys.argv[2], sys.argv[3]))
    elif mode == "review" and len(sys.argv) >= 4:
        print(cmd_review(sys.argv[2], sys.argv[3]))
    elif mode == "pdf-table" and len(sys.argv) >= 3:
        fmt = "csv"
        output = None
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--csv":
                fmt = "csv"
            elif args[i] == "--xlsx":
                fmt = "xlsx"
            elif args[i] == "--output" and i + 1 < len(args):
                output = args[i + 1]
                i += 1
            i += 1
        print(cmd_pdf_table(sys.argv[2], fmt, output))
    elif mode == "pdf-create":
        text = sys.argv[2] if len(sys.argv) > 2 else ""
        output = None
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--output" and i + 1 < len(args):
                output = args[i + 1]
                i += 1
            i += 1
        if not output:
            print("ERROR: --output is required for pdf-create")
            sys.exit(1)
        print(cmd_pdf_create(text, output))
    else:
        print(f"ERROR: missing arguments.\n{USAGE}")
        sys.exit(1)
