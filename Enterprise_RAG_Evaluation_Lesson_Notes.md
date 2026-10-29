# Enterprise RAG Evaluation — Complete Lesson Notes

**Project:** S-Presso Owner's Manual RAG  
**Scope:** Retrieval evaluation, LLM reranking, RAGAS, metrics, troubleshooting, and interview revision  
**Current status:** Retrieval metrics calculated on three questions; RAGAS generation scores not yet verified.

## 1. Why evaluate RAG?

Retrieval-Augmented Generation (RAG) has two main stages: **retrieval** finds source evidence, and **generation** produces an answer using that evidence. A fluent answer can still be incorrect, irrelevant, or unsupported. Evaluate both stages separately to diagnose the cause.

- **Retrieval coverage:** Did the system find the needed evidence?
- **Retrieval ranking:** Was the most useful evidence ranked early?
- **Faithfulness:** Is the answer supported by retrieved context?
- **Answer relevancy:** Does the answer address the question?
- **Reference correctness:** Does the answer agree with a manually verified answer?
- **Operational quality:** What are the latency, cost, failure rate, and security implications?

**Interview answer:** “I use a labeled question set, calculate Recall@K and MRR for retrieval, RAGAS faithfulness and answer relevancy for generation, and compare quality against latency and cost.”

## 2. End-to-end evaluation architecture

```text
Labeled dataset: question + reference + relevant_chunk_ids
                           |
             +-------------+-------------+
             |                           |
       Vector retrieval           Vector + LLM rerank
             |                           |
             +-------------+-------------+
                           |
           Ordered chunk IDs and retrieved contexts
                           |
                  Recall@K, RR, MRR
                           |
                    Answer generation
                           |
                  Generated response
                           |
        RAGAS faithfulness and answer relevancy
                           |
                    Comparison report
```

## 3. Chunking, embeddings, and Qdrant

A **chunk** is a searchable section of source text. Chunking makes retrieval more focused and reduces the context sent to the LLM. **Embeddings** represent text as numeric vectors. **Vector search** retrieves chunks whose embeddings are semantically similar to the question embedding.

**Qdrant** stores vector points and associated **payloads**. A point has a Qdrant point ID, vector(s), and optional payload metadata. Your payload can include `chunk_id`, `page`, and `text`. A payload `chunk_id` is not necessarily the internal Qdrant point ID.

Observed identifiers include `page_8_chunk_0`, `page_8_chunk_1`, `page_182_chunk_0`, and `page_182_chunk_1`. Page metadata helps users audit claims against the source manual.

**Why irrelevant chunks appear:** Embedding similarity is approximate. A broader search for engine-oil precautions returned `page_184_chunk_1`, a coolant passage, at rank 10 (vector score 0.5005). Both topics are automotive maintenance; similarity alone does not guarantee direct relevance.

## 4. Vector search vs. LLM reranking

**Vector retrieval:** Embed question → search Qdrant → obtain top-N candidate chunks. It is efficient, but the ranking can favor broadly similar rather than directly useful passages.

**LLM reranking:** Send the question and candidate passages to an LLM-based relevance assessment → reorder passages → retain top-K. This may improve the order but adds inference cost and latency. A **cross-encoder reranker** is a different implementation: it scores question–passage pairs with a dedicated model. Confirm whether your `llm_rerank` code actually calls an LLM or a cross-encoder.

**Critical limitation:** A reranker can reorder only the candidates it receives; it cannot recover a relevant chunk that was excluded from the candidate pool.

## 5. Ground-truth evaluation dataset

A labeled dataset must include:

- `question`: user query.
- `reference`: manually verified expected answer.
- `relevant_chunk_ids`: identifiers of all known relevant chunks.

Example from your observed retrieved passages:

```json
[
  {
    "question": "What is the standard warranty period for S-Presso?",
    "reference": "36 months or 100,000 km, whichever comes first, from the invoice date to the first owner.",
    "relevant_chunk_ids": ["page_8_chunk_0"]
  },
  {
    "question": "What happens if the vehicle exceeds the warranty mileage limit?",
    "reference": "The standard warranty ends when the vehicle reaches 100,000 km, even if 36 months have not passed; certain components have separate warranty terms.",
    "relevant_chunk_ids": ["page_8_chunk_0"]
  },
  {
    "question": "What are the recommended engine oil checking precautions?",
    "reference": "Check on a level surface before starting the engine or at least five minutes after stopping; clean and reinsert the dipstick, check the marks, and avoid overfilling.",
    "relevant_chunk_ids": ["page_182_chunk_0", "page_182_chunk_1"]
  }
]
```

**Caution:** These IDs are based on earlier retrieval results. Verify them against the original manual and Qdrant payload before declaring them definitive ground truth. Do not label a chunk as relevant merely because your current retriever returned it: that creates evaluation bias.

When `relevant_chunk_ids` was `[]`, your evaluator returned `None` for Recall@5 and RR. **Undefined is not zero**: there were no relevance labels to evaluate against.

## 6. Recall@K — coverage

**Definition:** Fraction of *all labeled relevant chunks* found in the first K retrieved results.

```text
Recall@K = number of relevant chunks found in top K
           ----------------------------------------
                 total labeled relevant chunks
```

Example: relevant IDs are `A, B`; top five are `A, C, D, E, F` → Recall@5 = 1/2 = **0.5**. If both A and B appear in top five, Recall@5 = **1.0**.

- **1.0:** All labeled relevant chunks were found in top K.
- **0.0:** None were found.
- **None:** Relevance labels missing or metric undefined.

**Limitation:** Recall@5 ignores ordering within the top five. A relevant result at rank 1 and at rank 5 can both give Recall@5 = 1.0.

## 7. Reciprocal Rank and Mean Reciprocal Rank

For **one question**, Reciprocal Rank (RR) is:

```text
RR = 1 / rank of the first relevant result
```

| First relevant rank | RR |
|---:|---:|
| 1 | 1.000 |
| 2 | 0.500 |
| 3 | 0.333 |
| 4 | 0.250 |
| No relevant result in evaluated list | 0.000 |

Across **N questions**:

```text
MRR = (RR_1 + RR_2 + ... + RR_N) / N
```

Your script prints `MRR` per question, but strictly those individual values are **RR**; MRR is their mean across questions.

### Your actual results

| Question | Vector RR | LLM-rerank RR | Vector Recall@5 | Rerank Recall@5 |
|---|---:|---:|---:|---:|
| Standard warranty | 1.0 | 1.0 | 1.0 | 1.0 |
| Mileage limit | 0.5 | 1.0 | 1.0 | 1.0 |
| Engine oil precautions | 1.0 | 1.0 | 1.0 | 1.0 |
| **Average** | **0.833** | **1.000** | **1.000** | **1.000** |

```text
Vector MRR = (1 + 0.5 + 1) / 3 = 0.8333
Rerank MRR = (1 + 1 + 1) / 3 = 1.0000
Relative MRR improvement ≈ (1 - 0.8333) / 0.8333 = 20%
```

**Interpretation:** On these three questions, reranking moved the first relevant mileage-limit chunk from rank 2 to rank 1. Both methods already found the labeled relevant chunks within top five. The dataset is too small to establish a robust production-wide advantage.

**MRR limitation:** Only the first relevant result counts; MRR does not measure whether the system found every needed passage.

## 8. Additional retrieval metrics

**Precision@K:** Number of relevant results in top K divided by K. Measures how much of the returned context is relevant. Do not confuse it with Recall@K, whose denominator is the total relevant set.

**Hit Rate@K:** Whether at least one relevant chunk appears in top K (1 or 0 per question), averaged across questions.

**nDCG@K:** Normalized Discounted Cumulative Gain rewards placing highly relevant chunks early and supports graded relevance, e.g., 0 = irrelevant, 1 = partially relevant, 2 = highly relevant.

**Top-K trade-off:** Larger K can increase recall but also increase tokens, latency, irrelevant context, and cost.

## 9. What is RAGAS?

**RAGAS** is an evaluation framework for RAG and LLM applications. Your current RAGAS 0.4.x script uses evaluator models and embeddings:

```python
from ragas.llms import llm_factory
from ragas.embeddings import embedding_factory
from ragas.metrics.collections import Faithfulness, AnswerRelevancy
```

**Version note:** API paths and signatures can change across RAGAS versions. Validate against the installed version before copying examples into a different environment.

### 9.1 Faithfulness

**Question:** Are the factual claims in the generated answer supported by the retrieved passages?

Conceptually, the evaluator identifies claims and checks which are supported by the evidence. An intuitive approximation is:

```text
Faithfulness ≈ supported factual claims / assessed factual claims
```

Example: The answer says “36 months or 100,000 km” and the retrieved warranty clause says the same → that claim is grounded.

**Important:** Faithfulness is not identical to real-world truth. A faithfully repeated incorrect document claim may still be factually wrong.

### 9.2 Answer relevancy

**Question:** Does the response directly address the user question?

Your `AnswerRelevancy` setup uses an evaluator LLM and embeddings. It does not require a reference answer in the shown code. An answer about coolant when the user asked about engine oil is poorly aligned even if the coolant facts are correct.

**Important:** Relevancy does not guarantee correctness or faithfulness.

### 9.3 Context precision

**Question:** Are the retrieved contexts relevant, and is useful evidence ranked early? RAGAS variants can assess this with a reference answer or reference contexts. This differs from simple exact-ID Precision@K.

### 9.4 Context recall

**Question:** Do retrieved contexts contain the facts needed to support the verified reference answer? This differs from exact-ID Recall@K, which uses labeled chunk identifiers.

### 9.5 Answer correctness

Compares generated answers with a verified reference. Depending on the chosen metric, it can use factual comparison, semantic similarity, or both.

### Metrics compared

| Metric | Main concern | Needs relevant chunk IDs? | Needs reference answer? |
|---|---|---|---|
| Exact-ID Recall@K | Evidence coverage | Yes | No |
| RR / MRR | First relevant rank | Yes | No |
| RAGAS Faithfulness | Answer grounding | No | No |
| RAGAS Answer Relevancy | Question alignment | No | No |
| RAGAS Context Precision | Context relevance/ranking | No | Depends on variant |
| RAGAS Context Recall | Coverage of reference facts | No | Usually yes |

## 10. Your evaluation files and workflow

```text
evaluation/
├── evaluate_live_rag.py
├── evaluate_ragas.py
└── reports/
    ├── live_retrieval_results.csv
    └── ragas_scores.csv        # created after successful RAGAS run
```

**Live retrieval CSV fields observed:** `question`, `method`, `answer`, `reference`, `recall_at_5`, `mrr`, `retrieved_chunk_ids`, `retrieved_pages`, `retrieved_contexts`.

The RAGAS script reads this CSV and should add `faithfulness` and `answer_relevancy`. **Actual RAGAS numerical results have not yet been shared**, so do not claim these metrics are complete.

### Code: Recall@K

```python
def recall_at_k(retrieved_ids, relevant_ids, k=5):
    relevant = set(relevant_ids)
    if not relevant:
        return None
    return len(set(retrieved_ids[:k]) & relevant) / len(relevant)
```

### Code: RR and MRR

```python
def reciprocal_rank(retrieved_ids, relevant_ids):
    relevant = set(relevant_ids)
    if not relevant:
        return None
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0

scores = [1.0, 0.5, 1.0]
mrr = sum(scores) / len(scores)  # 0.833333...
```

### Code: RAGAS asynchronous calls

```python
faith_result = await faithfulness.ascore(
    user_input=question,
    response=answer,
    retrieved_contexts=contexts,
)
faith_score = faith_result.value

relevancy_result = await answer_relevancy.ascore(
    user_input=question,
    response=answer,
)
relevancy_score = relevancy_result.value
```

**Common bug:** After `faith_score = faith_result.value`, do **not** use `faith_score.value`. The score is already a number (or `None` if evaluation failed).

**CSV parsing:** The `retrieved_contexts` list is stored as a JSON string in CSV. Parse it with `json.loads(row['retrieved_contexts'])` before passing to RAGAS.

**Failure handling:** If an evaluator fails, preserve `None` and log the exception. Do not silently convert API errors into zero-quality scores.

## 11. Troubleshooting from this project

### Qdrant connection refused

```text
[WinError 10061] No connection could be made because the target machine actively refused it
```

The configured Qdrant endpoint is unreachable or refusing connections. Verify Docker, port, and original data volume:

```cmd
docker ps -a
curl http://localhost:6333/healthz
curl http://localhost:6333/collections
```

Avoid creating a new empty Qdrant container before locating your existing indexed collection.

### Recall@5 and MRR returned None

`relevant_chunk_ids` was empty. Add manually verified ground-truth IDs and ensure their format matches the retrieved IDs.

### `.py` file opened in VS Code instead of executing

Typing a file path directly may invoke the Windows file association. Use:

```cmd
cd /d D:\warranty_RAG
python -m evaluation.evaluate_live_rag
python -m evaluation.evaluate_ragas
```

### RAGAS/LangChain import errors

Inspect the exact traceback and versions. Keep a dependency snapshot before targeted changes. Avoid broad package downgrades in an otherwise working project.

### LLM evaluator fails

Check `OPENAI_API_KEY`, evaluator model access, API quota, networking, rate limits, and the exception. Evaluator API calls may incur charges.

### Scores vary between runs

LLM judgments can vary. Record dataset version, metric version, model, prompt, temperature where applicable, and evaluation date.

## 12. How to design a reliable benchmark

Your three questions are a **smoke test**, not a comprehensive evaluation. Expand to at least **30–50 manually labeled questions** covering:

1. Standard warranty terms and exceptions.
2. Maintenance and service procedures.
3. Fluids, engine oil, and coolant.
4. Safety warnings and prohibited actions.
5. Numerical specifications and tables.
6. Questions requiring multiple chunks.
7. Paraphrases and ambiguous phrasing.
8. Questions that the manual cannot answer (abstention).

**Fair comparison:** Use the same questions, generation settings, top-K, and reference labels for both methods. Evaluate ranking, answer grounding, answer correctness, p95 latency, tokens, and cost. Inspect failures manually.

**Prevent label leakage:** Define relevant evidence by reading the manual, not by copying whichever chunks your preferred retriever found.

## 13. Production considerations

- **Latency:** Measure retrieval, reranking, generation, and end-to-end p50/p95/p99 latency.
- **Cost:** Track embedding, reranker, and generation tokens/inference costs per query.
- **Reliability:** Test Qdrant outages, empty results, timeouts, rate limits, and malformed payloads.
- **Security:** Test prompt injection, document-level access controls, PII leakage, and citation integrity.
- **Observability:** Log request IDs, model versions, stage timings, chunk IDs, failures, and token counts; avoid unnecessarily logging sensitive text.
- **Regression testing:** Re-run a stable benchmark whenever you change chunking, embeddings, reranking, prompts, models, or the index.

## 14. Interview questions — concise answers

**Q1. Why evaluate retrieval and generation separately?**  
A poor answer can result from missing evidence or from the LLM misusing correct evidence. Separate metrics isolate the issue.

**Q2. Recall@5 vs. MRR?**  
Recall@5 measures coverage of all labeled relevant chunks within five results; MRR measures how early the first relevant chunk appears across questions.

**Q3. How can MRR improve while Recall@5 stays the same?**  
A relevant chunk moves from rank 2 to rank 1 but was already inside the top five.

**Q4. What is faithfulness?**  
Whether answer claims are supported by retrieved context.

**Q5. Faithfulness vs. answer relevancy?**  
Faithfulness is evidence grounding; relevancy is alignment with the question.

**Q6. Why use reranking?**  
Fast vector search retrieves candidates; reranking may better prioritize passages that directly answer the question.

**Q7. Does reranking always increase Recall@5?**  
No. It may only change order, and cannot recover chunks absent from its candidate set.

**Q8. What is a Qdrant payload?**  
Metadata stored alongside vector points, such as page, chunk ID, and text.

**Q9. What does `MRR: None` mean in your project?**  
Ground-truth relevant chunk IDs were missing; it does not mean retrieval scored zero.

**Q10. Why is a three-question evaluation insufficient?**  
It misses rare and difficult query types, making performance estimates unstable.

**Q11. What if the manual lacks the answer?**  
Test abstention and ensure the assistant does not invent unsupported facts.

**Q12. How do you justify reranker cost?**  
Compare quality improvement against added latency and token/inference cost on a representative benchmark.

**Q13. What would you monitor in production?**  
Recall@K, MRR/nDCG, faithfulness, answer quality, p95 latency, error rate, token cost, and drift over time.

## 15. Quick revision table

| Term | Remember it as |
|---|---|
| Chunk | Searchable passage |
| Chunk ID | Evidence identifier |
| Embedding | Numeric semantic representation |
| Vector retrieval | Fast candidate search |
| Reranking | Reorder candidates by relevance |
| Ground truth | Independently verified answer and evidence |
| Recall@K | Coverage of relevant evidence |
| Precision@K | Purity of returned top-K |
| RR | 1 / first relevant rank |
| MRR | Average RR across questions |
| Faithfulness | Supported by context? |
| Answer relevancy | Answers the question? |
| Context precision | Is retrieved evidence useful and well ranked? |
| Context recall | Does retrieved evidence cover needed facts? |
| Hallucination | Unsupported or fabricated claim |
| Regression test | Detect quality degradation after a change |

## 16. Lesson completion checklist

- [x] Qdrant retrieval working.
- [x] Vector and LLM-rerank methods producing answers.
- [x] Retrieved IDs, pages, and contexts saved to CSV.
- [x] Three-question retrieval smoke test with relevance labels.
- [x] Recall@5 and RR calculated.
- [x] Mean RR comparison: 0.833 vs. 1.000.
- [ ] Manually verify all relevant chunk labels.
- [ ] Run RAGAS faithfulness and answer relevancy successfully.
- [ ] Review actual RAGAS scores and failures.
- [ ] Add context precision/recall if useful.
- [ ] Expand to 30–50+ independently verified questions.
- [ ] Compare latency, cost, and failure modes.
- [ ] Write final benchmark findings and limitations.

### Commands

```cmd
cd /d D:\warranty_RAG
python -m evaluation.evaluate_live_rag
python -m evaluation.evaluate_ragas
```

---

> **Final lesson takeaway:** A production RAG system is not judged by how convincing its answers sound. Verify that it retrieves the correct evidence, ranks that evidence well, produces grounded answers, and justifies its latency and cost.
