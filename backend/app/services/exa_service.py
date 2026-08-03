"""
AEKOF — Controlled Exa Web Search Fallback Service
"""

import os
import re
import structlog

logger = structlog.get_logger(__name__)


class ExaService:
    def __init__(self):
        self.api_key = os.environ.get("EXA_API_KEY")

    def search_fallback(self, question: str) -> str:
        """Executes external web search via Exa API when vector retrieval confidence is below threshold."""
        if not self.api_key:
            logger.warning("exa_service.missing_key")
            return "Sorry, I don't know based on the given context and web search fallback is not configured."

        try:
            from exa_py import Exa
            exa = Exa(api_key=self.api_key)
            extended_query = f"{question} technical manual documentation"
            response = exa.answer(extended_query)
            answer_text = response.answer

            # Extract links
            links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', answer_text)
            sources = []
            seen_urls = set()
            for title, url in links:
                if url not in seen_urls:
                    sources.append(f"- [{title}]({url})")
                    seen_urls.add(url)

            answer_text = re.sub(r'\s*\((?:\[[^\]]+\]\((?:https?://[^\)]+)\)(?:,\s*)?)+\)', '', answer_text)
            answer_text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1', answer_text)

            if sources:
                answer_text += "\n\n**Web Sources:**\n" + "\n".join(sources)

            logger.info("exa_service.search_success", query=question)
            return answer_text
        except Exception as exc:
            logger.error("exa_service.search_failed", error=str(exc))
            return f"Sorry, I couldn't retrieve an answer. (Web Search Error: {str(exc)})"


exa_service = ExaService()
