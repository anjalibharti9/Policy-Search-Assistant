# Internal Policy Search Assistant

A RAG-based AI chatbot that allows compliance and risk teams to query internal policy documents in plain English and get source-quoted answers.

## Problem Statement
Finding specific policy answers in long compliance documents is slow and
manual. This bot retrieves the most relevant passages and answers from them
in plain English.

## Features
- Retrieval-augmented Q&A over a policy document (each question answered independently, no conversation memory)
- Stays strictly within compliance and risk scope
- Admits when it doesn't have enough information
- Structured responses with policy area, answer, source and confidence level
- Powered by CFPB UDAAP Examination Manual

## Example

**Question:** What counts as an unfair act under UDAAP?

```
Policy Area: UDAAP
Answer: An act or practice is considered unfair when it causes or is likely to cause substantial injury to consumers, the injury is not reasonably avoidable by consumers, and the injury is not outweighed by countervailing benefits to consumers.
Source: "Act is that an act or practice is unfair when: (1) It causes or is likely to cause substantial injury to consumers; (2) The injury is not reasonably avoidable by consumers; and (3) The injury must not be outweighed by countervailing benefits to consum"
Confidence: High
```

Retrieved chunks: 0, 3, 8 (similarity scores 0.78, 0.76, 0.74)

## Tech Stack
- Python
- Google Gemini API (gemini-2.5-flash, gemini-embedding-001)
- google-genai library
- FAISS (vector search)
- pypdf (PDF parsing)
- Jupyter Notebook

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create a Gemini API key in Google AI Studio. In the project folder, create
   a file named `.env` containing one line: `GEMINI_API_KEY=your-key-here`
   (this file is gitignored and never uploaded).
3. Open `compliance_bot.ipynb` and run all cells from top to bottom. This
   parses the PDF, creates the chunks and embeddings, and builds the FAISS
   index (saved to `faiss_index/`).
4. To ask your own question, add a new cell at the end of the notebook and run:

```python
answer, sources = generate_rag_response("Your question here", index, chunk_id_to_text, client, system_instruction_rag)
print(answer)
```

## Project Status
✅ Core RAG pipeline complete (Steps 1–6): chat loop, memory, system prompt,
document loading, chunking, embedding, FAISS indexing, retrieval, and
grounded generation — all built and validated end to end, including an
eval pass confirming the bot refuses to hallucinate on out-of-scope questions.

🚧 Next: Advanced RAG phase (see Known Limitations below).

## Background
Built as part of an AI Engineer portfolio project, combining 7 years
of financial services experience (5 years credit risk + 2 years controls)
with applied AI engineering skills.

---

## Pipeline Overview (Steps 1–6)

**Step 1 — Chat loop**: Basic interactive loop using `client.chats.create()` and
`chat.send_message()` in a `while True` loop, reading user input and printing model
responses until an exit keyword (`end`/`quit`/`bye`/`goodbye`).

**Step 2 — Memory**: Multi-turn conversation handled via Gemini's native `chats`
session object, which persists conversation history across turns automatically.

**Step 3 — System prompt**: Role-prompted the model as a senior compliance officer,
combining role prompting, chain-of-thought, constraint prompting, few-shot examples,
and a fixed output format. Initial version (`chat`) embedded the entire source
document directly into the system instruction — functional for a single small PDF,
but not scalable (see Step 6).

**Step 4 — GitHub setup**: Repo initialized with a `master` branch; workflow is to
edit locally in VS Code only, never directly on GitHub, to avoid merge conflicts.

**Step 5 — PDF loading**: CFPB UDAAP PDF parsed via `pypdf`, with all pages flattened
into a single string (`document_text`) using `reader.pages` + `extract_text()`.

**Step 6 — True RAG (embeddings + vector search)**:
- **6.1–6.3 — Chunking & embedding**: Document split into fixed-size chunks
  (chunk_size=800, overlap=100 → 63 chunks); each chunk embedded via
  `gemini-embedding-001` (3072 dimensions). An earlier version added page-level
  chunk metadata and retry logic on embedding calls — both were intentionally
  reverted in favor of simplicity for v1 (see Known Limitations).
- **6.4 — Vector store**: Embeddings indexed in **FAISS** (switched from ChromaDB
  after a persistent crash — see Known Limitations). Vectors L2-normalized and
  indexed with `IndexFlatIP`, so inner product search is equivalent to cosine
  similarity. Index and a `chunk_id_to_text` mapping persisted to disk
  (`faiss_index/`, gitignored).
- **6.5 — Retrieval**: `search_policy()` embeds a query, normalizes it, searches
  the FAISS index, and returns the top-k matching chunks with similarity scores —
  validated against a real UDAAP question with relevant results (see Retrieval
  Validation).
- **6.6 — Generation**: `generate_rag_response()` retrieves the top-k chunks per
  query and sends them, together with the question, to Gemini (`generate_content`)
  under a system instruction (`system_instruction_rag`) that contains only the rules
  and output format, not the full document. This replaces the Step 3 approach of
  stuffing the entire document into context, making the pipeline scalable to
  multiple/larger policy documents. Each query is answered independently, with no
  conversation memory. A structured-output formatting issue came up along the way
  (see Prompt Engineering below).
- **6.7 — Eval pass**: Tested an out-of-scope query to confirm the bot refuses to
  hallucinate rather than answering from general knowledge (see Retrieval
  Validation).

**Key shift**: Steps 1–5 (and the original Step 3 `chat`) relied on the model seeing
the *entire* document on every turn. Step 6 moves to retrieval-augmented generation —
only the most relevant excerpts are retrieved and passed per-query, which is the
core architectural difference between "an LLM with a document pasted in" and "RAG."

---

## Vector Store & Similarity Search

- **Vector store switch (ChromaDB → FAISS)**: Originally planned to use ChromaDB,
  but hit a persistent native access-violation crash (`0xC0000005`) in
  `collection.add()` on Windows (VS Code + Jupyter, Python 3.12, anaconda3) that
  survived kernel/environment fixes, a chromadb reinstall, switching to an
  in-memory client, and confirming embeddings were valid. Older chromadb versions
  couldn't be installed either, since they require `chroma-hnswlib` built from
  source, which needs MS Visual C++ Build Tools (not present on this machine).
  Pinecone was briefly considered as an alternative before settling on **FAISS**,
  which avoids the native library issue entirely and offers deeper learning value
  (its lower-level API exposes vector search internals directly, vs. Chroma's
  managed abstraction).

- **Similarity metric**: Embeddings are L2-normalized (`faiss.normalize_L2()`)
  before indexing, and searched using `IndexFlatIP` (inner product). Inner product
  on unit-normalized vectors is mathematically equivalent to cosine similarity,
  which is the standard metric for text embeddings — embedding models encode
  semantic meaning in vector *direction*, not magnitude, so cosine (angle-based)
  similarity aligns with how the model was trained, unlike Euclidean
  (`IndexFlatL2`) distance, which is magnitude-sensitive. Any future query
  embedding must also be normalized before search to preserve this equivalence.

- **Index type**: Using `IndexFlatIP` — brute-force exact search, no approximation.
  Appropriate at current scale (63 chunks); would need an approximate index (IVF,
  HNSW) with a training step at production scale.

- **No per-chunk metadata**: Chunks are stored with no source/document tagging
  (e.g. no `source: CFPB_UDAAP.pdf` field). Fine with a single source document;
  will need metadata once multiple policy PDFs are indexed — planned for the
  Advanced RAG phase.

- **In-memory chunk-to-text mapping**: FAISS only stores vectors and returns index
  positions, not text. A plain Python dict (`chunk_id_to_text`) maps FAISS index
  positions back to original chunk text, relying on stable insertion order from a
  single batched `index.add()` call. This mapping is persisted to disk as JSON
  alongside the FAISS index, but the approach would break if chunks were later
  added/removed incrementally rather than as one batch — acceptable for v1, worth
  revisiting if the pipeline moves to incremental indexing.

---

## Retrieval Validation

**On-topic test** — query: *"What counts as an unfair act under UDAAP?"* against
the 63-chunk FAISS index (cosine similarity via L2-normalized vectors + IndexFlatIP).

Top 3 results:
1. **Chunk 0** (score 0.78) — UDAAP overview/introduction section
2. **Chunk 3** (score 0.76) — the actual three-part legal test for "unfair" acts
   (direct answer to the query)
3. **Chunk 8** (score 0.74) — footnote elaborating on the unfairness standard

**Observation**: the most directly relevant chunk (the legal test itself) scored
slightly lower than the general overview chunk. This reflects a known limitation
of plain semantic similarity — broad/introductory text can rank highly by touching
many topics shallowly, even when a narrower chunk is more precisely on-point.
Addressing this (e.g. via hybrid retrieval or reranking) is noted below rather
than solved in v1.

**Off-topic eval test** — query: *"What is the minimum credit score required for a
mortgage under this policy?"* (not covered by the UDAAP document).

Result: the bot correctly responded "This information is not available in the
provided document," with Source "N/A" and High confidence — rather than answering
from Gemini's general training knowledge of typical mortgage underwriting, which
it almost certainly has. This confirms the grounding instruction holds even under
pressure from a plausible-sounding, adjacent-domain question.

Retrieved chunks for this query: 60, 48, 56 — FAISS still returns top-k chunks
regardless of relevance (it has no built-in "no good match" concept), so scores
matter more than chunk presence here.

**Score comparison**: on-topic query scored 0.74–0.78; off-topic query scored
0.58–0.61. The ~0.15 gap suggests similarity scores could serve as a usable signal
for a future relevance threshold (e.g. reject retrieval below ~0.65), even without
building a full reranker — a lightweight improvement worth testing before the
reranker phase of the roadmap.

---

## Prompt Engineering: System Instruction vs. User-Turn Reinforcement

Initially, the output format (`Policy Area / Answer / Source / Confidence`) was
defined only in the system instruction. In practice, gemini-2.5-flash did not
reliably follow this format — responses came back as unstructured prose despite
the system prompt explicitly requiring it.

**Fix**: the format requirement was repeated in the user-turn prompt itself
(alongside the retrieved context and question), not just stated once in the
system instruction. This resolved the issue consistently.

**Takeaway**: system instructions set persistent behavior/role, but formatting and
output-structure requirements are more reliably enforced when reinforced per-turn,
especially in multi-turn chat sessions where the system instruction is set once at
session creation and may get deprioritized relative to the live conversation turn.

**Current implementation**: `generate_rag_response()` now calls `generate_content`
(single-turn) with `system_instruction_rag` passed as the system instruction, and
the output format is still repeated in the user-turn prompt. The formatting drift
described above was observed in the earlier chat-session version
(`chat_rag.send_message()`). Whether the per-turn reinforcement is still necessary
in the single-turn version has not been tested.

---

## Known Limitations (v1) → Planned Improvements

This project is being built in intentional layers — starting with hand-rolled,
simple implementations to build genuine understanding before adopting more
advanced techniques.

### Chunking
- **Current approach**: Fixed-size, character-based chunking (800 chars, 100 char
  overlap), applied to the full document text flattened across all pages into a
  single string before splitting.
- **Reverted complexity**: An earlier version added page-level chunk metadata and
  retry logic (try/except) on embedding calls, as production-style hardening. Both
  were intentionally reverted — decided it added too much complexity for v1.
- **Planned upgrade**: token-based chunking (via `tiktoken`) and/or recursive
  chunking that respects paragraph/sentence boundaries — important for compliance
  docs where clauses shouldn't be cut mid-sentence.

### Tradeoff considered: chunk-per-page vs. flatten-then-chunk

An earlier version of this pipeline chunked text on a per-page basis (preserving
page numbers as chunk metadata) rather than on the flattened document. That
approach was evaluated and intentionally reverted in favor of simplicity for v1.

| | Flatten-then-chunk (current) | Chunk-per-page (considered, reverted) |
|---|---|---|
| Page traceability | None — cannot cite which page an answer came from | Full — every chunk tagged with its source page |
| Clauses spanning a page break | Preserved — chunking flows continuously across the whole document, so a sentence/clause split across pages 5→6 stays intact within a chunk | Broken — chunking resets at every page boundary, so content is force-split at the page edge even mid-sentence, producing two disconnected chunks with no shared context |
| Implementation complexity | Low | Higher — requires restructuring PDF extraction to preserve page boundaries, and propagating metadata through chunking, embedding, and storage |
| Risk introduced | **Source citations are not verifiable to a specific page** — a compliance answer can point to "the document" but not "page 6," which weakens auditability | **Regulatory clauses that span a page break get semantically fragmented** — a clause split across two chunks may retrieve incompletely, so an answer could miss half a cross-page requirement |

**Known risks of the current (flattened) approach:**
- **No source page citation.** For a compliance/regulatory use case, this is the
  most significant limitation — an answer's "Source" field can quote text but
  can't point a reviewer to an exact page for verification.
- **Chunk boundaries are still character-count-based, not semantic.** Even without
  the page-per-chunk complication, fixed-size chunking can still cut mid-sentence
  or mid-clause anywhere in the document.
- **No easy path to page-level filtering.** Future features like "only search
  Section 4" or SQL-filtered hybrid retrieval by page/section are harder to bolt
  on later without reworking the chunking step.

**Planned resolution**: Revisit with **recursive or semantic chunking** (splitting
on paragraph/sentence boundaries rather than raw character counts) combined with
**lightweight page-tracking metadata** — this would solve both problems at once:
natural chunk boundaries (no more mid-sentence cuts) and traceability (page-level
citations), without reintroducing the "hard split at every page edge" problem that
per-page chunking caused. Deferred to a later iteration.

### Vector store
Local FAISS index (`IndexFlatIP`, brute-force exact search), suitable for
single-user/local demo at small scale (63 chunks). See "Vector Store &
Similarity Search" above for the full ChromaDB→FAISS migration story. Production
considerations (e.g. approximate indexes like IVF/HNSW, or managed services like
Pinecone/Weaviate) would apply at scale.

### Retrieval
Pure vector similarity search, no relevance threshold (see Retrieval Validation —
FAISS always returns top-k regardless of relevance). Planned improvements:
- Hybrid retrieval (keyword + vector) for exact regulatory term matching, which
  pure semantic similarity can miss.
- A lightweight similarity-score threshold (e.g. reject below ~0.65) as a cheap
  relevance gate, based on the measured 0.15 score gap between on-topic and
  off-topic queries.
- A reranker (e.g. RankGPT-style) as a heavier, more accurate alternative once the
  threshold approach is tested.

### Metadata
No per-chunk source/document tagging. Fine for a single source document; required
once multiple policy PDFs are indexed together.

### Planned roadmap (Advanced RAG phase)
1. HyDE / multi-query for query translation
2. Semantic or parent-document chunking (see Chunking above)
3. Re-ranker (RankGPT-style) post-retrieval
4. Corrective RAG — score retrieved docs, trigger re-retrieval/fallback if weak
5. Graph RAG (stretch) — Text-to-Cypher over a graph DB for regulatory cross-references
6. Agentic RAG — Self-RAG/RRR-style self-critique to decide on re-retrieval