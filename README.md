# Internal Policy Search Assistant

A RAG-based AI chatbot that allows compliance and risk teams to query 
internal policy documents in plain English and get accurate, cited answers instantly.

## Problem Statement
Finding specific policy answers across hundreds of pages of compliance 
documents takes hours. This bot does it in seconds.

## Features
- Conversational Q&A interface with memory
- Stays strictly within compliance and risk scope
- Admits when it doesn't have enough information
- Structured responses with policy area, answer, source and confidence level
- Powered by CFPB UDAAP Examination Manual

## Tech Stack
- Python
- Google Gemini API (gemini-2.5-flash)
- google-genai library
- Jupyter Notebook

## Project Status
🚧 Work in Progress — document loading complete, RAG retrieval coming next.

## Background
Built as part of an AI Engineer portfolio project, combining 7 years 
of financial services experience (5 years credit risk + 2 years controls) 
with applied AI engineering skills.

## Known Simplifications (v1) → Planned Improvements

This project is being built in intentional layers — starting with hand-rolled, simple implementations to build genuine understanding before adopting more advanced techniques. Current known simplifications:

- **Chunking**: Fixed-size, character-based chunking with overlap. Planned upgrade: token-based chunking (via `tiktoken`) and/or recursive chunking that respects paragraph/sentence boundaries — important for compliance docs where clauses shouldn't be cut mid-sentence.
- **Vector store**: Local ChromaDB, suitable for single-user/local demo. Production considerations (e.g. Pinecone, Weaviate) would apply at scale.
- **Retrieval**: Pure vector similarity search. Planned improvement: hybrid retrieval (keyword + vector) for exact regulatory term matching, which pure semantic similarity can miss.

## Known Limitations — Chunking Strategy (v1)

**Current approach:** Fixed-size character chunking (800 chars, 100 char overlap) applied to the full document text, flattened across all pages into a single string before splitting.

### Tradeoff considered: chunk-per-page vs. flatten-then-chunk

An earlier version of this pipeline chunked text on a per-page basis (preserving page numbers as chunk metadata) rather than on the flattened document. That approach was evaluated and intentionally reverted in favor of simplicity for v1. Documenting the tradeoff below:

| | Flatten-then-chunk (current) | Chunk-per-page (considered, reverted) |
|---|---|---|
| Page traceability | None — cannot cite which page an answer came from | Full — every chunk tagged with its source page |
| Clauses spanning a page break | Preserved — chunking flows continuously across the whole document, so a sentence/clause split across pages 5→6 stays intact within a chunk | Broken — chunking resets at every page boundary, so content is force-split at the page edge even mid-sentence, producing two disconnected chunks with no shared context |
| Implementation complexity | Low | Higher — requires restructuring PDF extraction to preserve page boundaries, and propagating metadata through chunking, embedding, and storage |
| Risk introduced | **Source citations are not verifiable to a specific page** — a compliance answer can point to "the document" but not "page 6," which weakens auditability | **Regulatory clauses that span a page break get semantically fragmented** — a clause split across two chunks may retrieve incompletely, so an answer could miss half a cross-page requirement |

### Known risks of the current (flattened) approach

- **No source page citation.** For a compliance/regulatory use case, this is the most significant limitation — an answer's "Source" field can quote text but can't point a reviewer to an exact page for verification.
- **Chunk boundaries are still character-count-based, not semantic.** Even without the page-per-chunk complication, fixed-size chunking can still cut mid-sentence or mid-clause anywhere in the document — this is a separate, already-noted limitation (see chunking strategy above) and applies regardless of the page tradeoff.
- **No easy path to page-level filtering.** Future features like "only search Section 4" or SQL-filtered hybrid retrieval by page/section are harder to bolt on later without reworking the chunking step.

### Planned resolution

Revisit with **recursive or semantic chunking** (splitting on paragraph/sentence boundaries rather than raw character counts) combined with **lightweight page-tracking metadata** — this would solve both problems at once: natural chunk boundaries (no more mid-sentence cuts) and traceability (page-level citations), without reintroducing the "hard split at every page edge" problem that per-page chunking caused. Deferred to a later iteration once the core retrieval pipeline (Steps 6.4–6.5) is working end to end.