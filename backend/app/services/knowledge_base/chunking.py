"""
NOVA — Document Chunking Pipeline
Extracts text from an uploaded document (PDF/Markdown/plain text) and
splits it into semantic chunks for embedding, preserving heading context,
section hierarchy, and page numbers wherever the source format has them.

Chunk sizing uses the same 4-chars/token heuristic as
app/services/ai/token_estimator.py rather than a real tokenizer —
consistent with how the rest of NOVA already budgets text, and precise
enough for chunk-boundary decisions.
"""

import re
from dataclasses import dataclass
from typing import Optional

from pypdf import PdfReader

from app.config import get_settings
from app.services.ai.token_estimator import CHARS_PER_TOKEN, estimate_tokens

settings = get_settings()

MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# Matches numbered headings common in standards/policy documents, e.g.
# "1.2.3 Access Control Requirements" — a heuristic, not exhaustive; text
# with no such headings simply gets no section_path/heading.
NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,4})\s+([A-Z][^\n]{2,120})$")


class UnsupportedDocumentTypeError(ValueError):
    pass


@dataclass
class ExtractedPage:
    page_number: Optional[int]  # None for markdown/text — no page concept
    text: str


@dataclass
class Chunk:
    content: str
    heading: Optional[str]
    section_path: Optional[str]
    page_number: Optional[int]
    token_count: int


def detect_document_type(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".md") or lowered.endswith(".markdown"):
        return "markdown"
    if lowered.endswith(".txt"):
        return "text"
    raise UnsupportedDocumentTypeError(
        f"Unsupported file type for '{filename}' — only .pdf, .md/.markdown, and .txt are supported."
    )


def extract_pages(file_path: str, document_type: str) -> list[ExtractedPage]:
    if document_type == "pdf":
        return _extract_pdf_pages(file_path)
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    return [ExtractedPage(page_number=None, text=_clean_text(text))]


def _extract_pdf_pages(file_path: str) -> list[ExtractedPage]:
    reader = PdfReader(file_path)
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        pages.append(ExtractedPage(page_number=index, text=_clean_text(raw_text)))
    return pages


def _clean_text(text: str) -> str:
    # Collapse whitespace left over from PDF text extraction (repeated
    # spacing from multi-column layouts, stray form-feeds) without
    # touching intentional paragraph breaks.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _match_heading(block: str, document_type: str) -> Optional[tuple[int, str]]:
    if "\n" in block:
        return None  # headings are always single lines
    if document_type == "markdown":
        match = MARKDOWN_HEADING_RE.match(block)
        if match:
            return len(match.group(1)), match.group(2).strip()
        return None
    match = NUMBERED_HEADING_RE.match(block)
    if match:
        level = match.group(1).count(".") + 1
        return level, block.strip()
    return None


def _update_heading_stack(stack: list[str], level: int, text: str) -> None:
    del stack[level - 1 :]
    stack.append(text)


def _tail_by_tokens(text: str, max_tokens: int) -> str:
    """The trailing slice of `text` worth roughly `max_tokens`, trimmed to
    a word boundary — used to carry overlap forward into the next chunk."""
    if max_tokens <= 0 or not text:
        return ""
    tail = text[-(max_tokens * CHARS_PER_TOKEN) :]
    space_index = tail.find(" ")
    if space_index > 0:
        tail = tail[space_index + 1 :]
    return tail.strip()


def _split_into_blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def chunk_document(pages: list[ExtractedPage], document_type: str) -> list[Chunk]:
    heading_stack: list[str] = []
    current_heading: Optional[str] = None
    chunks: list[Chunk] = []

    def flush(buffer: list[str], page_number: Optional[int]) -> Optional[str]:
        """Emits a Chunk from `buffer` (if non-empty) and returns an
        overlap tail to seed the next chunk's buffer."""
        content = "\n\n".join(buffer).strip()
        if not content:
            return None
        chunks.append(
            Chunk(
                content=content,
                heading=current_heading,
                section_path=" > ".join(heading_stack) if heading_stack else None,
                page_number=page_number,
                token_count=estimate_tokens(content),
            )
        )
        return _tail_by_tokens(content, settings.knowledge_chunk_overlap_tokens)

    for page in pages:
        buffer: list[str] = []
        buffer_tokens = 0

        for block in _split_into_blocks(page.text):
            heading_match = _match_heading(block, document_type)
            if heading_match:
                flush(buffer, page.page_number)
                buffer, buffer_tokens = [], 0
                level, heading_text = heading_match
                _update_heading_stack(heading_stack, level, heading_text)
                current_heading = heading_text
                continue

            block_tokens = estimate_tokens(block)
            if buffer and buffer_tokens + block_tokens > settings.knowledge_chunk_size_tokens:
                overlap = flush(buffer, page.page_number)
                buffer = [overlap] if overlap else []
                buffer_tokens = estimate_tokens(overlap) if overlap else 0

            buffer.append(block)
            buffer_tokens += block_tokens

        flush(buffer, page.page_number)

    return chunks
