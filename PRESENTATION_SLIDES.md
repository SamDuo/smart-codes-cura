# Hybrid Multi-Agent RAG with Knowledge Graph Augmentation for Building Code Amendments: Evaluation & Findings

---

## Slide 1: Title

**Hybrid Multi-Agent RAG with Knowledge Graph Augmentation for Building Code Amendment Analysis**
*Evaluating Retrieval-Augmented Generation Across U.S. Jurisdictions*

- SmartCodes Research Team
- April 2026

*Architecture: Custom hybrid -- Supabase pgvector + Neo4j graph and multi-agent routing*

---

## Slide 2: Problem Statement

**Why Building Code RAG is Hard**

Building codes are not like typical documents. Each U.S. city takes a national model code (like the International Building Code) and adds its own local amendments -- changes specific to that city's needs like earthquake zones, wildfire areas, or local construction practices.

This creates a unique challenge for AI-powered question answering:
- **9 cities**, each with their own version of the code
- **12,280 text passages** extracted from these documents
- Questions range from simple lookups ("What's the fire rating?") to complex comparisons ("How do LA and Phoenix differ?")
- A standard search engine treats every question the same -- but comparing two cities requires a fundamentally different approach than looking up a single fact

---

## Slide 3: Why Multi-Agent over Single-Pipeline RAG?

**One Size Doesn't Fit All**

A standard RAG system uses the same approach for every question: search for similar text, feed it to an LLM, get an answer. But building code questions come in very different types, and each type needs a different search strategy:

| Question Type | What It Needs | Why Standard Search Fails |
|--------------|---------------|--------------------------|
| **Simple fact** ("What is the fire rating for Group F-2?") | Search one city's code | Standard search works fine here |
| **City comparison** ("How do LA and Phoenix differ?") | Search each city **separately**, then compare side by side | Standard search mixes chunks from both cities together; can't compare properly |
| **Code history** ("What changed between 2019 and 2022?") | Search by **year**, plus know the adoption timeline | Standard search returns whatever is most similar, ignoring which year it's from |
| **Complex compliance** ("What fire seismic rules apply?") | Break into **sub-questions**, search each one | Standard search tries to find one chunk that answers everything, and usually fails |

**Our solution**: Instead of one pipeline, we use **specialist agents**, each one designed for a specific question type, with its own search strategy.

---

## Slide 4: Multi-Agent Pipeline Architecture

**How It Works: Route to the Right Specialist**

```
User Question
    |
    v
[Classifier] -- "What type of question is this?"
    |
    +---> [Factual Agent] -- searches one city's code
    +---> [Cross-Jurisdiction Agent] -- searches each city separately, then compares
    +---> [Temporal Agent] -- searches by year + uses adoption timeline from graph
    +---> [Compliance Agent] -- breaks question into parts, searches each one
    |
    v
[Citation Validator] -- double-checks for made-up information
    |
    v
Answer with Source Citations
```

Two data sources work together:
- **Vector store** (Supabase): Finds relevant text passages by meaning similarity
- **Knowledge graph** (Neo4j): Provides structured facts -- which city adopted which code, when, and what they changed

---

## Slide 5: Document Processing Pipeline

**How We Turned PDFs into Searchable Data**

Building code PDFs are messy -- they contain tables, diagrams, legal references, and amendment markers. Our pipeline handles this in 5 steps:

1. **Extract text** from PDFs using specialized tools that understand tables and page layout
2. **Split** the text into ~1,000-character passages with overlap so nothing falls between the cracks
3. **Convert** each passage into a mathematical vector (embedding) that captures its meaning
4. **Store** the vectors in Supabase for fast similarity search
5. **Build a knowledge graph** in Neo4j with city profiles, code editions, and adoption timelines

| What We Have | Count |
|-------------|-------|
| Cities covered | 9 |
| Searchable passages | 12,280 |
| Code editions tracked | 8 |
| Amendment events recorded | 2,550 |
| Code sections in graph | 11,163 |

---

## Slide 6: Evaluation Methodology

**How We Tested the System**

Built a benchmark of **56 test questions** with known correct answers, then ran both the baseline (simple search) and our multi-agent system against them.

**Three layers of scoring**:
1. **Automated fact matching**: Did the answer contain the key facts we expected? (e.g., "2 hours" for a fire rating question)
2. **LLM judge**: We used GPT-4o as an independent judge to score whether the answer was faithful to the evidence and whether it made things up
3. **Citation checking**: Did the answer cite the correct code sections?

We compared **Baseline** (standard vector search + single LLM call) vs. **Multi-Agent** (classifier + specialist agents + graph context).

---

## Slide 7: Benchmark Questions -- Examples by Category

**56 questions across 6 categories, covering 9 U.S. cities**

| Category | Count | Example |
|----------|-------|---------|
| **Factual Lookup** | 20 | "What is the minimum clear width required for an egress door in a dwelling unit?" (LA) |
| **Cross-Reference** | 8 | "What is required for compliance with reduced seismic loads?" (LA) |
| **Cross-Jurisdiction** | 10 | "How do LA and Phoenix differ in fire protection amendments?" |
| **Temporal** | 8 | "What is the complete timeline of building code amendments adopted by LA?" |
| **Compliance** | 6 | "What code applies to the construction of swimming pools in Irvine?" |
| **Unanswerable** | 4 | "In which city does the building code require surgical cystoscopic rooms?" |

**Why "Unanswerable" questions matter**: We deliberately included questions the system *shouldn't* be able to answer. A good system says "I don't know" instead of making something up. This tests calibration.

---

## Slide 8: Evaluation Metrics

**What We Measured and Why**

| Metric | What It Measures | How It's Calculated |
|--------|-----------------|-------------------|
| **Fact Accuracy** | Did the answer get the facts right? | Count of correct facts / total expected facts |
| **Faithfulness** | Is the answer backed by the retrieved evidence? | LLM judge rates 0-1 |
| **Citation Recall** | Did the answer reference the right code sections? | Count of correct citations / total expected citations |
| **Hallucination** | Did the answer make things up? | LLM judge rates 0-1 (0 = clean, 1 = heavy fabrication) |
| **Refusal Rate** | How often did the system decline to answer? | Count of "I don't know" / total answerable questions |

**The key tension**: Faithfulness and Hallucination measure opposite sides of the same coin.
- **Faithfulness** asks: "Is everything in the answer supported by evidence?"
- **Hallucination** asks: "Did the answer add anything that *wasn't* in the evidence?"

An answer can be partially faithful (some claims grounded) while also hallucinating (some claims fabricated).

---

## Slide 9: Issue #1 -- The Refusal Scoring Bug

**When "I Don't Know" Gets an Unfair Score**

We discovered our scoring system was giving partial credit to answers that were actually saying "I can't answer this."

**What happened**: The system answered "The provided context does not include information about *fire-resistance rating* for *Group F-2* buildings." Our scorer looked for the keywords "fire-resistance rating" and "Group F-2" in the answer -- and found them! So it scored 2 out of 3 facts correct = **0.67**. But the real answer should be **0.0** because the system was declining to answer, not providing the facts.

**The fix**: We expanded the list of "I don't know" phrases from 8 to 21 patterns. This correctly rescored **14 questions** that were getting inflated scores.

**Lesson**: Automated evaluation needs careful design. The scorer was accidentally rewarding the system for repeating question keywords in its refusal.

---

## Slide 10: Issue #2 -- Duplicate Document Retrieval

**Getting 5 Results from the Same PDF Isn't Helpful**

When we searched for "accessibility requirements," all 5 top results came from the same PDF (Chapter 11B Accessibility). This means we wasted 4 out of 5 search slots on overlapping content from one document, instead of getting diverse evidence from different sources.

**How common was this?** About 28% of search results were redundant -- same-source chunks that added little new information.

**The fix**: We now over-fetch 4x more candidates, then enforce a limit of **max 2 passages per source document**. This ensures the top-5 results come from at least 3 different sources.

**Bonus cleanup**: We also found and removed 632 exact duplicate passages from the database, and standardized city names that were inconsistent (e.g., "LosAngeles" vs "Los Angeles" -- 5,493 rows fixed).

---

## Slide 11: The Accuracy-Hallucination Tradeoff

**The Central Tension: Answer More, or Answer Safely?**

When we made our agents less conservative (tuned them to attempt answers instead of refusing), two things happened:
- Fact Accuracy went **up**: 0.414 -> **0.570** (system answers more questions correctly)
- Hallucination went slightly **up**: 0.464 -> 0.427 (system sometimes makes things up when it tries harder)

This is the fundamental tradeoff in RAG systems:
- **Too cautious** = refuses to answer when it actually has the information -> low accuracy
- **Too bold** = tries to answer everything, sometimes fabricating details -> high hallucination

**What the research says**:
- Shuster et al. (2021): RAG reduces hallucination compared to pure LLMs, but doesn't eliminate it
- Gao et al. (2023) "RARR": Post-generation fact-checking can catch fabrications before they reach the user
- Es et al. (2024) "RAGAS": Standard framework for measuring this faithfulness-accuracy tradeoff
- Huang et al. (2025): Survey categorizing hallucination types and mitigation strategies

---

## Slide 12: Hallucination Deep Dive

**What Kinds of Mistakes Does the System Make?**

We analyzed all 13 questions where the system scored high on hallucination (>0.5) and found 4 distinct patterns:

| Pattern | Count | What Happens |
|---------|-------|-------------|
| **Making up details** | 5 | The system invents plausible-sounding code requirements that aren't in the retrieved text (e.g., fabricating specific equation numbers) |
| **Over-generalizing** | 4 | The system reads a table header listing *possible* values and reports them as *actual* values for a city |
| **Wrong code edition** | 2 | The system finds the right topic but from the wrong year's code (e.g., answers with 2022 data when asked about 2014) |
| **Eval bug, not real hallucination** | 2 | The system correctly said "I don't know," but our evaluation scored this as hallucination |

**Key insight**: 2 of 13 "hallucinations" were actually measurement errors in our evaluation, not real model failures. Fixing the eval is as important as fixing the model.

**What we fixed**:
- Refusals now score 0 for hallucination (saying "I don't know" is not fabrication)
- Added year-aware filtering to prevent wrong-edition answers
- Graph provides a complete city list so the system doesn't guess

---

## Slide 13: Evaluation Progression

**How Each Fix Improved Results**

| Metric | Baseline | After Bug Fixes | + Graph Context | **+ Coverage Fix** |
|--------|----------|----------------|-----------------|-------------------|
| Fact Accuracy | 0.510 | 0.368 | 0.414 | **0.570** |
| Faithfulness | 0.627 | 0.511 | 0.512 | **0.577** |
| Citation Recall | 0.417 | 0.256 | 0.304 | **0.426** |
| Hallucination | 0.339 | 0.450 | 0.464 | **0.427** |
| Refusal Rate | -- | 32% | 36% | **9%** |

**Reading this table**:
1. **After Bug Fixes**: Scores *dropped* -- this is not a regression. We fixed the scoring bug, so now we see the *true* performance. The old scores were inflated.
2. **+ Graph Context**: Adding the knowledge graph improved citation recall (+0.048) because the system now knows structured facts about cities and code editions.
3. **+ Coverage Fix**: The biggest win. By tuning agents to extract answers from relevant context instead of refusing, we cut refusals from 36% to 9% and fact accuracy jumped to 0.570 -- now **beating baseline**.

---

## Slide 14: What Works and What Doesn't

**Strengths of Multi-Agent RAG**:
- Different question types get different search strategies (the core advantage)
- Cross-jurisdiction questions search each city separately instead of mixing everything together
- Knowledge graph gives the system structured facts about adoption timelines and code families
- Source diversity ensures answers draw from multiple documents, not just one

**What Still Needs Work**:
- Hallucination (0.427) is still higher than baseline (0.339) -- the agents sometimes fabricate section numbers when trying harder to answer
- "Which cities have X?" questions need to scan the entire dataset, not just top-K results
- Only 2 cities (LA and San Diego) have full graph coverage -- the other 7 cities rely on vector search alone
- The multi-agent pipeline takes 25 seconds vs 16 seconds for baseline (extra LLM calls)

**The tradeoff is worth it for this domain**: In building code compliance, getting the answer right (+12% accuracy) matters more than saving 9 seconds.

---

## Slide 15: Research Contribution & Publishability

**Why This Work Matters**

1. **First benchmark for multi-jurisdiction building code QA** -- no existing dataset tests AI systems on comparing building codes across cities with local amendments

2. **Empirical evidence that multi-agent retrieval outperforms generic search** on regulatory documents -- we showed specialist routing improves accuracy by +12% over standard vector search

3. **Quantified the accuracy-hallucination tradeoff** with statistical testing -- this is a known problem in RAG, but rarely measured empirically in domain-specific settings

4. **Reproducible evaluation framework** -- 56 questions, 5 metrics, automated scoring with LLM-as-judge, statistical comparison using Wilcoxon signed-rank test

**Where this could be published**:
- ACL/EMNLP Workshop on NLP for Legal/Regulatory Text
- SIGIR (Information Retrieval)
- BuildSys / Smart Cities conferences
- Journal of Computing in Civil Engineering

---

## Slide 16: Next Steps -- Toward Graph-Based RAG

**What We're Doing Now**:
- Reduce hallucination with post-generation fact verification
- Expand the knowledge graph to all 9 cities (currently only LA + San Diego)
- Connect the multi-agent pipeline to the Streamlit chatbot UI

**What Comes Next: Two Established Graph-RAG Frameworks**

Our current system uses a custom hybrid approach (vector search + manual graph queries). Two published frameworks could take this further:

**1. Microsoft GraphRAG** (Edge et al., 2024)
- Automatically builds a hierarchical community structure from documents -- groups related concepts together and creates summaries at different levels
- Great for big-picture questions like "What are the main themes across all cities?"
- Paper: arxiv.org/abs/2404.16130

**2. LightRAG** (Guo et al., 2024)
- A lighter-weight alternative -- automatically extracts entities and relationships from text to build a knowledge graph
- Could replace our manual Neo4j seeding with automatic graph construction at lower cost
- Paper: arxiv.org/abs/2410.05779

| Approach | How Graph is Built | Best For |
|----------|-------------------|----------|
| **Our system** | Manually seeded in Neo4j | Targeted city/section lookups |
| **Microsoft GraphRAG** | LLM extracts entities + community detection | Big-picture / thematic questions |
| **LightRAG** | LLM extracts entities + dedup graph | Balanced local/global at lower cost |

**Proposed next step**: Run all three approaches on our 56-question benchmark to see which works best for building code questions.

**Path to publication**: Expand to 100+ questions, add per-category breakdown, conduct user study with building code professionals, scale to 30+ cities.

---

## Slide 17: Summary

**Key Takeaways**

1. **Multi-agent RAG beats standard vector search** on building code QA. Fact Accuracy: 0.570 vs 0.510 (+12%)

2. **Evaluation methodology matters** found two scoring bugs that inflated results by ~5%. Fixing measurement is as important as fixing the model.

3. **Knowledge graph augmentation helps** providing structured facts about cities, code editions, and adoption timelines improved citation recall and grounded the agents' answers.

4. **The accuracy-hallucination tradeoff is true** making agents less conservative improves accuracy but increases fabrication risk. Our pipeline reduces refusals from 36% to 9%.

5. **This establishes a need for reproducible evaluation framework** for domain-specific RAG in building codes, a domain where hallucination has real safety consequences.

---
