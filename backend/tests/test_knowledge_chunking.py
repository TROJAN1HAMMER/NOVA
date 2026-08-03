"""
NOVA — Knowledge Base Chunking Unit Tests
Targets the pure text-processing functions in
app/services/knowledge_base/chunking.py — no database, no embedding
model, no async required. `extract_pages`'s PDF branch (which shells out
to pypdf against a real file) and the embedding/vector-store pieces are
integration-level and covered by the manual testing walkthrough instead.
"""

import pytest

from app.services.knowledge_base.chunking import (
    Chunk,
    ExtractedPage,
    UnsupportedDocumentTypeError,
    chunk_document,
    detect_document_type,
)


class TestDetectDocumentType:
    def test_pdf(self):
        assert detect_document_type("policy.pdf") == "pdf"

    def test_markdown_variants(self):
        assert detect_document_type("readme.md") == "markdown"
        assert detect_document_type("readme.markdown") == "markdown"

    def test_text(self):
        assert detect_document_type("notes.txt") == "text"

    def test_unsupported_raises(self):
        with pytest.raises(UnsupportedDocumentTypeError):
            detect_document_type("archive.zip")

    def test_case_insensitive(self):
        assert detect_document_type("POLICY.PDF") == "pdf"


class TestChunkDocumentMarkdown:
    def test_preserves_heading_and_section_path(self):
        text = (
            "# Access Control\n\n"
            "This section covers access control requirements.\n\n"
            "## Password Policy\n\n"
            "Passwords must be rotated every 90 days.\n"
        )
        pages = [ExtractedPage(page_number=None, text=text)]

        chunks = chunk_document(pages, "markdown")

        assert len(chunks) == 2
        assert chunks[0].heading == "Access Control"
        assert chunks[0].section_path == "Access Control"
        assert "access control requirements" in chunks[0].content.lower()

        assert chunks[1].heading == "Password Policy"
        assert chunks[1].section_path == "Access Control > Password Policy"
        assert "rotated every 90 days" in chunks[1].content

    def test_heading_stack_pops_on_sibling_heading(self):
        text = (
            "# Section A\n\n## Sub A.1\n\nDetail one.\n\n"
            "## Sub A.2\n\nDetail two.\n"
        )
        pages = [ExtractedPage(page_number=None, text=text)]

        chunks = chunk_document(pages, "markdown")

        section_paths = [c.section_path for c in chunks]
        assert "Section A > Sub A.1" in section_paths
        assert "Section A > Sub A.2" in section_paths

    def test_no_headings_produces_single_chunk_no_section_path(self):
        text = "Just a plain paragraph with no heading structure at all."
        pages = [ExtractedPage(page_number=None, text=text)]

        chunks = chunk_document(pages, "markdown")

        assert len(chunks) == 1
        assert chunks[0].heading is None
        assert chunks[0].section_path is None

    def test_empty_page_produces_no_chunks(self):
        pages = [ExtractedPage(page_number=None, text="")]
        assert chunk_document(pages, "markdown") == []


class TestChunkDocumentNumberedHeadings:
    def test_numbered_heading_detected_in_pdf_text(self):
        text = (
            "1.2.3 Access Control Requirements\n\n"
            "All systems must enforce role-based access control.\n"
        )
        pages = [ExtractedPage(page_number=1, text=text)]

        chunks = chunk_document(pages, "pdf")

        assert len(chunks) == 1
        assert chunks[0].heading == "1.2.3 Access Control Requirements"
        assert chunks[0].page_number == 1


class TestChunkDocumentPageNumbers:
    def test_each_chunk_carries_its_source_page_number(self):
        pages = [
            ExtractedPage(page_number=1, text="Content from page one."),
            ExtractedPage(page_number=2, text="Content from page two."),
        ]

        chunks = chunk_document(pages, "pdf")

        assert [c.page_number for c in chunks] == [1, 2]


class TestChunkDocumentSizeBudget:
    def test_long_text_is_split_into_multiple_chunks(self):
        # ~350 tokens is the default budget (app/config.py) — build a
        # paragraph-per-block text comfortably over that so at least one
        # split is forced.
        paragraphs = [f"Paragraph number {i} with some representative body text." for i in range(80)]
        text = "\n\n".join(paragraphs)
        pages = [ExtractedPage(page_number=None, text=text)]

        chunks = chunk_document(pages, "text")

        assert len(chunks) > 1
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.token_count > 0

    def test_consecutive_chunks_share_overlap_text(self):
        paragraphs = [f"Distinctive paragraph marker {i} with enough words to matter here." for i in range(80)]
        text = "\n\n".join(paragraphs)
        pages = [ExtractedPage(page_number=None, text=text)]

        chunks = chunk_document(pages, "text")

        assert len(chunks) > 1
        # The overlap tail carried into chunk N+1 should reappear as a
        # prefix of chunk N+1's content, sourced from the tail of chunk N.
        first_chunk_tail_words = chunks[0].content.split()[-5:]
        second_chunk_words = chunks[1].content.split()
        assert any(word in second_chunk_words for word in first_chunk_tail_words)
