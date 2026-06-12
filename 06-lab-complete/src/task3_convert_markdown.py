"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.

Sử dụng MarkItDown của Microsoft:
    https://github.com/microsoft/markitdown

Cài đặt:
    pip install markitdown

Hướng dẫn:
    1. Scan toàn bộ file trong data/landing/ (PDF, DOCX, JSON)
    2. Convert sang Markdown
    3. Lưu vào data/standardized/ giữ nguyên cấu trúc thư mục
"""

import json
import sys
from pathlib import Path

from markitdown import MarkItDown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown()

    for filepath in legal_dir.iterdir():
        if filepath.suffix.lower() in (".pdf", ".docx", ".doc"):
            print(f"Converting: {filepath.name}")
            result = md.convert(str(filepath))
            output_path = output_dir / f"{filepath.stem}.md"
            text_content = result.text_content.strip()
            if not text_content:
                text_content = (
                    "MarkItDown không trích xuất được nội dung chữ từ file PDF này. "
                    "File có thể là PDF scan hoặc không có text layer. "
                    "Để dùng tốt cho RAG, cần OCR hoặc copy nội dung văn bản pháp luật từ nguồn chính thống "
                    "rồi thay thế phần ghi chú này bằng nội dung thật trước khi indexing."
                )
            content = (
                f"# {filepath.stem}\n\n"
                f"**Source:** {filepath.name}\n"
                f"**Type:** legal\n\n"
                "---\n\n"
                f"{text_content}"
            )
            output_path.write_text(content, encoding="utf-8")
            print(f"  ✓ Saved: {output_path}")


def convert_news_articles():
    """Convert crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown()

    for filepath in news_dir.iterdir():
        suffix = filepath.suffix.lower()
        if suffix not in (".json", ".html", ".htm", ".txt", ".md"):
            continue

        print(f"Converting: {filepath.name}")
        output_path = output_dir / f"{filepath.stem}.md"

        if suffix == ".json":
            data = json.loads(filepath.read_text(encoding="utf-8"))
            title = data.get("title", filepath.stem)
            source = data.get("url", filepath.name)
            crawled = data.get("date_crawled", "N/A")
            article_content = data.get("content_markdown") or data.get("content") or ""
            content = (
                f"# {title}\n\n"
                f"**Source:** {source}\n"
                f"**Crawled:** {crawled}\n"
                f"**Type:** news\n\n"
                "---\n\n"
                f"{article_content}"
            )
        elif suffix == ".md":
            original = filepath.read_text(encoding="utf-8")
            content = (
                f"# {filepath.stem}\n\n"
                f"**Source:** {filepath.name}\n"
                f"**Type:** news\n\n"
                "---\n\n"
                f"{original}"
            )
        else:
            result = md.convert(str(filepath))
            content = (
                f"# {filepath.stem}\n\n"
                f"**Source:** {filepath.name}\n"
                f"**Type:** news\n\n"
                "---\n\n"
                f"{result.text_content}"
            )

        output_path.write_text(content, encoding="utf-8")
        print(f"  ✓ Saved: {output_path}")


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown (MarkItDown)")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    convert_legal_docs()

    print("\n--- News Articles ---")
    convert_news_articles()

    print("\n✓ Done! Output tại:", OUTPUT_DIR)


if __name__ == "__main__":
    convert_all()
