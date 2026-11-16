# Policy Search Assistant v2 (Advanced RAG): Step 7 Build Log

CFPB UDAAP RAG bot. This file covers the v2 work (Step 7) up to the multi-query evaluation (7A.3) and its diagnostic: the plan, decisions, evaluation results, errors, fixes and open questions. The original v1 (Steps 1-6) is preserved under the git tag `v1-faiss`.

## 1. Where things stand

| Item | Status |
|---|---|
| v1 (Steps 1-6) | Frozen with git tag `v1-faiss`; original notebook and README untouched |
| v2 scaffold | `compliance_bot_v2.ipynb` and `README_v2.md` created as new files |
| 7A.1 Baseline eval | Done: Hit@5 4/5, MRR 0.600 (labels in `eval_set.json`) |
| 7A.2 Variant generation | Done: 3 clean variants per query, all 18 generated with `gemini-3.5-flash-lite` and saved in `query_variants.json` |
| 7A.3 Multi-query + RRF | Done: Hit@5 4/5, MRR 0.500. Did not beat the baseline on this small eval set (see section 5) |
| 7A.3b Diagnostic | Done: q3/q5 drops traced to near-tied RRF scores; weighting the original query dropped; q4 label checked (weak, inferred, kept as is). See sections 5 and 7 |
| 7A.4 HyDE | Done: 6 passages generated and cached in `hyde_cache.json`. HyDE alone MRR 0.567; original + HyDE MRR 0.800 but with narrow margins. q4 still a miss. See section 5b |
| Next | Expand the eval set (more vague queries, rewrite the weak q4), re-run the four-way comparison, add answer generation to v2, then 7B reranking |

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

- Multi-query did not beat the baseline on this 5-query set. The sample is tiny (q3 and q5 each lost 0.5 of reciprocal rank (0.1 of MRR) and q1 gained 0.5, a net change of -0.1), so this is "has not helped yet", not proof that it hurts.
- q1 improved: one variant used "substantial injury" and "reasonable consumer avoidability", the exact elements of the unfairness test in chunks 3 and 4.
- q4 stayed a miss. The variants used "high-pressure", "coercive" and "deceptive" wording, none said "abusive" or "unreasonable advantage", and the top 5 filled with deception chunks (20, 2, 22, 0, 47); chunk 33 never appeared. Rewriting can steer a query away from the document's vocabulary as easily as toward it.
- **Why q3 and q5 dropped (diagnosed with a no-API side-by-side cell, using cached variants).** My first guess was that variants outranked the original's best chunk. That was only partly right. The cause is how RRF scores:
  - q3: chunk 53 was top-1 for the original and ranked 2 and 1 in two variants, but was missing from variant 3's top 10, which cost it about a third of its score. Chunk 21 appeared in all four lists at moderate ranks and won (0.0626).
  - q5: a near-tie. Chunk 21 scored 0.0640 and chunk 22 scored 0.0629, so a 0.001 gap flipped the order.
  - The top-5 RRF scores sit within about 0.002 of each other, so RRF mostly counts how many lists a chunk appears in, and small swaps are expected.
  - Chunk 21 tops the fused list for both q3 and q5. Its text has not been inspected yet.
- **Weighting the original query more in RRF would not help.** A rough estimate from the printed scores puts the weight needed for chunk 53 to beat chunk 21 at about 8-12x per variant, which is close to turning multi-query off. q4 cannot be fixed this way either, because chunk 33 is not in the original's top 10.
- **Possible benefit: candidate recall.** Multi-query found chunks the baseline missed (q4's chunk 33 at fused rank 6, q1's chunk 4 at fused rank 12). Hand-calculated from the ranked lists:

| Metric (5 queries) | Baseline | Multi-query |
|---|---|---|
| Recall@5 | 0.600 | 0.633 |
| Recall@10 | 0.700 | 0.900 |
| Recall@5, excluding q4 | 0.750 | 0.792 |
| Recall@10, excluding q4 | 0.875 | 0.875 |

- The Recall@10 gain comes entirely from q4, whose label is inferred. Excluding q4, top-10 recall is identical. There is no evidence yet that multi-query improves the top 5. It may work as a candidate generator for the 7B reranker, which is a hypothesis to test, not a finding.
- The out-of-scope query q6 scored 0.065 under RRF (maximum possible 0.066): its rewritten variants all agreed on the same chunk. Agreement across variants is not relevance, so RRF scores cannot flag off-topic queries.

## 5b. HyDE (7A.4) and the four-way comparison

**Design**

- For each query, `gemini-3.5-flash-lite` (temperature 0.3, thinking level minimal) writes a short passage (80-120 words) in the formal style of the CFPB manual that would answer the question. The passage is embedded and searched in FAISS (top 10) in place of the question.
- Passages are cached in `hyde_cache.json`: 6 `generate_content` calls in total, none repeated on re-runs.
- The output was clean (plain prose, 112-126 words, no headings or list markers), so no cleaning code was needed.
- Two HyDE methods were scored: HyDE alone, and original + HyDE fused with the same RRF as multi-query (k = 60, two lists).
- Quota: the AI Studio usage page shows free-tier limits of 15 requests per minute and 500 per day for this model. The 20-per-day cap in section 6 (#4) was specific to `gemini-2.5-flash`. The usage page can lag, so every LLM output is still cached.

**Results**

| Method | Hit@5 | MRR | MRR without q4 | Recall@5 | Recall@10 |
|---|---|---|---|---|---|
| baseline | 4/5 | 0.600 | 0.750 | 0.600 | 0.700 |
| multi-query | 4/5 | 0.500 | 0.625 | 0.633 | 0.900 |
| HyDE alone | 4/5 | 0.567 | 0.708 | 0.733 | 0.733 |
| original + HyDE (RRF) | 4/5 | 0.800 | 1.000 | 0.633 | 0.800 |

The baseline and multi-query rows reproduced the earlier numbers, which confirms the comparison code matches.

| Query | Baseline rr | Multi-query rr | HyDE rr | Original + HyDE rr |
|---|---|---|---|---|
| q1 | 0.50 | 1.00 | 0.33 | 1.00 |
| q2 | 0.50 | 0.50 | 1.00 | 1.00 |
| q3 | 1.00 | 0.50 | 0.50 | 1.00 |
| q4 | 0.00 | 0.00 | 0.00 | 0.00 |
| q5 | 1.00 | 0.50 | 1.00 | 1.00 |

**Reading of the result**

- **No method fixes q4.** The HyDE passage used "unfair, deceptive, or abusive" and "material costs, risks, or conditions", wording close to chunk 33, but chunk 33 still ranked outside the top 10. Retrieval preferred deception and overview chunks (41, 2, 34).
- **HyDE alone does not beat the baseline on MRR (0.567 vs 0.600).** It improved q2 (chunk 33 from rank 2 to rank 1) and put both q1 chunks in the top 5. It hurt q3: chunk 27 fell out of the top 10 and chunk 53 dropped from rank 1 to rank 2. It has the highest Recall@5 (0.733), so it gets more relevant chunks into the top 5 even when the first hit ranks lower.
- **Original + HyDE has the best MRR, but the margins are narrow.** By hand arithmetic from the printed ranks (not code output), q2 comes down to chunk 33 at 0.03252 against chunk 0 at 0.03227, a gap of about 0.0003. q1 is also narrow. q3 and q5 look solid. This is the same kind of near-tie that cost multi-query its q3 and q5 ranks. The data supports carrying this method forward and nothing stronger.
- **HyDE cosine scores run higher for every query, so they cannot be compared with baseline scores.** They compare a passage with a chunk, not a question with a chunk. For the out-of-scope q6, the top score rose from 0.541 to 0.705. The gap between q6 and the weakest in-scope query is about the same (about 0.061 baseline, 0.057 HyDE, by hand arithmetic), so a score threshold still would not separate them. The q6 passage also confidently describes what the manual says about credit scores, which it does not cover.
- **Possible advantage from model memory.** The CFPB manual is public, so the model may partly remember its wording. HyDE may look better here than it would on a private internal policy.
- **The eval set is now the main limit.** With 5 labeled queries, the differences between methods are about one rank on one query. More vague queries are needed before any method is declared the winner

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
  - Label check: I read the full text of chunk 33, the baseline's top 3 (22, 52, 28) and multi-query's top 2 (20, 2). None mentions pressure or urgency. Chunk 33 is the closest, but a reader has to reason from "unreasonable advantage" to "pressure"; the passage does not say it. Chunks 3 and 4 (the unfairness test) were not re-read in this check.
  - Decision: keep the label as [33], flagged as weak and inferred, and report metrics with and without q4. Rewrite q4 only when the new vague queries are added, so the eval set does not change in the middle of a comparison.
- **A simple score threshold would not work.** Vague but legitimate queries (q3, q4) score 0.59-0.67, barely above the out-of-scope q6 (0.53-0.54). A cutoff near 0.65 would reject real questions. HyDE does not help: its scores run higher for every query, and the q6 gap to the weakest in-scope query is about the same (section 5b). A better relevance signal is needed (reranking, Corrective RAG).
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
7. Diagnostic: baseline vs multi-query top 5 side by side, with labeled chunks marked; uses `search_cache.json`, no generate_content calls
8. HyDE generation: one passage per query from `REWRITE_MODEL`, cached in `hyde_cache.json` (6 generate_content calls the first time, 0 after)
9. HyDE retrieval + four-way comparison (baseline, multi-query, HyDE, original + HyDE): side-by-side top 5, metrics table, q6 score check; uses `search_cache.json`, no generate_content calls

## 9. Next actions

1. Expand the eval set: add about 8-10 queries, mostly vague, labeled by reading the full chunks. Rewrite q4 at the same time, since its label is weak (section 7).
2. Re-run the four-way comparison on the larger set. The original + HyDE lead rests on narrow RRF margins (section 5b), so it needs to hold up before it is chosen.
3. Add answer generation (`system_instruction_rag`, `generate_rag_response`) to v2. It must be present before 7D.
4. Then 7B reranking (test multi-query and original + HyDE as candidate generators for it), 7C pgvector, 7D FastAPI, 7E README, 7F Corrective RAG.

**Done since the last version:** HyDE generation and the four-way comparison (section 5b).

## 10. Open decisions

- Whether to enable billing on the Google project. The AI Studio usage page shows free-tier limits of 15 requests per minute and 500 per day for `gemini-3.5-flash-lite`, which is enough for HyDE and probably for answer generation. Revisit if reranking or Corrective RAG make many calls per query, or if a different model is needed.
- Whether to allow LangGraph for 7F and a LlamaIndex comparison notebook.
- Which README becomes the landing page at 7E.

## 11. Changelog

**v2.3**

- Added section 5b: HyDE design, the four-way comparison (baseline, multi-query, HyDE, original + HyDE) and a reading of it. Original + HyDE has the best MRR (0.800), but by hand arithmetic its lead rests on narrow RRF margins (about 0.0003 in q2). No method fixed q4.
- Noted that HyDE cosine scores run higher than baseline scores and cannot be compared with them; a threshold still would not separate q6 from the weakest in-scope query.
- Noted the possible model-memory advantage on a public manual.
- Replaced the billing open decision with the verified free-tier limits for `gemini-3.5-flash-lite`.
- Updated the intro and sections 1, 7, 8 and 9.

**v2.2**

- Added the side-by-side diagnostic of baseline vs multi-query (no generate_content calls; search results cached in `search_cache.json`). It reproduced both earlier numbers (baseline MRR 0.600, multi-query 0.500), which confirms the local RRF matches `multi_query_retrieve`.
- Replaced the q3/q5 hypothesis with the diagnosed cause: near-tied RRF scores, not variants outranking the original's best chunk. Noted that weighting the original query would not help.
- Added the candidate-recall table (Recall@5 and @10, with and without q4) and stated that there is no evidence yet that multi-query improves the top 5.
- Added the q4 label check to section 7: kept [33] as a weak, inferred label and decided to report metrics with and without q4.
- Updated sections 1 and 9 to reflect the completed diagnostic and the dropped weighting idea.

**v2.1**

- Added the 7A.3 multi-query results (MRR 0.500 vs baseline 0.600) and the reading of them, with the q3/q5 explanation marked as a hypothesis.
- Corrected an earlier statement. The first version said the q1-q4 variants were saved and only q5/q6 were blocked. In fact none were saved, because the cell crashed before the file was written, and all six were regenerated on `gemini-3.5-flash-lite`.
- Errors table: added the 404 on the retired model, the `NameError`, and the lost-variants issue, and made the thinking-token fix specific to each model.
- Replaced the "when the quota resets" next steps with the current ones, since those steps are done.

**v2.0**

- Initial build log: plan and decisions, why FAISS, baseline evaluation and errors 1-4.