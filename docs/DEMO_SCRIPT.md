# Japanese Financial Table Parser — Presenter-Ready Demo Script (`DEMO_SCRIPT.md`)

This guide is designed for pair programming, technical screenings, or system presentations. It provides a sequence of checkpoints to navigate the codebase, what to say, what code to highlight, and answers to likely technical questions.

---

## 1. Quick Reference: The 10 Essential Components to Master

Before beginning, these 10 components form the core backbone of the parser:

1. **`run_pipeline.py`** (`run_pipeline`): End-to-end pipeline runner that executes extraction, scoring, and synthetic stress testing.
2. **`src/loader.py`** (`load_pdf`): Hardened PDF ingestion with encryption and corruption gating.
3. **`src/router.py`** (`PageRouter.assess_page`): Text layer trust evaluation; escalates to OCR if plausibility $< 85\%$ or words $< 15$.
4. **`src/row_clustering.py`** (`compute_adaptive_y_tolerance`): Dynamically scales vertical line clustering with median font height.
5. **`src/row_clustering.py`** (`detect_columns_and_gutter`): 1D gap-clustering on numeric right edges ($x_1$) to discover $N$ columns and label gutter.
6. **`src/number_parser.py`** (`parse_number`): Pure functional NFKC parser handling `△` negatives, `"△0"` zero values, and `－` printed nil.
7. **`src/structure.py`** (`StructureClassifier.classify_and_link`): 1D density clustering of label $x_0$ for depth tiers, stack-based parent resolution, and general total suffix linking.
8. **`src/writer.py`** (`format_output_document`): Canonical JSON schema formatting with root-level `confidence_flags`.
9. **`eval/aligner.py`** (`RowAligner.align`): Order-preserving edit-distance DP alignment with strict circularity prevention (numbers excluded).
10. **`eval/scorer.py`** (`TableScorer.score`): 5-layer cascading evaluation engine (Gate $\rightarrow$ Alignment $\rightarrow$ Cell Raw $\rightarrow$ Value Parsing $\rightarrow$ Hierarchy $\rightarrow$ Invariants).

---

## 2. Presentation Tracks & Recommended Timing

| Track | Duration | Target Audience | Focus Areas |
| :--- | :---: | :--- | :--- |
| **Track A (Fast-Track)** | **10–15 mins** | Engineering Managers / Quick Screen | High-level problem, end-to-end execution, adaptive layout clustering, and live test run. |
| **Track B (Deep-Dive)** | **30–45 mins** | Senior Engineers / Architects | Algorithmic implementations, 1D projection profile, DP alignment equations, error taxonomy, and invariant auditing. |

---

## 3. Presenter Checkpoint Sequence

---

### Checkpoint 1: System Entry Point & Execution
- **Open**: `run_pipeline.py` ([Lines 22–55](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/run_pipeline.py#L22-L55))
- **Say**:
  > *"We start at `run_pipeline.py`. This is the top-level orchestrator. It runs both our baseline and improved adaptive parsers on Page 4 of the consolidated balance sheet (`連結貸借対照表`), scores both against ground truth across 5 evaluation layers, tests our OCR fallback on a synthetic scanned page, and dumps comparison metrics to disk."*
- **Trace**:
  `pdf_path` $\rightarrow$ `baseline_parser.parse_pdf` $\rightarrow$ `scorer.score` $\rightarrow$ `improved_parser.parse_pdf` $\rightarrow$ `scorer.score`.
- **Demonstrate**:
  Run in terminal:
  ```powershell
  python run_pipeline.py
  ```
- **Likely Question**:
  *Q: Why evaluate both baseline and improved parsers in the same script?*
  **Answer**: *"To prove that our improvements actually move the needle on real metrics without regressions. The baseline achieves only 2.3% on parent hierarchy because it lacks typographic indentation modeling; the improved parser achieves 100% across all 5 layers."*

---

### Checkpoint 2: Hardened PDF Ingestion
- **Open**: `src/loader.py` ([Lines 17–46](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/loader.py#L17-L46))
- **Say**:
  > *"Next is `src/loader.py`. We don't just call PyMuPDF directly in the parser. We wrap it in a hardened loader that catches file-not-found, corrupt byte streams, empty zero-page PDFs, and handles password decryption gracefully with custom `PDFLoadError` exceptions."*
- **Connect**: Called by `FinancialTableParser.parse_pdf()`; passes `fitz.Document` to `PageRouter`.
- **Likely Question**:
  *Q: What happens if a filing is password-protected?*
  **Answer**: *"If a password is provided, `doc.authenticate(password)` is called. If authentication fails or no password was provided, it raises a clean `PDFLoadError` rather than crashing downstream."*

---

### Checkpoint 3: Trust Router & OCR Escalation
- **Open**: `src/router.py` ([Lines 60–120](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/router.py#L60-L120))
- **Say**:
  > *"Before attempting table parsing, we must assess whether the native text layer is trustworthy. In real filings, PDFs can be scanned images or have garbled font encodings. `PageRouter` checks three signals: word count, character plausibility ratio, and numeric token density. If character plausibility drops below 85% or words are under 15, we escalate to OCR stub with diagnostic flags rather than hallucinating numbers."*
- **Trace**:
  `page.get_text()` $\rightarrow$ `is_plausible_char` $\rightarrow$ `ratio` $\rightarrow$ `extraction_method: "text_layer"` vs `"ocr"`.
- **Demonstrate**:
  Point to the scanned page routing output in the terminal:
  ```
  Extraction Method: ocr
  Route Reason: Escalated to OCR/VLM stub: Low word count (0 words); Empty text layer...
  ```
- **Likely Question**:
  *Q: How do you define character plausibility?*
  **Answer**: *"We inspect codepoints using `is_plausible_char`: rejecting Unicode replacement characters (`\ufffd`) and Private Use Area codepoints while accepting standard CJK ideographs, hiragana, katakana, full-width numerals, and Japanese accounting symbols like triangle negatives (`△`)."*

---

### Checkpoint 4: Adaptive Column Discovery via Right-Edge Projection
- **Open**: `src/row_clustering.py` ([Lines 78–161](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/row_clustering.py#L78-L161))
- **Say**:
  > *"Here is one of our major architectural improvements: dynamic column detection. Older parsers rely on hardcoded x-coordinates like `split_x = 415.0`. If a document has 3 columns, or margins shift, or scaling changes, that breaks. Instead, we project the right edges ($x_1$) of all numbers across rows. In financial statements, numbers are strictly right-aligned, so their right edges cluster neatly regardless of how many digits a number has. We run 1D gap clustering to detect $N$ columns, derive column dividers, and isolate the label gutter."*
- **Trace**:
  `body_num_tokens` $\rightarrow$ sort by `x1` $\rightarrow$ cluster gaps $> 18.0\,\text{pt}$ $\rightarrow$ `col_bounds` $\rightarrow$ `col_splits` $\rightarrow$ `max_label_x`.
- **Likely Question**:
  *Q: Why use right edges ($x_1$) instead of horizontal centers ($(x_0 + x_1)/2$)?*
  **Answer**: *"Because small tokens like nil dashes (`－`) or small numbers have centers far to the right of 8-digit numbers. Right edges align to the column margin; centers do not."*

---

### Checkpoint 5: Number Normalization & Signs
- **Open**: `src/number_parser.py` ([Lines 14–64](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/number_parser.py#L14-L64))
- **Say**:
  > *"Our number parser is a pure functional module. It handles Japanese accounting negatives like `△1,923,585`, parentheses `(1,234)`, full-width unicode numerals (`１２３`), and printed nil dash markers (`－`). Crucially, `"△0"` is parsed as `status: "present"`, `value_in_unit: 0` because in accounting, reported zero is distinct from nil or parser failure."*
- **Trace**:
  `"△1,923,585"` $\rightarrow$ NFKC $\rightarrow$ detect leading `△` $\rightarrow$ strip comma $\rightarrow$ `val = -1923585` $\rightarrow$ `("present", -1923585)`.
- **Demonstrate**:
  Point out [tests/test_number_parser.py](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/tests/test_number_parser.py). Run:
  ```powershell
  pytest tests/test_number_parser.py
  ```
- **Likely Question**:
  *Q: How do you differentiate a printed dash (`－`) from an unreadable extraction failure?*
  **Answer**: *"Printed dashes belong to `NIL_MARKERS` and map to `status: "nil"`, `value_in_unit: None`. If text is missing or garbled, it maps to `status: "unreadable"`."*

---

### Checkpoint 6: Indentation Hierarchy & Accounting Lineage
- **Open**: `src/structure.py` ([Lines 35–120](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/structure.py#L35-L120))
- **Say**:
  > *"In Japanese balance sheets, hierarchy is encoded typographically by indentation. We run 1D density clustering on label left-coordinates (`label_x0`) with a 3.5pt jitter tolerance to discover the document's native depth tiers. Then we traverse a header stack to assign `parent_row_idx`. For contra accounts like `減価償却累計額`, they attach directly to the gross item above it ($i-1$). For net accounts (`純額`), they attach to the section header and link `derived_from = [i-2, i-1]`. For section totals, we dynamically discover which preceding items sum up to the total within tolerance."*
- **Trace**:
  `label_x0s` $\rightarrow$ sorted clusters $\rightarrow$ depth tiers $0..4$ $\rightarrow$ stack traversal $\rightarrow$ mathematical sum checks $\rightarrow$ `derived_from`.
- **Likely Question**:
  *Q: What happens if an unseen PDF has no indentation at all (a flat table)?*
  **Answer**: *"If fewer than 2 indentation tiers are detected, the classifier sets `parent_row_idx = None` and emits `confidence_flags: ["hierarchy_unavailable"]` rather than guessing false parents."*

---

### Checkpoint 7: Fail-Loud JSON Output Schema
- **Open**: `out/page4.json` ([Lines 1–25](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/out/page4.json#L1-L25))
- **Say**:
  > *"Here is the serialized JSON output. Notice the root-level metadata: `page`, `extraction_method`, `route_reason`, and `confidence_flags`. Each table has dynamic `columns`, and each cell is keyed by column ID (`cells.c1`, `cells.c2`). If there are any layout ambiguities or invariant discrepancies, they are explicitly recorded in `confidence_flags`."*
- **Trace**:
  `confidence_flags` array $\rightarrow$ `tables` $\rightarrow$ `rows` $\rightarrow$ `cells` with `raw`, `status`, `value_in_unit`.

---

### Checkpoint 8: Circularity-Free Order-Preserving DP Alignment
- **Open**: `eval/aligner.py` ([Lines 132–205](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/aligner.py#L132-L205))
- **Say**:
  > *"Let's look at the evaluation engine. To score predictions against ground truth, we implemented an edit-distance DP aligner. Notice our cost function: it uses normalized label string similarity, section context hierarchy, and document order drift. We strictly forbid using cell numbers in alignment. Why? Because if you match rows by numbers, you create circular evaluation and cannot detect when the parser puts the wrong number into a row."*
- **Trace**:
  `dp[i][j]` matrix $\rightarrow$ Match, Delete, Insert transitions $\rightarrow$ Backtracking $\rightarrow$ Tie detection (`Unresolved`).
- **Likely Question**:
  *Q: How do you handle repeated account titles like `その他` or `減価償却累計額`?*
  **Answer**: *"Section context similarity checks the parent chain. `減価償却累計額` under Buildings has parent `有形固定資産`, whereas under Leases it has parent `リース資産`. If costs are tied within $10^{-3}$, we classify it as `Unresolved`, penalizing both recall and precision."*

---

### Checkpoint 9: 5-Layer Cascading Evaluation
- **Open**: `eval/scorer.py` ([Lines 20–80](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/scorer.py#L20-L80))
- **Say**:
  > *"Our evaluation pipeline cascades through 5 strict layers. Layer 0 is the Page Gate. Layer 1 evaluates row alignment. Layer 2 evaluates raw cell extraction over ALL ground-truth cells—meaning dropped rows automatically count as extraction errors. Layer 3 evaluates parsed integer values only over confirmed raw-matched cells. Layer 4 evaluates hierarchy. Layer 5 checks ground-truth-independent accounting invariants."*
- **Demonstrate**:
  Point to `out/improved_report.txt` in editor.

---

### Checkpoint 10: Full Test Suite Execution
- **Say**:
  > *"To verify that the entire system is healthy, let's run the complete automated test suite."*
- **Demonstrate**:
  Run in terminal:
  ```powershell
  pytest
  ```
  Expected output: `43 passed in 0.15s`.
- **Run Stress Benchmark**:
  ```powershell
  python scripts/run_test_set.py reports/failures_after.md
  ```
  Show [reports/failures_after.md](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/reports/failures_after.md) to demonstrate 100% accuracy on all synthetic variants and clean invariant passing on real external corporate filings (Toyota, MHI, SoftBank).
