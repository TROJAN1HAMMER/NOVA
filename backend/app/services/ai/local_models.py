"""
NOVA — Known Local Model Reference

Ollama and vLLM both accept arbitrary model identifiers — this is not an
enforced whitelist, just the set of models NOVA's local-mode has
actually been validated against. `warn_if_unknown_model` is called once at
provider construction time and only ever logs; it never blocks a custom or
future model from being used.
"""

import structlog

logger = structlog.get_logger(__name__)

OLLAMA_KNOWN_TAGS = {
    "llama3": "Llama 3 (8B/70B, Meta)",
    "llama3.1": "Llama 3.1 (Meta)",
    "mistral": "Mistral 7B (Mistral AI)",
    "phi3": "Phi-3 (Microsoft)",
    "mixtral": "Mixtral 8x7B MoE (Mistral AI)",
}

VLLM_KNOWN_REPOS = {
    "meta-llama/meta-llama-3-8b-instruct": "Llama 3 8B Instruct",
    "meta-llama/meta-llama-3-70b-instruct": "Llama 3 70B Instruct",
    "mistralai/mistral-7b-instruct-v0.3": "Mistral 7B Instruct",
    "microsoft/phi-3-mini-4k-instruct": "Phi-3 Mini",
    "mistralai/mixtral-8x7b-instruct-v0.1": "Mixtral 8x7B Instruct",
}


def warn_if_unknown_ollama_model(model: str) -> None:
    if model and model.lower() not in OLLAMA_KNOWN_TAGS:
        logger.info(
            "ollama_provider.unvalidated_model",
            model=model,
            note="not one of NOVA's validated tags (llama3/mistral/phi3/mixtral) — will still be used as-is",
        )


def warn_if_unknown_vllm_model(model: str) -> None:
    if model and model.lower() not in VLLM_KNOWN_REPOS:
        logger.info(
            "vllm_provider.unvalidated_model",
            model=model,
            note="not one of NOVA's validated repos (Llama 3/Mistral/Phi-3/Mixtral) — will still be used as-is",
        )
