# Policy Search Assistant v2 (Advanced RAG): Step 7 Build Log

CFPB UDAAP RAG bot. This file covers the v2 work (Step 7) up to the multi-query evaluation (7A.3): the plan, decisions, evaluation results, errors, fixes and open questions. The original v1 (Steps 1-6) is preserved under the git tag `v1-faiss`.

## 1. Where things stand

| Item | Status |
|---|---|
| v1 (Steps 1-6) | Frozen with git tag `v1-faiss`; original notebook and README untouched |
| v2 scaffold | `compliance_bot_v2.ipynb` and `README_v2.md` created as new files |
| 7A.1 Baseline eval | Done: Hit@5 4/5, MRR 0.600 (labels in `eval_set.json`) |
| 7A.2 Variant generation | Done: 3 clean variants per query, all 18 generated with `gemini-3.5-flash-lite` and saved in `query_variants.json` |
| 7A.3 Multi-query + RRF | Done: Hit@5 4/5, MRR 0.500. Did not beat the baseline on this small eval set (see section 5) |
| Next | Side-by-side diagnostic of baseline vs multi-query rankings, then HyDE (7A.4) and the comparison (7A.5) |

## 2. Step 7 plan and decisions

| Part | Work |
|---|---|
| 7A | Baseline eval set, then multi-query and HyDE |
| 7B | Reranking |
| 7C | pgvector migration + SQL metadata filtering (page-level metadata added during migration; re-run eval right after to confirm scores match the FAISS baseline) |
| 7D | FastAPI wrapper + deployed demo |
| 7E | README update with before/after eval numbers |
| 7F | Corrective RAG (last) |

**Decisions made**

- Project 1 is the active focus; the missing production pieces go into Step 7.
- No LangChain / LlamaIndex in Project 1 so far (built by hand so every layer is understood). Open options: a small LlamaIndex comparison notebook after 7E, and LangGraph for 7F.
- Semantic / parent-document chunking, Graph RAG and Agentic RAG from the earlier six-item roadmap are not in the production list. If chunking is wanted, do it as its own step, not inside the 7C migration, otherwise chunk IDs change and the "scores match" check proves nothing.
- README plan: keep `README.md` untouched during Step 7. At 7E, either `git mv README.md README_v1_faiss.md` and make the new README the landing page, or keep `README.md` permanently. Decide then.
- The v2 notebook is standalone: it copies the v1 setup cells (load, chunk, embed, FAISS, `search_policy`) and rebuilds the index in memory each run. The chat-session and save-to-disk cells were left out so v2 cannot overwrite v1's saved files.
- Answer generation (`system_instruction_rag`, `generate_rag_response()`) is not in v2 yet. It is added at the end of 7A and must be present before 7D.

## 3. Why FAISS (and not ChromaDB)

- ChromaDB crashed on the Windows machine (native access-violation error on `collection.add()`), surviving kernel and environment fixes, a reinstall and an in-memory client.
- FAISS installed cleanly and also taught more: manual normalisation, `IndexFlatIP` on unit vectors (= cosine similarity), and the chunk-ID-to-text mapping.
- Costs: vectors only (no text or persistence), no metadata filtering, no relevance threshold. pgvector at 7C addresses the first two.

## 4. Baseline evaluation (7A.1)

Six test queries: 2 direct, 2 vague, 1 mismatch, 1 out of scope. Labels were chosen by reading the full chunks; a chunk counts as relevant only if it contains the answer.

| Query | Type | Labeled relevant chunks | First relevant rank | Result |
|---|---|---|---|---|
| q1 What counts as an unfair act? | direct | 3, 4 | 2 | hit, rr 0.50 |
| q2 How is an abusive practice defined? | direct | 33, 34 | 2 | hit, rr 0.50 |
| q3 Can we hide fees in the fine print? | vague | 19, 27, 53 | 1 | hit, rr 1.00 |
| q4 Pressure customers into signing up quickly? | vague | 33 (inferred) | not in top 5 | miss |
| q5 What makes a disclosure misleading? | mismatch | 18, 22 | 1 | hit, rr 1.00 |
| q6 Minimum credit score for a mortgage? | out of scope | none | n/a | top score 0.541 |

**Baseline: Hit@5 = 4/5, MRR = 0.600.** Labels are saved in `eval_set.json` with a text anchor per chunk so they can be re-mapped if chunk IDs change.

## 5. Multi-query (7A.2 and 7A.3)

**Design**

- `gemini-3.5-flash-lite` rewrites each question into 3 differently worded queries, using regulatory vocabulary where it fits.
- Each of the 4 queries (original + 3 variants) searches FAISS (top 10); results are merged with reciprocal rank fusion (RRF): each chunk scores the sum of 1/(60 + rank) over the lists it appears in, and the top 5 are kept.
- Variants are cached to `query_variants.json` so the eval is reproducible (rewrites differ on every run at temperature 0.7).
- RRF scores (max about 0.066) are not cosine similarities and cannot be compared with the baseline's top scores.

**Results**

| Query | Baseline rr | Multi-query rr | Change |
|---|---|---|---|
| q1 | 0.50 | 1.00 | better |
| q2 | 0.50 | 0.50 | same |
| q3 | 1.00 | 0.50 | worse |
| q4 | 0.00 | 0.00 | still a miss |
| q5 | 1.00 | 0.50 | worse |
| **Hit@5 / MRR** | **4/5 / 0.600** | **4/5 / 0.500** | slightly worse |

**Reading of the result**

- Multi-query did not beat the baseline on this 5-query set. The sample is tiny (two queries each dropping one rank moves MRR by 0.1), so this is "has not helped yet", not proof that it hurts.
- q1 improved: one variant used "substantial injury" and "reasonable consumer avoidability", the exact elements of the unfairness test in chunks 3 and 4.
- q4 stayed a miss. The variants used "high-pressure", "coercive" and "deceptive" wording, none said "abusive" or "unreasonable advantage", and the top 5 filled with deception chunks (20, 2, 22, 0, 47); chunk 33 never appeared. Rewriting can steer a query away from the document's vocabulary as easily as toward it.
- Why q3 and q5 dropped is a hypothesis, not a finding: RRF rewards chunks that several variants agree on, so a chunk ranked #1 for the original wording may be outvoted. The ranked lists need to be inspected before drawing a conclusion.
- The out-of-scope query q6 scored 0.065 under RRF (maximum possible 0.066): its rewritten variants all agreed on the same chunk. Agreement across variants is not relevance, so RRF scores cannot flag off-topic queries.

## 6. Errors, causes and fixes

| # | What happened | Cause | Fix |
|---|---|---|---|
| 1 | Variants cut off mid-word (q1, q2) | `gemini-2.5-flash` "thinking" tokens count against `max_output_tokens`; a limit of 300 was mostly used up before the answer | Turn thinking down and raise the limit (`thinking_budget=0`, 1024 tokens on 2.5; `thinking_level="minimal"`, 2048 tokens on 3.5) |
| 2 | `ServerError` crashed the run on q3 | Transient overload on Google's side | Retry with backoff |
| 3 | q4 returned an `<h2>` heading and "1." / "2." prefixes despite "no numbering or extra text" | LLMs do not reliably follow formatting rules; the code would have searched the heading as a query, silently skewing results | Clean the output in code: regex strips numbering and bullets, filter drops lines starting with `<` or ending with `:` |
| 4 | Repeated `ClientError 429` with long waits | Initially misread as a per-minute limit. The real cause: the free tier allows only 20 `generate_content` requests per day per project per model for `gemini-2.5-flash` (quota `GenerateRequestsPerDayPerProjectPerModel-FreeTier`), and repeated test loops used it up | Cache every LLM output to disk; remove test loops that re-call Gemini; stop retrying on per-day errors (the error text contains `PerDay`); use a model with free quota left. Embedding calls have a separate quota and kept working |
| 5 | `404 NOT_FOUND` when switching to `gemini-2.5-flash-lite` | Model retired for new users; model names change over time | Use the model Google's error recommends (`gemini-3.5-flash-lite`), keep the name in one constant (`REWRITE_MODEL`), and set `thinking_level` instead of `thinking_budget` |
| 6 | `NameError: generate_query_variants is not defined` | The helpers cell had been deleted or not re-run after a kernel restart; a notebook only knows functions from cells that have run | Keep the helpers cell before the prep cell and run the notebook top to bottom after any restart |
| 7 | All six variants showed "(generated)" after the quota error | The variants only lived in memory when the cell crashed, so the file was never written | Save to `query_variants.json` after each query so a crash cannot lose finished work |

**Lessons:** a per-day quota cannot be fixed by waiting and retrying, so read the full error message first; it names the exact quota. Cache every LLM output to disk. Keep model names in one place, because they get retired.

## 7. Findings and pushbacks along the way

- **Overview chunk crowds out precise chunks.** Chunk 0 (the intro) outranks the chunks holding the actual definitions for q1 and q2. This is the target for reranking (7B).
- **q4 is a real miss, and the document has no direct coverage of high-pressure sales.** Keyword searches for "pressure", "urgent" and "take advantage" returned nothing. The closest text is chunk 33 (abusive = takes unreasonable advantage), so the q4 label is inferred and is stated as such.
- **A simple score threshold would not work.** Vague but legitimate queries (q3, q4) score 0.59-0.67, barely above the out-of-scope q6 (0.53-0.54). A cutoff near 0.65 would reject real questions. A better relevance signal is needed (reranking, Corrective RAG).
- **The eval set is small.** With 5 labeled queries one query moves MRR by 0.1-0.2. Add more vague queries before the final before/after comparison.
- **Label correction.** Chunk 19 was first marked borderline for q3; reading the full text showed it directly addresses fine-print disclosures, so it was included.
- **Frameworks.** Employers want evidence of using standard tools, but also an explanation of why each technique was chosen and a measured improvement. Plan: hand-built through 7E, with LlamaIndex / LangGraph used in contained places (decision pending).

## 8. Notebook cell order

1. Setup (load PDF, chunk, embed, FAISS, `search_policy`)
2. Eval setup (`eval_queries`, `K`, `retrieve()`, `find_chunks()`); no print loop
3. Labels, `evaluate()` and the baseline run
4. Helpers (`call_with_retry`, `generate_query_variants` with `REWRITE_MODEL`); no test loop
5. Prep: generate variants once, paced, saved to `query_variants.json`
6. `multi_query_retrieve()` + RRF eval + q4 top-5 printout

## 9. Next actions

1. Diagnostic cell (no API calls): print the baseline and multi-query top 5 side by side for every query, with the labeled chunks marked, to see why q3 and q5 dropped and whether q4 can be fixed.
2. Possibly weight the original query more in RRF, then re-evaluate.
3. HyDE (7A.4): about 6 Gemini calls, cached to disk.
4. Compare baseline vs multi-query vs HyDE (7A.5).
5. Add more vague queries to the eval set, and add answer generation to v2.
6. Then 7B reranking, 7C pgvector, 7D FastAPI, 7E README, 7F Corrective RAG.

## 10. Open decisions

- Whether to enable billing on the Google project. HyDE, answer generation, reranking and Corrective RAG all make Gemini calls, and the free daily cap will slow every one of them.
- Whether to allow LangGraph for 7F and a LlamaIndex comparison notebook.
- Which README becomes the landing page at 7E.

## 11. Changelog

**v2.1**

- Added the 7A.3 multi-query results (MRR 0.500 vs baseline 0.600) and the reading of them, with the q3/q5 explanation marked as a hypothesis.
- Corrected an earlier statement. The first version said the q1-q4 variants were saved and only q5/q6 were blocked. In fact none were saved, because the cell crashed before the file was written, and all six were regenerated on `gemini-3.5-flash-lite`.
- Errors table: added the 404 on the retired model, the `NameError`, and the lost-variants issue, and made the thinking-token fix specific to each model.
- Replaced the "when the quota resets" next steps with the current ones, since those steps are done.

**v2.0**

- Initial build log: plan and decisions, why FAISS, baseline evaluation and errors 1-4.