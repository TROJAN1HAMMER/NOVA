const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  PageNumber, Footer, TableOfContents, PageBreak, SectionType,
  NumberFormat, convertInchesToTwip,
} = require("docx");

const {
  FONT, bodyPar, labeledPar, h1, h1NoBreak, h2, h3,
  figureCaption, tableCaption, imageParagraph, buildTable,
} = require("./helpers");

const MARGIN = convertInchesToTwip(1);
const PAGE = {
  size: { width: convertInchesToTwip(8.27), height: convertInchesToTwip(11.69) }, // A4
  margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
};

// ============================================================
// TITLE PAGE
// ============================================================
const titlePageChildren = [
  new Paragraph({ spacing: { before: 600 }, children: [] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "VELLORE INSTITUTE OF TECHNOLOGY", bold: true, font: FONT, size: 34 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200 },
    children: [new TextRun({ text: "Literature Review and Proposed Architecture Report", font: FONT, size: 28, italics: true })],
  }),
  new Paragraph({ spacing: { before: 900 }, children: [] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Project Title", font: FONT, size: 22, bold: true, color: "555555" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 500 },
    children: [new TextRun({ text: "Adaptive Enterprise Knowledge Operating Framework (AEKOF)", font: FONT, size: 30, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Course", font: FONT, size: 22, bold: true, color: "555555" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 260 },
    children: [new TextRun({ text: "Natural Language Processing", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Course Code", font: FONT, size: 22, bold: true, color: "555555" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 700 },
    children: [new TextRun({ text: "ISWE310L", font: FONT, size: 24 })],
  }),
  new Paragraph({ spacing: { before: 400 }, children: [] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Prepared By", font: FONT, size: 22, bold: true, color: "555555" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100 },
    children: [new TextRun({ text: "[Student Name 1] — [Registration Number 1]", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "[Student Name 2] — [Registration Number 2]", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 500 },
    children: [new TextRun({ text: "[Student Name 3] — [Registration Number 3]", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Submitted To", font: FONT, size: 22, bold: true, color: "555555" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100, after: 500 },
    children: [new TextRun({ text: "[Faculty Name]", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Submission Date", font: FONT, size: 22, bold: true, color: "555555" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100 },
    children: [new TextRun({ text: "[Date]", font: FONT, size: 24 })],
  }),
];

// ============================================================
// FRONT MATTER: TOC, LIST OF FIGURES, LIST OF TABLES
// ============================================================
const frontMatterChildren = [
  h1NoBreak("Table of Contents"),
  new TableOfContents("Table of Contents", {
    hyperlink: true,
    headingStyleRange: "1-3",
  }),
  new Paragraph({ children: [new PageBreak()] }),
  h1NoBreak("List of Figures"),
  new TableOfContents("List of Figures", {
    hyperlink: true,
    captionLabelIncludingNumbers: "Figure",
  }),
  new Paragraph({ children: [new PageBreak()] }),
  h1NoBreak("List of Tables"),
  new TableOfContents("List of Tables", {
    hyperlink: true,
    captionLabelIncludingNumbers: "Table",
  }),
];

// ============================================================
// BODY CONTENT
// ============================================================
const body = [];

// ---------- 1. Introduction ----------
body.push(h1("1. Introduction"));
body.push(bodyPar(
  "Retrieval-Augmented Generation (RAG) has emerged as a prominent paradigm for augmenting Large Language Models (LLMs) with external knowledge. However, traditional RAG systems deployed in enterprise environments often encounter structural limitations, including static retrieval pipelines, uncalibrated confidence leading to hallucinations, and an inability to resolve conflicting information. In mission-critical applications, presenting an unverified or low-confidence response introduces significant operational risk."
));
body.push(bodyPar(
  "The Adaptive Enterprise Knowledge Operating Framework (AEKOF) is motivated by the need for a deterministic, robust, and calibrated retrieval system. The primary objective of AEKOF is to orchestrate a multi-stage evidence cascade that verifies knowledge consensus prior to generation. By integrating task-decomposed query planning, pairwise Natural Language Inference (NLI) consensus verification, and multi-dimensional trust modeling, the framework mitigates the risk of hallucinations and enhances response reliability. When internal confidence is insufficient, the system facilitates a controlled external web search fallback. This report reviews foundational literature, proposes an architectural pipeline based on these concepts, and discusses potential methodologies for evaluation."
));

// ---------- 2. Literature Review ----------
body.push(h1("2. Literature Review"));

const litReview = [
  {
    id: "2.1", title: "Adaptive-RAG",
    problem: "Traditional RAG systems apply a uniform retrieval pipeline to all queries, which can be computationally inefficient for simple queries and inadequate for complex reasoning tasks.",
    solution: "A dynamic routing mechanism that categorizes query complexity to determine the optimal retrieval strategy, thereby allocating computational resources more effectively.",
    strengths: "Reduces latency and computational overhead while improving accuracy for complex queries.",
    limitations: "The effectiveness is highly dependent on the accuracy of the underlying query classifier.",
    relation: "The architecture incorporates a query planning layer that evaluates query complexity based on linguistic heuristics. This layer dynamically adjusts timeout thresholds, confidence requirements, and selects active retrieval paths to optimize the execution strategy.",
  },
  {
    id: "2.2", title: "Self-RAG",
    problem: "RAG models often exhibit blind trust in retrieved information, leading to hallucinations if the retrieval quality is poor or contextually irrelevant.",
    solution: "Fine-tuning the LLM to generate reflection tokens that self-evaluate whether retrieval is necessary and whether the retrieved context adequately supports the generation.",
    strengths: "Improves output reliability and faithfulness without relying on external evaluators.",
    limitations: "Requires costly model fine-tuning, increases inference latency, and restricts the choice of foundational models.",
    relation: "Rather than relying on autoregressive reflection tokens, the architecture employs a deterministic consensus module. This module evaluates pairwise agreement across retrieved contexts prior to generation, significantly reducing the probability of the model processing conflicting data.",
  },
  {
    id: "2.3", title: "GraphRAG",
    problem: "Standard dense retrieval mechanisms frequently fail to capture global context and multi-hop relationships across extensive document corpora.",
    solution: "Extracting entities and relationships into a Knowledge Graph (KG) and retrieving interconnected subgraphs to provide holistic, structured context.",
    strengths: "Excels at complex reasoning, \u201cconnecting the dots,\u201d and answering global summarization queries.",
    limitations: "Graph construction is computationally expensive, and maintaining graph integrity during updates presents significant engineering challenges.",
    relation: "The current architecture includes foundational data models designed for future GraphRAG integration. The active retrieval phase currently prioritizes dense vector approaches, while graph traversal is reserved as a future architectural extension.",
  },
  {
    id: "2.4", title: "LightRAG",
    problem: "Comprehensive GraphRAG implementations often suffer from high latency and substantial computational costs during both graph construction and retrieval.",
    solution: "A dual-level retrieval system that combines low-level entity retrieval with high-level relationship retrieval, facilitating faster graph traversal.",
    strengths: "Reduces retrieval latency compared to exhaustive GraphRAG methodologies while preserving relationship awareness.",
    limitations: "Performance remains dependent on the quality and accuracy of the initial entity extraction phase.",
    relation: "Dual-level graph retrieval is designed for future integration. The current system maintains compatibility with this paradigm while optimizing performance through single-stage dense retrieval.",
  },
  {
    id: "2.5", title: "HyDE (Hypothetical Document Embeddings)",
    problem: "There is frequently a semantic mismatch between short, ambiguous user queries and long, detailed document chunks in the knowledge base.",
    solution: "Utilizing an LLM to generate a hypothetical answer to the query, embedding that answer, and retrieving documents similar to the hypothetical embedding.",
    strengths: "Effectively bridges the semantic gap without requiring explicit relevance labels or query rewriting.",
    limitations: "Introduces additional generation latency and risks retrieving off-topic documents if the hypothetical answer hallucinates.",
    relation: "The current implementation prioritizes low-latency retrieval by embedding raw user queries directly. Hypothetical document generation is reserved as a potential future extension for domain-specific adaptations where latency constraints are less strict.",
  },
  {
    id: "2.6", title: "CRAG (Corrective Retrieval Augmented Generation)",
    problem: "The introduction of irrelevant retrieved documents into the LLM context window severely degrades generation quality and factuality.",
    solution: "A lightweight retrieval evaluator assesses document relevance. If internal documents are deemed incorrect or ambiguous, the system triggers a large-scale web search as a corrective fallback mechanism.",
    strengths: "Highly robust against incomplete or low-quality internal knowledge bases.",
    limitations: "Web search can introduce unverified external data and variable latency.",
    relation: "The framework natively adopts the corrective philosophy through a trust calibration layer. If the calibrated trust score falls below a dynamically determined threshold, the system triggers an external search fallback mechanism to retrieve supplementary context prior to generation.",
  },
  {
    id: "2.7", title: "MemoRAG",
    problem: "Standard RAG pipelines lack long-term context retention, limiting their utility in multi-turn, complex reasoning tasks.",
    solution: "A dual-system architecture utilizing a memory model to build a global memory representation over the database, guiding subsequent retrieval and generation.",
    strengths: "Maintains state and contextual awareness over extended horizons.",
    limitations: "Imposes significant memory overhead and requires complex state management infrastructure.",
    relation: "The architecture features a session management module that injects historical conversational context into the prompt. Global memory retrieval over the entire corpus maintains compatibility with future architectural expansions.",
  },
  {
    id: "2.8", title: "LongRAG",
    problem: "Segmenting documents into small chunks often destroys macroscopic document-level context and narrative continuity.",
    solution: "Leveraging LLMs with massive context windows to retrieve and process entire documents or exceedingly long chunks, preserving structural integrity.",
    strengths: "Preserves document integrity and facilitates macro-structural reasoning.",
    limitations: "Entails exceedingly high token costs, increases inference latency, and may exceed the effective attention span of the LLM.",
    relation: "The current framework utilizes granular document segmentation. This approach optimizes for low token usage and precise cross-encoder reranking, while processing of full-length documents remains a consideration for future iterations.",
  },
  {
    id: "2.9", title: "Reciprocal Rank Fusion (RRF)",
    problem: "Integrating and normalizing results from multiple disparate retrieval algorithms (e.g., dense vector search and sparse lexical search) poses a significant ranking challenge.",
    solution: "An algorithm that combines ranked lists by assigning scores based on the inverse of their rank position, effectively smoothing out anomalies and highlighting consistent documents.",
    strengths: "Simple, parameter-free, and highly effective for standardizing hybrid search results.",
    limitations: "Can be suboptimal if one retrieval method is significantly more accurate than the others.",
    relation: "RRF is designed for future integration alongside sparse and graph retrieval models. The current system focuses on optimizing a single dense retrieval pipeline, rendering fusion algorithms unnecessary at this stage.",
  },
  {
    id: "2.10", title: "Platt Scaling / Confidence Calibration",
    problem: "Classifier and retrieval distance scores are often uncalibrated and do not represent true statistical probabilities, making thresholding unreliable.",
    solution: "Applying logistic regression (Platt scaling) to model outputs to transform raw scores into reliable, bounded probability distributions.",
    strengths: "Yields mathematically sound confidence scores that can be used for reliable decision-making.",
    limitations: "Requires careful tuning of weights and biases to prevent overconfidence or underconfidence.",
    relation: "The framework includes a dedicated confidence calibration module that applies logistic scaling to a multi-dimensional feature vector (incorporating retrieval scores, consensus metrics, and citation coverage) to produce a definitive, normalized trust probability.",
  },
];

litReview.forEach((item, idx) => {
  if (idx === 0) {
    body.push(h2(`${item.id} ${item.title}`));
  } else {
    body.push(h2(`${item.id} ${item.title}`));
  }
  body.push(labeledPar("Problem addressed", item.problem));
  body.push(labeledPar("Proposed solution", item.solution));
  body.push(labeledPar("Strengths", item.strengths));
  body.push(labeledPar("Limitations", item.limitations));
  body.push(labeledPar("How AEKOF incorporates or extends the idea", item.relation));
});

// ---------- 3. Comparative Analysis ----------
body.push(h1("3. Comparative Analysis"));
body.push(bodyPar(
  "Table 1 summarizes the core contributions, addressed problems, limitations, and the specific relationship of each methodology to the AEKOF framework."
));
body.push(tableCaption("Comparative Analysis of Foundational Literature"));
body.push(buildTable(
  ["Paper", "Core Contribution", "Problem Solved", "Limitations", "Relation to AEKOF"],
  [1250, 1750, 1750, 2150, 2120],
  [
    ["Adaptive-RAG", "Query complexity routing", "Inefficient static retrieval", "Dependent on accurate classification", "Adapted via a heuristic query planning layer"],
    ["Self-RAG", "Autoregressive reflection", "Blind trust in retrieved data", "High fine-tuning and latency costs", "Substituted with a deterministic consensus layer"],
    ["GraphRAG", "Subgraph context retrieval", "Loss of macroscopic context", "High extraction and maintenance cost", "Designed for future architectural integration"],
    ["LightRAG", "Dual-level graph traversal", "Graph retrieval latency", "Relies on initial extraction quality", "Reserved as a future architectural extension"],
    ["HyDE", "Hypothetical embeddings", "Semantic query-document mismatch", "Introduces pre-retrieval latency", "Current focus on direct query embedding"],
    ["CRAG", "Evaluation and web fallback", "Degradation from poor retrieval", "External data reliability risks", "Implemented via calibrated corrective fallback"],
    ["MemoRAG", "Global memory models", "Lack of multi-turn state retention", "Significant computational overhead", "Implemented via session context injection"],
    ["LongRAG", "Unsegmented retrieval", "Destruction of narrative continuity", "High token utilization", "Current focus on granular chunk optimization"],
    ["RRF", "Multi-list rank fusion", "Normalization of hybrid results", "Assumes comparable list quality", "Designed for future hybrid search integration"],
    ["Platt Scaling", "Logistic score calibration", "Unreliable raw retrieval scores", "Requires precise weight optimization", "Implemented via multi-dimensional calibration"],
  ]
));

// ---------- 4. Proposed Architecture ----------
body.push(h1("4. Proposed Architecture"));
body.push(bodyPar(
  "The proposed architecture of the AEKOF system is modular and strictly layered, separating retrieval concerns from generation and evaluation. The comprehensive flow, components, and sequences are illustrated in Figures 1, 2, and 3 respectively in Section 5."
));

const layers = [
  {
    id: "4.1", title: "Query Planning Layer",
    purpose: "Analyzes incoming queries to establish execution parameters, dynamically routing the request based on linguistic complexity.",
    inputs: "Natural language user query.",
    outputs: "An execution plan defining the complexity classification, timeout constraints, and required confidence thresholds.",
    interaction: "Operates as the entry point, directly influencing the stringency of the Confidence Layer and the active paths in the Retrieval Layer.",
    rationale: "Reduces computational waste by preventing complex retrieval operations for simple factual queries, enhancing overall system throughput.",
  },
  {
    id: "4.2", title: "Retrieval Layer",
    purpose: "Identifies and extracts semantically relevant information from the indexed knowledge corpus.",
    inputs: "Embedded representation of the user query.",
    outputs: "A candidate set of document segments.",
    interaction: "Receives execution parameters from the Query Planning Layer and passes candidates forward to the Ranking Layer.",
    rationale: "Utilizes dense vector similarity to prioritize semantic intent over lexical matching, providing a foundational baseline of relevant context.",
  },
  {
    id: "4.3", title: "Ranking Layer",
    purpose: "Refines and reorders the initial candidate set to surface the most contextually appropriate segments.",
    inputs: "User query and raw text of candidate segments.",
    outputs: "A strictly ordered list of segments with updated relevance scores.",
    interaction: "Acts as an intermediary, filtering the broad results of the Retrieval Layer before computationally intensive evaluation by the Confidence Layer.",
    rationale: "Decouples fast, coarse retrieval (bi-encoders) from slower, highly accurate scoring (cross-encoders), optimizing the balance between latency and precision.",
  },
  {
    id: "4.4", title: "Confidence Layer",
    purpose: "Evaluates the integrity, consensus, and sufficiency of the ranked evidence to determine if it is safe to proceed to generation.",
    inputs: "Ranked document segments, relevance scores, and internal consensus metrics derived from pairwise semantic overlap.",
    outputs: "A normalized trust probability and a binary routing decision (sufficient vs. insufficient).",
    interaction: "Gates access to the Generation Layer. If the trust probability fails to meet the threshold set by the Query Planning Layer, it triggers a corrective external retrieval mechanism.",
    rationale: "Mitigates hallucinations by ensuring the LLM is only provided with mathematically verified, non-contradictory information.",
  },
  {
    id: "4.5", title: "Generation Layer",
    purpose: "Synthesizes the final natural language response based on verified evidence.",
    inputs: "Conversational history, verified document segments, and the user query.",
    outputs: "The final response text.",
    interaction: "Receives only vetted context from the Confidence Layer, ensuring high faithfulness to the source material.",
    rationale: "Isolates the non-deterministic LLM generation at the very end of the pipeline, strictly constraining its operational boundaries to the provided context.",
  },
  {
    id: "4.6", title: "Citation Layer",
    purpose: "Grounds the generated response in verifiable source material, ensuring traceability.",
    inputs: "Metadata associated with the utilized document segments.",
    outputs: "Structured reference data appended to the final response.",
    interaction: "Operates in parallel with the Generation Layer, mapping text spans to their origin points.",
    rationale: "Enhances user trust and facilitates auditing by providing transparent links to enterprise source documents.",
  },
];

layers.forEach((l) => {
  body.push(h2(`${l.id} ${l.title}`));
  body.push(labeledPar("Purpose", l.purpose));
  body.push(labeledPar("Inputs", l.inputs));
  body.push(labeledPar("Outputs", l.outputs));
  body.push(labeledPar("Interaction", l.interaction));
  body.push(labeledPar("Design rationale", l.rationale));
});

// ---------- 5. Architecture Diagrams ----------
body.push(h1("5. Architecture Diagrams"));

body.push(h2("5.1 System Architecture Flowchart"));
body.push(bodyPar(
  "As shown in Figure 1, the execution pipeline begins with the user query and routes through the various verification and retrieval layers before culminating in a grounded generation."
));
body.push(imageParagraph("fig1", 2.7, 7.56));
body.push(figureCaption("System Architecture Flowchart"));

body.push(h2("5.2 Component Architecture Diagram"));
body.push(bodyPar(
  "Figure 2 illustrates the modular boundaries and integration points across the core framework, separating knowledge management from orchestration and synthesis."
));
body.push(imageParagraph("fig2", 4.6, 6.03));
body.push(figureCaption("Component Architecture Diagram"));

body.push(h2("5.3 Sequence Diagram of the Execution Pipeline"));
body.push(bodyPar(
  "As depicted in Figure 3, the chronological execution ensures that external corrective fallbacks are only triggered following rigorous internal evaluation."
));
body.push(imageParagraph("fig3", 6.27, 4.965));
body.push(figureCaption("Sequence Diagram of the Execution Pipeline"));

// ---------- 6. Novel Contributions ----------
body.push(h1("6. Novel Contributions"));
body.push(bodyPar("The proposed architecture introduces several methodological enhancements to standard RAG deployments:"));
body.push(labeledPar("Multi-Dimensional Confidence Calibration", "By moving beyond raw vector distance, the architecture scales multiple semantic features into a unified probabilistic trust score. This facilitates rigorous thresholding policies in enterprise settings."));
body.push(labeledPar("Pre-Generation Consensus Verification", "Implementing NLI-inspired pairwise comparison matrices allows the system to detect and penalize contradictory evidence before it reaches the language model, preemptively reducing hallucination rates."));
body.push(labeledPar("Adaptive Corrective Routing", "The integration of dynamic thresholds based on query complexity ensures that corrective mechanisms (such as web fallbacks) are only invoked when mathematically justified, optimizing both latency and data reliability."));

// ---------- 7. Proposed Methodology ----------
body.push(h1("7. Proposed Methodology"));
body.push(bodyPar("The standard operational sequence of the proposed architecture is defined as follows:"));
body.push(labeledPar("Intent Analysis", "The incoming natural language query undergoes linguistic analysis to classify its complexity, which dictates the operational constraints for subsequent layers."));
body.push(labeledPar("Deterministic Evaluation", "The system first evaluates the query against predefined knowledge rules. If a high-confidence match is detected, the pipeline resolves immediately."));
body.push(labeledPar("Semantic Extraction", "The query is transformed into a dense vector representation and compared against the indexed corpus to extract a broad candidate set of informational segments."));
body.push(labeledPar("Precision Ranking", "A deep semantic interaction model re-evaluates the candidate set against the query, ordering the segments by relevance."));
body.push(labeledPar("Consensus and Calibration", "The top segments are cross-referenced for internal consistency. The resulting metrics are mathematically scaled to produce a final trust probability."));
body.push(labeledPar("Corrective Action (Conditional)", "If the trust probability is deemed insufficient, the system supplements the internal data with controlled external retrieval."));
body.push(labeledPar("Synthesis and Grounding", "The verified information, along with conversational context, is processed by the language model to synthesize the final output, which is strictly annotated with traceable citations."));

// ---------- 8. Technology Stack ----------
body.push(h1("8. Technology Stack"));
body.push(bodyPar("Table 2 provides a high-level overview of the underlying technology stack facilitating the AEKOF architecture."));
body.push(tableCaption("Technology Stack Overview"));
body.push(buildTable(
  ["Layer", "Component Category", "Academic / Technical Purpose"],
  [1700, 2500, 4820],
  [
    ["API", "High-Performance HTTP Server", "Facilitates asynchronous communication and endpoint orchestration"],
    ["Database", "Relational SQL Datastore", "Manages structured metadata, session history, and relational schemas"],
    ["Vector Database", "Native Vector Extension", "Enables high-throughput approximate nearest neighbor (ANN) and cosine similarity search"],
    ["Embedding / Reranking", "Local Inference Engine", "Executes bi-encoder and cross-encoder models for embedding and precision ranking"],
    ["LLMs", "Model Gateway", "Interfaces with foundational language models for natural language synthesis"],
    ["Workers", "Asynchronous Task Queue", "Processes background indexing, graph extraction, and data ingestion tasks"],
  ]
));

// ---------- 9. Future Work ----------
body.push(h1("9. Future Work"));
body.push(bodyPar("The current architecture provides a robust foundation for enterprise knowledge retrieval, but several avenues remain open for future expansion:"));
[
  ["GraphRAG Integration", "Activating the existing schema designs to extract and traverse knowledge graphs, enabling the system to answer complex, multi-hop queries that require global corpus context."],
  ["LightRAG Methodology", "Adopting a dual-level entity and relationship retrieval mechanism to optimize the latency of future graph traversal operations."],
  ["Hybrid BM25 + Dense Retrieval", "Incorporating sparse lexical retrieval (BM25) alongside dense vectors, fused via Reciprocal Rank Fusion (RRF), to improve recall for exact keyword matches and domain-specific acronyms."],
  ["Enterprise Knowledge Graph (EKG)", "Expanding the data model to support a unified EKG, integrating disparate organizational data silos into a single queryable semantic layer."],
  ["Adaptive Retrieval Selection", "Enhancing the Query Planning Layer with machine learning classifiers to dynamically route queries between dense, sparse, and graph retrieval pipelines based on historical performance data."],
  ["Incremental Knowledge Evolution", "Implementing feedback loops where user interactions and corrected hallucinations automatically update the underlying knowledge base, fostering a self-improving system."],
  ["Multi-Agent Reasoning", "Deploying specialized sub-agents for distinct tasks (e.g., data extraction, summarization, and formatting) to orchestrate complex analytical workflows beyond simple question-answering."],
].forEach(([label, text]) => body.push(labeledPar(label, text)));

// ---------- 10. Potential Evaluation Metrics ----------
body.push(h1("10. Potential Evaluation Metrics"));
body.push(bodyPar("To rigorously assess the performance of the proposed architecture, the following evaluation metrics are recommended:"));
[
  ["Recall@K", "Measures the proportion of relevant document segments successfully retrieved in the top K results, indicating the effectiveness of the initial Retrieval Layer."],
  ["Precision", "Evaluates the fraction of retrieved segments that are genuinely relevant to the query, assessing the accuracy of the Ranking Layer."],
  ["Mean Reciprocal Rank (MRR)", "Calculates the average of the reciprocal ranks of the first relevant segment, providing insight into the ranking algorithm\u2019s ability to surface correct answers quickly."],
  ["Normalized Discounted Cumulative Gain (NDCG)", "Assesses the ranking quality by assigning higher importance to highly relevant segments appearing at the top of the search results."],
  ["Faithfulness", "Measures the degree to which the LLM\u2019s generated response is supported exclusively by the retrieved context, penalizing external hallucinations."],
  ["Citation Accuracy", "Evaluates the correctness of the structural links between the generated text spans and the source metadata."],
  ["Latency / Response Time", "Quantifies the end-to-end execution time of the pipeline, essential for evaluating the computational overhead of the Confidence and Ranking Layers."],
  ["Hallucination Rate", "The frequency at which the system generates factually incorrect or unsupported statements, acting as the primary metric for the efficacy of the Confidence Layer."],
  ["Confidence Calibration Error", "Measures the deviation between the system\u2019s predicted trust probability and the actual empirical accuracy of the responses, validating the Platt scaling implementation."],
].forEach(([label, text]) => body.push(labeledPar(label, text)));

// ---------- 11. Conclusion ----------
body.push(h1("11. Conclusion"));
body.push(bodyPar(
  "The AEKOF architecture presents a disciplined, modular approach to Retrieval-Augmented Generation designed specifically for environments where accuracy and traceability are paramount. By explicitly moving away from paradigms that rely entirely on LLM self-reflection, the framework shifts the burden of verification to a deterministic mathematical pipeline. The implementation of a pre-generation consensus mechanism and a calibrated trust layer ensures that the risk of hallucinations is significantly mitigated before natural language synthesis occurs. Furthermore, the architecture\u2019s strict separation of concerns facilitates scalability and provides a clear trajectory for incorporating future advancements such as hybrid search fusion and knowledge graph traversal."
));

// ---------- 12. References ----------
body.push(h1("12. References"));
const refs = [
  "S. Baek et al., \u201cAdaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models,\u201d arXiv preprint arXiv:2403.14403, 2024.",
  "A. Asai et al., \u201cSelf-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection,\u201d arXiv preprint arXiv:2310.11511, 2023.",
  "D. Edge et al., \u201cFrom Local to Global: A Graph RAG Approach to Query-Focused Summarization,\u201d arXiv preprint arXiv:2404.16130, 2024.",
  "H. Guo et al., \u201cLightRAG: Simple and Fast Retrieval-Augmented Generation,\u201d arXiv preprint arXiv:2410.05779, 2024.",
  "L. Gao et al., \u201cPrecise Zero-Shot Dense Retrieval without Relevance Labels (HyDE),\u201d arXiv preprint arXiv:2212.10496, 2022.",
  "S. Yan et al., \u201cCorrective Retrieval Augmented Generation (CRAG),\u201d arXiv preprint arXiv:2401.15884, 2024.",
  "P. Lewis et al., \u201cMemoRAG: Memory-Augmented Retrieval-Augmented Generation,\u201d arXiv preprint arXiv:2409.05591, 2024.",
  "Z. Jiang et al., \u201cLongRAG: Enhancing Retrieval-Augmented Generation with Long-context LLMs,\u201d arXiv preprint arXiv:2406.15319, 2024.",
  "G. Cormack, C. Clarke, and S. Buettcher, \u201cReciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods,\u201d SIGIR, 2009.",
  "J. Platt, \u201cProbabilistic Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods,\u201d Advances in Large Margin Classifiers, 1999.",
];
refs.forEach((r, i) => {
  body.push(new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 360, lineRule: "auto", after: 140 },
    indent: { left: 540, hanging: 540 },
    children: [new TextRun({ text: `[${i + 1}] `, font: FONT, size: 24 }), new TextRun({ text: r, font: FONT, size: 24 })],
  }));
});

// ============================================================
// FOOTERS
// ============================================================
function pageNumberFooter(numberFormat) {
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })],
      }),
    ],
  });
}

// ============================================================
// DOCUMENT ASSEMBLY
// ============================================================
const doc = new Document({
  creator: "AEKOF Project Team",
  title: "Adaptive Enterprise Knowledge Operating Framework (AEKOF) — Literature Review and Proposed Architecture Report",
  styles: {
    default: {
      document: {
        run: { font: FONT, size: 24 },
        paragraph: { spacing: { line: 360, lineRule: "auto" } },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 32, bold: true, color: "000000" },
        paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "000000" },
        paragraph: { spacing: { before: 260, after: 160 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: "000000" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 },
      },
    ],
  },
  sections: [
    {
      properties: {
        page: PAGE,
        titlePage: true,
      },
      children: titlePageChildren,
    },
    {
      properties: {
        page: PAGE,
        titlePage: false,
        page: { ...PAGE, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } },
      },
      footers: { default: pageNumberFooter() },
      children: frontMatterChildren,
    },
    {
      properties: {
        page: { ...PAGE, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } },
      },
      footers: { default: pageNumberFooter() },
      children: body,
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  const outPath = path.join(__dirname, "AEKOF_Literature_Review_Report.docx");
  fs.writeFileSync(outPath, buffer);
  console.log("Wrote", outPath);
});
