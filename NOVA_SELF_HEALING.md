# NOVA Outer-Loop Self-Healing System Specification

## Overview

NOVA implements a closed-loop self-healing mechanism that monitors retrieval failures and query refusals, clusters recurring knowledge gaps, auto-synthesizes candidate Stage 0 FAQ rules, and monitors active rules for degradation.

## Self-Healing Loop Stages

1. **Failure Logging**: Assistant query refusals and low-confidence searches are logged to `search_analytics_logs`.
2. **Frequency Clustering**: Background Celery task `nightly_gap_cluster_analysis_task` extracts failed queries and clusters normalized patterns.
3. **Draft FAQ Candidate Synthesis**: Auto-generates candidate `FAQRule` in `is_draft=True` state with candidate answers and evidence links.
4. **Administrative Promotion Gate**: Surfaced in the Knowledge Evolution dashboard (`/knowledge-evolution`) for 1-click promotion to active production status.
5. **Degradation Monitoring & Rollback**: `nightly_faq_synthesis_task` checks active FAQ rules against analytics fallback spikes; if fallback rate exceeds threshold ($\ge 5$), the rule is automatically marked `ROLLED_BACK` and disabled from Stage 0 sub-millisecond execution.
