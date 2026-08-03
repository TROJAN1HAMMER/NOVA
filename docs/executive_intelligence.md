# Executive Intelligence — RAG Milestone 4

Adds a Q&A panel to the existing Executive Dashboard (`/executive`) that answers
leadership-facing questions — "What are our biggest risks?", "What changed this
week?", "What compliance gaps remain?", "What should leadership prioritize?" —
grounded in two sources, both always retrieved before any generation.

## Two grounding sources, different roles

1. **Scan history evidence** (`evidence_service.py`) — the PRIMARY grounding,
   deterministic, always computed regardless of the question asked. Portfolio
   totals, findings by severity, average Banking Risk Score, top-risk
   repositories, per-framework compliance, and an 8-week trend plus a
   this-week-vs-last-week delta — all pure aggregation over `ScanJob`/
   `ScanResult`/`Repository`/`Finding`, no LLM involved at all.
2. **Knowledge-base documentation** (Milestone 1/2's pipeline, reused
   unmodified) — a SECONDARY, supplementary source. Unlike Milestones 2/3,
   falling short of the confidence gate doesn't block an answer here — the
   evidence snapshot alone is always enough to ground a response about scan
   history. Knowledge-base retrieval only adds supplementary citations when it
   clears the gate.

An answer is only refused entirely (no LLM call) when **neither** source has
anything — i.e., a brand-new deployment with zero completed scans and no
relevant knowledge-base content.

## "Never fabricate statistics" — how it's actually enforced

Every number in `render_evidence_block()`'s output is a field this same module
computed one line above. The rendered block is the **only** scan-history text
that ever reaches the LLM prompt — there is no raw per-scan or per-finding data
in the prompt for a model to misread, round differently, or embellish. If the
model states a number, it can only be one of the numbers already given to it.

This mirrors — and is the direct evolution of — `app/services/ai/ai_engine.py`'s
pre-existing `generate_executive_summary()`, which already never sent raw
findings to a provider, only pre-computed aggregate counts. This milestone
extends that same discipline from "one fixed summary shape" to "any question,"
and adds the knowledge-base layer + citations + PDF export on top.

## Pipeline

```
question asked
  │
  ▼
1. Build evidence snapshot   — ALWAYS run, regardless of the question:
                               portfolio stats, top-risk repos, compliance
                               per framework, weekly trend, week-over-week
  │
  ▼
2. Retrieve + rerank KB docs  — same Milestone 1/2 code, unmodified;
                               confidence gate decides whether citations
                               are INCLUDED, not whether to proceed at all
  │
  ▼
3. Grounding check            — refuse (no LLM call) only if there's
                               neither evidence data nor KB citations
  │
  ▼
4. Stream a grounded answer   — closed-context prompt: the exact evidence
                               block + any KB excerpts + conversation
                               history + the question. Same LLM gateway
                               (app/services/ai/gateway.py) as every other
                               milestone, unmodified.
```

If no LLM provider is configured (this deployment's default), the response
streams the raw evidence block itself back as the "answer" — verified live:
asking "What are our biggest risks?" against a repository with 26 completed
scans returned the exact computed numbers (88 repositories, 26 scans, 309
findings, portfolio average BRS 40.66, `premade_critical_risk` at BRS 91.7,
PCI-DSS 9/24 repositories compliant with 308 violations) with no fabricated or
rounded-differently figures.

## Show evidence

Every answer's evidence snapshot is shown in the UI (and included in the PDF)
as: portfolio average BRS, total findings, this-week vs. last-week scan counts,
a severity breakdown, the top-risk repositories with their BRS scores, and
per-framework compliance ratios — the same numbers the LLM was given, rendered
for the human to independently verify rather than just trusting the prose above it.

## Export to PDF

`POST /executive-intelligence/export-pdf` renders **exactly what the client
already displayed** — the question, the answer text, the evidence snapshot,
and the citations are all passed back from the frontend, not recomputed
server-side. This is deliberate: recomputing evidence moments after the user
read the answer could pick up a scan that just completed in the background,
producing a PDF that no longer matches what was actually reviewed on screen.
The PDF (reportlab, self-contained — no dependency on the existing scan-report
pipeline) includes the question, answer, a metric table of the evidence used,
and a numbered source list for any knowledge-base citations.

## RBAC

Gated by `get_current_active_user` only (any authenticated user) — same
precedent Milestone 3's finding-intelligence endpoint set. The actual access
boundary is the frontend: this panel lives on `/executive`, whose existing
role set (Admin, Security Manager, Executive/Board, Read Only) is wider than
the AI Assistant/Knowledge Base pages' (`KNOWLEDGE_READ`, which excludes Read
Only but includes Security Analyst) — deliberately matching who already sees
the rest of the Executive Dashboard, not a new access tier. Both new routes
are POST-shaped but semantically read-only, so both are listed in
`PermissionMiddleware`'s existing `READ_ONLY_QUERY_PATH_PREFIXES` allowlist
(same mechanism Milestones 2/3 already established) so the Read Only/Executive
roles aren't wrongly blocked by the coarse verb-based rule.

## Configuration

Reuses Milestone 2/3's assistant settings entirely — no new settings were
introduced for this milestone.
