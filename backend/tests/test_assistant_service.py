"""
NOVA — AI Assistant Unit Tests
Targets the pure functions in app/services/assistant/rerank_manager.py and
app/services/assistant/assistant_service.py — no database, no ONNX model,
no LLM call required. `retrieve_and_rerank`/`stream_answer` themselves are
integration-level (real DB + real local models) and covered by the manual
testing walkthrough instead.
"""

from app.services.assistant.assistant_service import Citation, build_context_block, format_history, is_sufficient
from app.services.assistant.rerank_manager import normalize_confidence


class TestNormalizeConfidence:
    def test_zero_score_is_midpoint(self):
        assert normalize_confidence(0.0) == 0.5

    def test_large_positive_score_approaches_one(self):
        assert normalize_confidence(10.0) > 0.99

    def test_large_negative_score_approaches_zero(self):
        assert normalize_confidence(-10.0) < 0.01

    def test_none_is_zero(self):
        assert normalize_confidence(None) == 0.0

    def test_monotonic(self):
        assert normalize_confidence(1.0) > normalize_confidence(0.5) > normalize_confidence(0.0)

    def test_always_in_unit_range(self):
        for raw in (-50.0, -1.0, 0.0, 1.0, 50.0):
            score = normalize_confidence(raw)
            assert 0.0 <= score <= 1.0


class TestIsSufficient:
    def test_above_threshold(self):
        assert is_sufficient(0.9) is True

    def test_below_threshold(self):
        assert is_sufficient(0.1) is False

    def test_at_exact_threshold_is_sufficient(self):
        from app.config import get_settings

        assert is_sufficient(get_settings().assistant_min_confidence) is True


def _citation(**overrides) -> Citation:
    defaults = dict(
        document_id="doc-1",
        filename="policy.pdf",
        page_number=2,
        section_path="Access Control > Password Policy",
        heading="Password Policy",
        similarity_score=0.8,
        rerank_score=3.2,
        excerpt="Passwords must be rotated every 90 days.",
    )
    defaults.update(overrides)
    return Citation(**defaults)


class TestBuildContextBlock:
    def test_single_citation_includes_source_section_page_and_excerpt(self):
        block = build_context_block([_citation()])
        assert "[1]" in block
        assert "Source: policy.pdf" in block
        assert "Section: Access Control > Password Policy" in block
        assert "Page: 2" in block
        assert "Passwords must be rotated every 90 days." in block

    def test_multiple_citations_are_numbered_in_order(self):
        block = build_context_block([_citation(filename="a.pdf"), _citation(filename="b.pdf")])
        assert "[1]" in block and "[2]" in block
        assert block.index("a.pdf") < block.index("[2]")

    def test_missing_page_number_omits_page_field(self):
        block = build_context_block([_citation(page_number=None)])
        assert "Page:" not in block

    def test_falls_back_to_heading_when_no_section_path(self):
        block = build_context_block([_citation(section_path=None, heading="Introduction")])
        assert "Section: Introduction" in block

    def test_no_citations_produces_empty_block(self):
        assert build_context_block([]) == ""


class TestFormatHistory:
    def test_renders_role_and_content(self):
        history = [{"role": "user", "content": "What is PCI-DSS?"}]
        rendered = format_history(history, max_turns=6)
        assert "User: What is PCI-DSS?" in rendered

    def test_truncates_to_max_turns(self):
        history = [{"role": "user", "content": f"turn {i}"} for i in range(10)]
        rendered = format_history(history, max_turns=3)
        assert "turn 9" in rendered
        assert "turn 6" not in rendered  # only the last 3 of 10 survive

    def test_zero_max_turns_yields_empty_string(self):
        history = [{"role": "user", "content": "hello"}]
        assert format_history(history, max_turns=0) == ""

    def test_empty_history_yields_empty_string(self):
        assert format_history([], max_turns=6) == ""
