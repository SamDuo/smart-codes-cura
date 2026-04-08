# SmartCodes GraphRAG Architecture and Execution Plan (Neo4j + Supabase Hybrid)

## Summary

This plan upgrades the current Streamlit/Supabase vector RAG prototype into a GraphRAG system aligned with the `SmartCodes_Progress_Update.pptx` proposal (dated February 19, 2026), with immediate focus on:

1. Completing a Neo4j knowledge graph schema with all required relation types for building-code hierarchy, citations, versioning, and amendments.
2. Replacing manual file-by-file uploads with an automated shared-folder ingestion pipeline (direct scan of the OneDrive shared folder).
3. Defining a 100-item QA benchmark dataset and evaluation pipeline for citation accuracy, structural faithfulness, and temporal consistency.

Current-state findings used for this plan:
- `Agentic-RAG-with-LangChain` is a Streamlit prototype with manual uploads and `SupabaseVectorStore` (`pages/1_📚_Knowledge_Base.py`, `pages/2_🤖_Chatbot.py`).
- No Neo4j/GraphRAG implementation exists yet in the repo.
- Shared data folder contains ~381 PDFs (~732 MB PDFs) plus GIS/CSV/XLSX assets under `01_Data`.
- Building code chapter PDFs are filename-structured and mostly text-extractable (UpCodes exports), enabling deterministic metadata parsing.
- `Amendments.xlsx` already encodes yearly adoption/amendment signals by city for BC/RC and should become temporal graph edges.
- `support_files/ingest_in_db.ipynb` appears to contain exposed Supabase credentials in notebook output; rotate keys before implementation.

## Chosen Defaults (Locked for This Plan)

- Neo4j deployment for MVP: `Local Docker` (first-class target)
- MVP data scope: `2-city pilot` (`Los Angeles` + `San Diego`)
- Data ingestion source mode: `Direct shared-folder scan` (no manual upload UI)
- Vector DB for MVP: `Supabase` retained (hybrid with Neo4j)
- OS/runtime assumption: Windows local development (PowerShell, OneDrive shared path)
- Benchmark size: `100 annotated Q&A pairs`

## Goals and Success Criteria

### Goal A: Neo4j KG schema complete with all relation types
Success criteria:
- Neo4j schema documented and implemented with constraints/indexes.
- All defined core relation types are populated in pilot data (LA + San Diego).
- Cross-reference traversal and version traversal queries return valid paths.
- Amendment/adoption events from `Amendments.xlsx` are represented as temporal graph facts.

### Goal B: Shared-folder ingestion replaces manual upload workflow
Success criteria:
- System scans `C:\Users\qduong7\OneDrive - Georgia Institute of Technology\Synn, Sung Ho's files - BuildingCodeResearch\01_Data` directly.
- Incremental ingestion (skip unchanged files via manifest/hash/mtime).
- Files are chunked/embedded into Supabase with graph anchors (chunk-to-node linkage).
- No need to upload each PDF in Streamlit.

### Goal C: QA benchmark dataset (100 Q&A pairs) for RAG/GraphRAG validation
Success criteria:
- 100 annotated Q&A pairs created with evidence citations and expected answer constraints.
- Split defined (`dev`, `test`).
- Baseline vector-only and hybrid GraphRAG evaluation scripts produce comparable metrics.
- Metrics include citation recall, structural faithfulness, temporal consistency, and no-answer handling.

---

## Architecture Decision: Neo4j vs Alternatives

### Recommended: Neo4j + Supabase (Hybrid)
Why:
- Best fit for hierarchical/code citation traversal (`CITES`, `IS_PART_OF`, `SUPERSEDES`, `AMENDS`)
- Cypher is strong for explainable, traceable multi-hop retrieval
- Supports future vector indexing if you later consolidate from Supabase
- Clear path to GraphRAG while preserving current Supabase investment

### Alternatives Evaluated (Not selected for MVP)
1. `Supabase/Postgres-only (pgvector + recursive CTEs)`
- Pros: reuse existing stack
- Cons: harder to model/query deep citation/version paths and explain traversal
- Recommendation: keep only as vector/metadata store in MVP

2. `FAISS/Chroma + NetworkX`
- Pros: fast prototype
- Cons: weak persistence/multi-user ops, less robust for production-scale graph updates
- Recommendation: okay for experiments, not main system

3. `RDF/SPARQL triplestore`
- Pros: semantic rigor
- Cons: higher implementation overhead, less practical for current team velocity
- Recommendation: not MVP

---

## Target System Architecture (MVP and Extension Path)

## 1. Data Source Layer (Shared Folder Connector)
Source root:
- `C:\Users\qduong7\OneDrive - Georgia Institute of Technology\Synn, Sung Ho's files - BuildingCodeResearch\01_Data`

Connector behavior:
- Polling-based scanner (not filesystem watcher) every run/scheduled interval
- Manifest-driven incremental ingestion using:
  - `absolute_path`
  - `relative_path`
  - `size_bytes`
  - `mtime_utc`
  - `sha256` (content hash)
  - `ingestion_status`
  - `parse_status`
- OneDrive handling:
  - Detect inaccessible placeholder files
  - Log/hard-fail with “hydrate file” instruction if not locally available
  - Prefer “Always keep on this device” for pilot folders

Why polling instead of watcher:
- OneDrive/shared-folder sync can make real-time file events unreliable

## 2. Parsing and Normalization Layer
Pipeline stages per file:
1. File discovery + manifest dedupe
2. Metadata parsing from path/filename (city, year, code family, chapter/appendix, source type)
3. Text extraction
   - Primary: `pypdf`
   - Fallback: OCR queue for low-text pages
4. Structural segmentation
   - Chapter / section / subsection detection
   - Clause typing: `provision`, `condition`, `exception`, `penalty`, `definition` (where detectable)
5. Citation extraction (`§1403.2`, `R902`, etc.)
6. Canonical ID assignment
7. Graph upsert payload creation
8. Chunking + embedding payload creation (Supabase)
9. Validation + audit logging

## 3. Knowledge Graph Layer (Neo4j)
Stores:
- document hierarchy
- legal/code cross-references
- version lineage
- amendment/adoption temporal facts
- structural fingerprints and similarity/diff edges
- provenance/evidence linkage to chunks/pages/files

## 4. Vector Layer (Supabase)
Stores:
- chunk embeddings and retrieval metadata
- graph anchor IDs (`code_unit_id`, `clause_id`)
- ingestion run IDs and provenance
- optional benchmark/eval result tables

## 5. Hybrid Retrieval Layer (GraphRAG)
Query flow:
1. Query classify (`lookup`, `citation`, `cross-ref`, `change-over-time`, `compare`, `no-answer`)
2. Vector retrieve top-K chunks from Supabase
3. Extract graph anchors from chunks
4. Neo4j traversal expansion around anchors (bounded hops + relation filters)
5. Re-rank evidence bundle (vector relevance + graph path confidence + provenance quality)
6. LLM answer generation with citation path + confidence
7. Return answer + cited sections/pages + path trace

## 6. Evaluation Layer
- Benchmarks (100 annotated Q&A)
- Automated metrics and regression checks
- Baseline comparison:
  - vector-only (current style)
  - hybrid GraphRAG

---

## Neo4j Schema (Decision-Complete)

## Node Labels (MVP required)

1. `State`
- `state_code`, `state_name`

2. `Jurisdiction`
- `jurisdiction_id` (slug)
- `name`
- `state_code`
- `population` (from `Amendments.xlsx` if available)

3. `CodeFamily`
- `code_family_id` (`BC`, `RC`, `FC`, etc.)
- `name`
- `model_family` (`IBC`, `IRC`, `IFC`, `CBC`, `CRC`, etc. when mapped)

4. `CodeEdition`
- `code_edition_id`
- `jurisdiction_id` (nullable for model code editions)
- `code_family_id`
- `edition_year`
- `edition_name`
- `is_model_code` (bool)

5. `SourceFile`
- `source_file_id` (= sha256)
- `relative_path`
- `absolute_path`
- `file_name`
- `size_bytes`
- `mtime_utc`
- `source_root`
- `source_type` (`building_codes`, `amendment_pdf`, `amendment_matrix`, etc.)

6. `DocumentUnit`
- Represents chapter/appendix/article-level document partitions
- `document_unit_id`
- `unit_type` (`chapter`, `appendix`, `whole_ordinance`, etc.)
- `label`, `number`, `title`

7. `CodeUnit`
- Core section/subsection node
- `code_unit_id`
- `canonical_ref` (normalized citation)
- `raw_ref`
- `title`
- `text`
- `level` (`section`, `subsection`, `paragraph`, etc.)
- `page_start`, `page_end`
- `effective_year`
- `jurisdiction_id`
- `code_family_id`
- `code_edition_id`

8. `Clause`
- `clause_id`
- `clause_type` (`provision`, `condition`, `exception`, `penalty`, `definition`)
- `text`
- `sequence_no`

9. `AmendmentEvent`
- `amendment_event_id`
- `year`
- `event_type` (`adoption`, `amendment`)
- `source_value` (e.g., `2022_CBC`)
- `is_amended` (bool)
- `sheet` (`BC`/`RC`)

10. `Chunk`
- `chunk_id`
- `supabase_table`
- `supabase_row_id`
- `content_hash`
- `char_start`, `char_end`
- `page`
- `embedding_model`

11. `Fingerprint`
- `fingerprint_id`
- `structure_hash`
- `semantic_hash` (or embedding ref)
- `schema_version`
- `divergence_score` (optional computed edge property instead)

12. `Hazard` (extension-ready but included in schema now)
- `hazard_id` (`wildfire`, `seismic`, etc.)
- `name`

## Relationship Types (All required schema relation types)

### Hierarchy / containment
- `(:State)-[:HAS_JURISDICTION]->(:Jurisdiction)`
- `(:Jurisdiction)-[:HAS_CODE_EDITION]->(:CodeEdition)`
- `(:CodeFamily)-[:HAS_EDITION]->(:CodeEdition)`
- `(:CodeEdition)-[:HAS_DOCUMENT_UNIT]->(:DocumentUnit)`
- `(:DocumentUnit)-[:HAS_CODE_UNIT]->(:CodeUnit)`
- `(:CodeUnit)-[:IS_PART_OF]->(:CodeUnit)` (subsection/paragraph nesting)
- `(:CodeUnit)-[:HAS_CLAUSE]->(:Clause)`

### Provenance / evidence
- `(:SourceFile)-[:CONTAINS_DOCUMENT_UNIT]->(:DocumentUnit)`
- `(:CodeUnit)-[:DERIVED_FROM_FILE]->(:SourceFile)`
- `(:CodeUnit)-[:EVIDENCED_BY_CHUNK]->(:Chunk)`
- `(:Clause)-[:EVIDENCED_BY_CHUNK]->(:Chunk)`
- `(:Chunk)-[:FROM_FILE]->(:SourceFile)`

### Citation and structural references
- `(:CodeUnit)-[:CITES]->(:CodeUnit)`
- `(:Clause)-[:CITES]->(:CodeUnit)`
- `(:Clause)-[:CONDITION_FOR]->(:Clause)` (when parser can infer)
- `(:Clause)-[:EXCEPTION_TO]->(:Clause)` (when parser can infer)
- `(:Clause)-[:PENALTY_FOR]->(:Clause)` (when parser can infer)
- `(:Clause)-[:DEFINES_TERM]->(:Clause)` (optional if terms modeled later; kept reserved but declared)

### Versioning / temporal comparison
- `(:CodeUnit)-[:NEXT_VERSION]->(:CodeUnit)`
- `(:CodeUnit)-[:PREVIOUS_VERSION]->(:CodeUnit)`
- `(:CodeUnit)-[:SAME_CANONICAL_SECTION_AS]->(:CodeUnit)` (cross-edition alignment)
- `(:CodeUnit)-[:SUPERSEDES]->(:CodeUnit)` (when explicit)
- `(:CodeUnit)-[:AMENDS]->(:CodeUnit)` (jurisdiction section to model/base section)
- `(:CodeUnit)-[:DIVERGES_FROM {score: float}]->(:CodeUnit)` (fingerprinting output)

### Adoption / amendment events (from `Amendments.xlsx`)
- `(:Jurisdiction)-[:ADOPTION_EVENT]->(:AmendmentEvent)`
- `(:Jurisdiction)-[:AMENDMENT_EVENT]->(:AmendmentEvent)`
- `(:AmendmentEvent)-[:FOR_CODE_FAMILY]->(:CodeFamily)`
- `(:AmendmentEvent)-[:TARGETS_CODE_EDITION]->(:CodeEdition)` (when resolvable)
- `(:AmendmentEvent)-[:EVIDENCED_BY_FILE]->(:SourceFile)` (if ordinance PDF exists)

### Fingerprinting
- `(:CodeUnit)-[:HAS_FINGERPRINT]->(:Fingerprint)`
- `(:Fingerprint)-[:SIMILAR_TO {score: float}]->(:Fingerprint)`

### Domain tagging (MVP optional population, schema included)
- `(:CodeUnit)-[:AFFECTS_HAZARD]->(:Hazard)`
- `(:Clause)-[:AFFECTS_HAZARD]->(:Hazard)`

## Neo4j Constraints and Indexes (MVP)
Create unique constraints on:
- `Jurisdiction.jurisdiction_id`
- `CodeFamily.code_family_id`
- `CodeEdition.code_edition_id`
- `SourceFile.source_file_id`
- `DocumentUnit.document_unit_id`
- `CodeUnit.code_unit_id`
- `Clause.clause_id`
- `AmendmentEvent.amendment_event_id`
- `Chunk.chunk_id`
- `Fingerprint.fingerprint_id`
- `Hazard.hazard_id`

Create lookup indexes on:
- `CodeUnit.canonical_ref`
- `CodeUnit.title`
- `CodeUnit.effective_year`
- `CodeUnit.jurisdiction_id`
- `Clause.clause_type`
- `SourceFile.relative_path`

---

## Shared-Folder Ingestion Strategy (Replacing Manual Upload)

## Recommended approach (MVP): Direct shared-folder scan + manifest + optional local cache
Why:
- Eliminates manual upload bottleneck
- Preserves current shared team workflow
- Minimal duplication
- Supports incremental re-runs

### Directory strategy
Do not copy all files into repo.
Instead:
- Register source roots in config (`shared_folder` path)
- Maintain a repo-local manifest database/file (small)
- Optionally maintain extracted-text/cache artifacts in repo-adjacent cache directory (not source PDFs)

### Optional supported modes (same pipeline interface)
1. `direct_scan` (default)
2. `local_mirror` (for reproducibility/offline runs)
3. `supabase_storage_sync` (future collaboration/cloud runs)

## Data source config (new interface)
`config/data_sources.yaml`
- source ID
- root path
- include patterns
- exclude patterns
- source type mapping rules
- priority
- OCR policy
- hydration required flag (OneDrive)

## Manifest store (new interface)
`data/ingestion_manifest.sqlite` (recommended) or `data/ingestion_manifest.jsonl`
Tracks:
- source file identity
- parse status
- graph upsert status
- vector upsert status
- last error
- retry count
- timestamps

---

## Supabase Integration Plan (Keep Current Investment)

## Current state
- Prototype stores chunks in `documents` and retrieves via `match_documents` (`pages/1_📚_Knowledge_Base.py`, `pages/2_🤖_Chatbot.py`).
- Manual UI upload is the bottleneck.

## MVP target
Keep Supabase as vector DB, but create a dedicated table/RPC for building-code GraphRAG data.

### New Supabase table (recommended): `code_chunks`
Columns:
- `id` (uuid)
- `chunk_id` (text, unique)
- `content` (text)
- `metadata` (jsonb)
- `embedding` (vector)
- `source_file_id` (text)
- `jurisdiction_id` (text)
- `code_family_id` (text)
- `code_edition_id` (text)
- `document_unit_id` (text, nullable)
- `code_unit_ids` (jsonb array)
- `page_start` (int)
- `page_end` (int)
- `ingestion_run_id` (text)
- `content_hash` (text)

### New RPC
- `match_code_chunks(query_embedding vector, filter jsonb, match_count int)` (name exact for planning)

### Synchronization rule
Every chunk inserted into Supabase must include at least one graph anchor:
- `code_unit_ids[]` and/or `document_unit_id`
This is required for hybrid retrieval expansion.

### Security task (mandatory pre-work)
- Rotate Supabase service key
- Remove notebook outputs / secrets from `support_files/ingest_in_db.ipynb`
- Move all credentials to `.env` only

---

## Structural Fingerprinting Module (Aligned to PPT)

## Purpose
Implement the “Structural Fingerprinting” feature from the proposal:
- normalize section structure
- compare city-to-city and year-to-year
- detect novel amendments/divergence from model codes

## Inputs
- Parsed `CodeUnit` + `Clause` graph nodes
- Canonical alignment edges (`SAME_CANONICAL_SECTION_AS`)
- Text + clause-type sequence

## Fingerprint output
For each `CodeUnit`:
- `structure_signature` (ordered clause pattern; e.g., `PROVISION->CONDITION->EXCEPTION`)
- `structure_hash`
- `semantic_embedding_ref` (reuse chunk/section embedding or separate)
- `normalized_features` (json)
- `fingerprint_version`

## Comparisons
Create:
- `DIVERGES_FROM` edge between aligned code units with `score`
- `SIMILAR_TO` edge between fingerprints for top-N nearest neighbors (bounded)

## MVP scope
- LA vs San Diego
- same code family and chapter where alignment is possible
- year-to-year within same jurisdiction for available editions

---

## Hybrid Retrieval Design (GraphRAG)

## Retrieval modes
1. `Citation lookup`
2. `Hierarchy lookup` (chapter/section/subsection)
3. `Cross-reference traversal`
4. `Temporal change` (year-to-year)
5. `Cross-city comparison`
6. `No-answer / insufficient evidence`

## Retrieval algorithm (MVP exact behavior)
1. Vector retrieval from `code_chunks` in Supabase (`top_k=12`)
2. Extract distinct `code_unit_ids`
3. Neo4j expansion:
- hops `<=2` for `CITES`, `IS_PART_OF`, `HAS_CLAUSE`
- hops `<=1` for `NEXT_VERSION`, `PREVIOUS_VERSION`, `SAME_CANONICAL_SECTION_AS`, `AMENDS`
4. Score evidence bundle:
- vector relevance (0.5)
- graph-path relevance (0.3)
- provenance quality (0.2; direct section chunk > clause chunk > document chunk)
5. LLM answer with:
- cited section refs
- path trace summary
- confidence bucket (`high`, `medium`, `low`)
6. If evidence below threshold:
- return “insufficient evidence” and list best citations

## Baseline retained for comparison
- Existing vector-only similarity retrieval (current pattern in `pages/2_🤖_Chatbot.py`)

---

## QA Benchmark Dataset (100 Annotated Q&A Pairs)

## Dataset purpose
Validate GraphRAG against proposal goals:
- factual grounding
- citation correctness
- structural reasoning
- temporal consistency
- reduced hallucination

## Dataset composition (100 total, decision-complete)
- 20 `citation lookup` questions
- 15 `hierarchy navigation` questions
- 20 `cross-reference` multi-hop questions
- 20 `temporal change` (year-to-year)
- 15 `cross-city comparison` questions
- 10 `no-answer / insufficient evidence` questions

## Scope for annotation (MVP)
- Cities: `Los Angeles`, `San Diego`
- Code families: `Building`, `Fire`, `Residential` where present
- Amendment/ordinance PDFs + chapter PDFs
- Include at least 20 questions that depend on amendment/ordinance evidence

## Annotation schema (file/table interface)
`benchmarks/qa_benchmark_v1.jsonl`
Fields:
- `qa_id`
- `question`
- `question_type`
- `jurisdiction_scope`
- `code_family_scope`
- `year_scope`
- `expected_answer_short` (1-3 sentences)
- `required_citations` (list of canonical refs and/or file+page)
- `allowed_citations` (optional list)
- `required_relation_paths` (optional; e.g., `CITES>IS_PART_OF`)
- `gold_no_answer` (bool)
- `difficulty` (`easy`, `medium`, `hard`)
- `notes`
- `annotator`
- `review_status`

## Split
- `dev`: 40
- `test`: 60

## Annotation workflow
1. Generate candidate questions from templates + parsed graph coverage
2. Manually author/refine gold answers and citations
3. Peer review each item (1 reviewer pass)
4. Freeze `qa_benchmark_v1`

## Metrics (MVP exact)
- `Citation Recall@K`
- `Citation Precision@K`
- `Answer Faithfulness` (evidence-supportedness)
- `Structural Faithfulness` (required relation path satisfied)
- `Temporal Consistency` (correct year/version alignment)
- `No-Answer Precision/Recall`
- `Hallucination Rate` (answers citing nonexistent/incorrect refs)

## Reporting format
`eval_reports/YYYYMMDD_runid/summary.json` + markdown table:
- vector-only baseline
- hybrid GraphRAG
- delta by question type

---

## Important Changes / Additions to Public APIs, Interfaces, and Types

## New configuration interfaces
1. `config/data_sources.yaml`
- Defines shared folder roots, include/exclude rules, source modes

2. `config/graph_schema.yaml` (optional but recommended)
- Declarative mapping of labels/relations and parsing rules

3. `config/ingestion_profile.yaml`
- Chunking sizes, OCR policy, parser thresholds, pilot scope filters

## New CLI interfaces (exact commands to plan around)
1. `python -m smartcodes.ingest.scan --source shared_codes --scope pilot`
- Build/update manifest only

2. `python -m smartcodes.ingest.parse --scope pilot`
- Parse and normalize source files into structured artifacts

3. `python -m smartcodes.ingest.graph --scope pilot`
- Upsert Neo4j nodes/edges

4. `python -m smartcodes.ingest.vector --scope pilot`
- Upsert Supabase `code_chunks`

5. `python -m smartcodes.eval.run --benchmark benchmarks/qa_benchmark_v1.jsonl --mode hybrid`
- Run benchmark and generate report

## New data interfaces / types (internal but stable)
- `SourceFileRecord`
- `ParsedCodeDocument`
- `DocumentUnitRecord`
- `CodeUnitRecord`
- `ClauseRecord`
- `CitationEdgeRecord`
- `AmendmentEventRecord`
- `ChunkRecord`
- `FingerprintRecord`
- `QAItem`
- `EvalResult`

## Streamlit integration changes (later in implementation)
- Knowledge Base page stops being the primary ingestion path
- Add “Run ingestion / Scan shared folder” admin controls
- Chatbot page calls hybrid retrieval backend instead of direct `similarity_search` only

---

## Implementation Phases (Weeks 1-4 Immediate Milestones)

## Week 1: Foundations and Schema
- Rotate leaked Supabase credentials and clean secret exposure risk
- Add project structure for ingestion/graph/eval modules
- Define Neo4j schema (labels, rel types, constraints, indexes)
- Implement shared-folder manifest scanner (`direct_scan`)
- Parse metadata from paths/filenames for pilot scope (LA/SD)

Deliverables:
- Schema spec document
- Manifest DB populated for pilot files
- Pilot file inventory report

## Week 2: Parsing + Graph Upsert
- Implement PDF text extraction pipeline (`pypdf`, OCR fallback stub)
- Implement hierarchical parsing into `DocumentUnit` + `CodeUnit` + `Clause`
- Extract citations and build `CITES`
- Import `Amendments.xlsx` as `AmendmentEvent` graph data
- Upsert Neo4j for pilot corpus

Deliverables:
- Neo4j populated with hierarchy/citation/version/adoption/amendment core edges
- Validation queries showing non-empty counts for each core relation type

## Week 3: Supabase Hybrid Retrieval + Fingerprinting (MVP)
- Chunk parsed text and load `code_chunks` to Supabase with graph anchors
- Build hybrid retriever (Supabase + Neo4j traversal)
- Implement initial structural fingerprinting and `DIVERGES_FROM`
- Add path-trace citations in answer output

Deliverables:
- End-to-end GraphRAG query pipeline for pilot corpus
- Fingerprint comparison outputs for at least one cross-city or cross-year chapter set

## Week 4: Benchmark + Evaluation + Proposal Alignment Check
- Define and annotate 100 QA benchmark items
- Run baseline vector-only and hybrid GraphRAG eval
- Produce metrics and error analysis
- Gap assessment against PPT proposal milestones

Deliverables:
- `qa_benchmark_v1`
- Eval report with metrics
- Proposal alignment checklist (pass/fail + next actions)

---

## Test Cases and Scenarios

## A. Ingestion and Manifest
1. New file detection
- Add a new pilot PDF under shared folder
- Scanner marks file as `new`
- Parse and ingest run creates graph/vector records

2. Unchanged file skip
- Re-run scanner/ingest with no file changes
- Manifest marks file `unchanged`
- No duplicate graph/vector inserts

3. Modified file re-ingest
- Change file contents (same name)
- Hash changes
- Old version lineage preserved, new ingest run recorded

4. OneDrive placeholder file
- File exists but is not hydrated
- Pipeline logs actionable error and skips without crashing entire run

## B. Parsing and Schema
1. Chapter PDF parsing
- Correctly derives city/year/code family/chapter title from filename
- Creates `DocumentUnit` and child `CodeUnit` nodes

2. Citation extraction
- `§` references become `CITES` edges where target exists
- Unresolved citations logged for resolution queue

3. Clause typing
- `exception`, `provided that`, penalty-like phrases produce clause records/edges (when rules match)
- No false hard failure if clause typing is uncertain

4. Amendment matrix import
- `Amendments.xlsx` BC/RC rows create `AmendmentEvent` nodes and event edges
- Population/state/city mapping validated

## C. Hybrid Retrieval
1. Citation lookup question
- Returns direct cited section and source pages
- Includes citation in final answer

2. Cross-reference question
- Uses graph traversal beyond top vector chunks
- Path trace shows `CITES` chain

3. Temporal change question
- Traverses `NEXT_VERSION` / `SAME_CANONICAL_SECTION_AS`
- Answer cites both years

4. No-answer case
- System returns insufficient evidence, not hallucinated code text

## D. Structural Fingerprinting
1. Same section across years
- Fingerprints created for aligned sections
- Divergence score computed and stored

2. Cross-city comparison
- Aligned sections produce `DIVERGES_FROM` with score
- Reserved/no-text sections handled without crash

## E. Benchmark and Evaluation
1. Benchmark schema validation
- All 100 items parse and required fields exist
2. Baseline vs hybrid run
- Reports generated for both modes
3. Metric consistency
- Citation metrics computed deterministically for same run inputs

---

## Risks and Mitigations

1. PDF quality variance / OCR noise
- Mitigation: text-density detection, OCR fallback queue, provenance flags per page/chunk

2. Cross-reference normalization ambiguity
- Mitigation: canonical ref normalization rules + unresolved citation registry

3. Overly broad scope too early
- Mitigation: locked pilot (`LA`, `San Diego`) before scaling to 30 cities

4. OneDrive sync quirks
- Mitigation: polling scanner + hydration checks, optional local mirror mode

5. Secret exposure / credential hygiene
- Mitigation: rotate Supabase keys immediately, remove notebook outputs, use `.env` only

---

## Proposal Alignment Checklist (What “aligned with the proposal” means)

The system will be considered aligned when all are true:
- Neo4j KG schema exists and includes hierarchy, citation, amendment, and temporal relation types
- Hybrid retrieval (graph traversal + vector search) is running for pilot corpus
- Structural fingerprinting module produces divergence outputs
- QA benchmark dataset (100 annotated Q&A) exists and is used for evaluation
- Evaluation report includes citation recall and structural faithfulness metrics
- Answers include traceable citations/path evidence

---

## Explicit Assumptions and Defaults Chosen

- First implementation will not attempt all ~120 cities shown in the proposal; it will validate architecture on `Los Angeles` + `San Diego`.
- Supabase remains the vector database in MVP; Neo4j is added for graph structure and traversal (no immediate vector DB migration).
- Building code chapter PDFs and amendment PDFs are the primary corpus for MVP; GIS/large geojson assets are out of scope for immediate GraphRAG.
- Shared-folder ingestion is direct scan in-place; no repo-wide file copy is required.
- OCR is fallback-only in MVP, not mandatory for every PDF.
- Benchmark annotation is manual-reviewed and stored as JSONL for reproducibility.
- Streamlit UI modernization is secondary to backend GraphRAG correctness and evaluation.
