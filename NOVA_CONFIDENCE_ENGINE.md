# NOVA Dynamic 8D Trust Score & NLI Consensus Specification

## 8-Vector Trust Score Calibration Formula

NOVA computes answer correctness $P(\text{Correct} \mid \mathbf{C})$ using Platt-scaled logistic calibration:

$$\text{logit} = w_0 + \sum_{i=1}^8 w_i \cdot C_i$$

$$P(\text{Correct} \mid \mathbf{C}) = \frac{1}{1 + e^{-\text{logit}}}$$

### Dimension 2: $C_{\text{agreement}}$ (NLI Evidence Relationship Consensus)

$C_{\text{agreement}}$ is derived from the **NLI Pairwise Consensus Engine** (`consensus_engine.py` & `nli_engine.py`):

- **Supported Evidence**: Pairwise `SUPPORTS` relationships boost $C_{\text{agreement}}$ up to $1.00$.
- **Contradictory Evidence**: Pairwise `CONTRADICTS` relationships drop $C_{\text{agreement}}$ to $\le 0.10$.
- **Impact on Decision Gate**: A drop in $C_{\text{agreement}}$ reduces the overall TrustScore below the security policy threshold ($\ge 0.75$), forcing NOVA to abstain or route to Exa web fallback search rather than hallucinating contradictory security claims.
