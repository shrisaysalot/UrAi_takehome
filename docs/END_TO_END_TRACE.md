# Japanese Financial Table Parser — Complete End-to-End Execution Trace (`END_TO_END_TRACE.md`)

This document traces **one complete, real run** of the parser on `data/balance_sheet_page4.pdf` from the moment the command is invoked to the generation of the final JSON output and evaluation score report.

Every stage shows the real functions involved, the actual data received, transformations performed, and the output passed to the next stage.

---

## Stage 1: Invocation & Entry

- **Trigger Command**:
  ```powershell
  python run_pipeline.py
  ```
- **Executing Module**: `run_pipeline.py:L22` (`run_pipeline`)
- **Initial Parameters**:
  - `pdf_path = "data/balance_sheet_page4.pdf"`
  - `page_idx = 0` (0-indexed first page in PDF file)
  - `gt_path = "data/ground_truth_v0.json"`
  - `out_path = "out/page4.json"`
  - `mode = "improved"`

---

## Stage 2: Loading & Hardened Validation

- **Executing Function**: `src/loader.py:load_pdf(pdf_path)`
- **Input**: `"data/balance_sheet_page4.pdf"`
- **Internal Checks**:
  1. `os.path.exists(...)` $\rightarrow$ File exists on disk (290,139 bytes).
  2. `fitz.open(...)` $\rightarrow$ Document initialized cleanly.
  3. `doc.is_encrypted` $\rightarrow$ `False` (no password needed).
  4. `len(doc)` $\rightarrow$ `1` page (non-empty).
- **Output Produced**: PyMuPDF `fitz.Document` object with 1 page, page bounds `Rect(0.0, 0.0, 595.2, 841.8)`.

---

## Stage 3: Page Trust Routing Assessment

- **Executing Function**: `src/router.py:PageRouter.assess_page(page)`
- **Input**: `fitz.Page` (Page 0)
- **Extracted Text Metrics**:
  - Raw character count: 878 characters.
  - Non-space characters: 735 characters.
  - Plausible characters: 735 / 735 ($100.0\%$). No `\ufffd` replacement or private-use code points.
  - Word count: 132 words ($\ge 15$).
  - Numeric tokens: 83 numeric tokens ($\ge 5$).
- **Router Decision**:
  - `extraction_method`: `"text_layer"`
  - `is_trustworthy`: `True`
  - `route_reason`: `"High character plausibility (100.0%), sufficient word count (132 words), and 83 numeric tokens detected."`
  - `confidence_flags`: `[]`

*(Note: On `data/synthetic/scanned_page.pdf`, this stage detects 0 words and routes to `ocr` with `confidence_flags: ["escalate_to_ocr", "text_layer_missing"]`)*.

---

## Stage 4: Geometric Word Token Extraction

- **Executing Function**: `src/extractor.py:extract_page_elements(page)`
- **Transformation**: Unpacks PyMuPDF `page.get_text("words")` into structured dictionaries.
- **Sample Output Token (Word #3)**:
  ```python
  {
    "text": "（訂正後）",
    "bbox": [54.72, 58.68, 104.64, 73.62],
    "x0": 54.72, "y0": 58.68, "x1": 104.64, "y1": 73.62,
    "block_no": 2, "line_no": 0, "word_no": 0
  }
  ```
- **Total Tokens Extracted**: 132 word tokens.

---

## Stage 5: Vertical Line Formation & Page Number Extraction

- **Executing Functions**:
  - `src/row_clustering.py:compute_adaptive_y_tolerance(words)`
  - `src/row_clustering.py:RowClusterer.cluster_visual_lines(words)`
  - `src/row_clustering.py:RowClusterer.extract_page_number(lines)`
- **Adaptive Calculation**:
  - Median word height across tokens = $9.0\,\text{pt}$.
  - Adaptive $y_{\text{tol}} = \max(2.0, \min(8.0, 0.35 \times 9.0)) = 3.15\,\text{pt}$.
- **Resulting Visual Lines**: 132 words grouped into 47 visual horizontal lines.
- **Page Number Extracted**:
  - Last line token: `"-"`, `"4"`, `"-"` $\rightarrow$ regex matches `4`.
  - Nominal filing page number resolved to `4`.

---

## Stage 6: Metadata & 1D Column Clustering

- **Executing Functions**:
  - `src/row_clustering.py:RowClusterer.extract_metadata(lines)`
  - `src/row_clustering.py:RowClusterer.detect_columns_and_gutter(lines, start_idx)`
- **Header Parsing**:
  - Title detected: `line_str` contains `（１）連結貸借対照表` $\rightarrow$ `title_raw = "（１）連結貸借対照表"`.
  - Unit detected: `単位：千円` $\rightarrow$ `{"raw": "千円", "multiplier": 1000}`.
- **Adaptive Column Right-Edge Projection**:
  - Body numeric tokens sorted by right edge ($x_1$).
  - Two distinct right-edge clusters detected:
    - Column 1 right edges: cluster center $\approx 397.5\,\text{pt}$ (range: 347.9 to 397.5).
    - Column 2 right edges: cluster center $\approx 522.6\,\text{pt}$ (range: 472.9 to 522.6).
  - Derived Column Split Divider: $\text{split}_0 = (397.5 + 472.9) / 2 = 435.2\,\text{pt}$.
  - Derived Label Gutter: Label tokens end at $x_1 = 309.3\,\text{pt}$; Column 1 starts at $x_0 = 347.9\,\text{pt}$ $\rightarrow$ $x_{\text{gutter}} = 328.6\,\text{pt}$.
- **Column Header Mapping**:
  - Region $x \in [328.6, 435.2]$ maps to `前連結会計年度 (2025 年３月 31 日)` $\rightarrow$ `id: "c1"`, `period_end: "2025-03-31"`.
  - Region $x > 435.2$ maps to `当連結会計年度 (2026 年３月 31 日)` $\rightarrow$ `id: "c2"`, `period_end: "2026-03-31"`.

---

## Stage 7: Row Clustering & Cell Value Parsing

- **Executing Functions**:
  - `src/row_clustering.py:RowClusterer.cluster_rows(lines, ...)`
  - `src/number_parser.py:parse_number(raw)`
- **Label Gutter Partitioning & Wrapped Label Merging**:
  - Tokens with $x_1 \le 328.6$ are assigned to label; tokens with $x_0 > 328.6$ are assigned to value tokens.
  - Multi-line wrapped labels are detected and merged (e.g. standalone row without values followed by data row).
- **Cell Extraction & Number Normalization Samples**:
  - **Sample Item (Row 2, `現金及び預金`)**:
    - Raw token in $x \le 435.2$: `"2,002,429"` $\rightarrow$ NFKC $\rightarrow$ `parse_number` $\rightarrow$ `status: "present"`, `value_in_unit: 2002429`.
    - Raw token in $x > 435.2$: `"1,675,502"` $\rightarrow$ `status: "present"`, `value_in_unit: 1675502`.
  - **Sample Contra Account (Row 16, `減価償却累計額`)**:
    - Raw token in $x \le 435.2$: `"△1,923,585"` $\rightarrow$ leading `△` flags negative $\rightarrow$ `status: "present"`, `value_in_unit: -1923585`.
    - Raw token in $x > 435.2$: `"△1,987,194"` $\rightarrow$ `status: "present"`, `value_in_unit: -1987194`.
  - **Sample Nil Marker (Row 25, `建設仮勘定`)**:
    - `c1` raw token: `"28,348"` $\rightarrow$ `value_in_unit: 28348`.
    - `c2` raw token: `"－"` $\rightarrow$ in `NIL_MARKERS` $\rightarrow$ `status: "nil"`, `value_in_unit: None`.
- **Rows Constructed**: 43 data and header rows.

---

## Stage 8: Indentation Hierarchy & Accounting Lineage

- **Executing Function**: `src/structure.py:StructureClassifier.classify_and_link(rows, columns)`
- **Indentation Depth Clustering**:
  - Label $x_0$ positions clustered with 3.5pt jitter threshold into 5 discrete tiers:
    - Tier 0: $62.3\,\text{pt}$ (`資産の部`)
    - Tier 1: $75.2\,\text{pt}$ (`流動資産`, `固定資産`, `資産合計`)
    - Tier 2: $88.2\,\text{pt}$ (`有形固定資産`, `無形固定資産`, `投資その他の資産`)
    - Tier 3: $101.3\,\text{pt}$ (Standard items like `建物及び構築物（純額）`, `現金及び預金`)
    - Tier 4: $114.2\,\text{pt}$ (Gross items and contra accounts like `減価償却累計額`)
- **Parent Assignment**:
  - Grand total (Row 42, `資産合計`): Parent = Row 0 (`資産の部`).
  - Contra accounts (Row 16, 19, 23, 27, `減価償却累計額`): Attached to gross item above it (Row 15, 18, 22, 26).
  - Net accounts (Row 17, `建物及び構築物（純額）`): Attached to section header Row 14 (`有形固定資産`).
- **Mathematical Lineage (`derived_from`)**:
  - Row 17 (`建物及び構築物（純額）`): Net of gross Row 15 and contra Row 16 $\rightarrow$ `derived_from: [15, 16]`.
    - Check: $2,121,360 - 1,923,585 = 197,775$ (exact match).
  - Row 29 (`有形固定資産合計`): Sum of leaf net/standalone items `[17, 20, 21, 24, 25, 28]` $\rightarrow$ matches reported total within rounding tolerance ($\pm 1$ in `c1`, $\pm 3$ in `c2`).
  - Row 41 (`固定資産合計`): Sum of section totals `[29, 33, 40]` $\rightarrow$ matches reported total.
  - Row 42 (`資産合計`): Sum of `[12, 41]` (`流動資産合計` + `固定資産合計`) $\rightarrow$ matches reported total.
- **Invariants Audited**: All 20 domain identities pass within tolerance.

---

## Stage 9: Output Serialization

- **Executing Function**: `src/writer.py:format_output_document` and `save_output_json`
- **Output File Written**: `out/page4.json` (26,669 bytes, valid UTF-8 JSON).
- **Page-Level Header**:
  ```json
  {
    "page": 4,
    "extraction_method": "text_layer",
    "route_reason": "High character plausibility (100.0%), sufficient word count (132 words), and 83 numeric tokens detected.",
    "confidence_flags": [],
    "tables": [ ... ]
  }
  ```

---

## Stage 10: Evaluation & Layered Scoring

- **Executing Function**: `eval/scorer.py:TableScorer.score(gt_doc, pred_doc)`
- **Evaluation Progression**:
  1. **Page Gate**: 1 table found, 2 columns match GT $\rightarrow$ **PASSED**.
  2. **Layer 1: Order-Preserving DP Alignment**:
     - Aligns 43 predicted rows against 43 ground-truth rows.
     - Pairings: 43 Exact matches, 0 Fuzzy, 0 Unresolved, 0 Dropped, 0 Inserted.
     - Alignment cost: **0.0000**. Recall: **100.00%**, Precision: **100.00%**.
  3. **Layer 2: Cell Extraction**:
     - 74 / 74 GT data cells matched exact raw text $\rightarrow$ **100.00%**.
  4. **Layer 3: Value Parsing**:
     - 74 / 74 cells matched status and parsed integer value $\rightarrow$ **100.00%**.
  5. **Layer 4: Structure & Hierarchy**:
     - Header vs Item: 43 / 43 correct $\rightarrow$ **100.00%**.
     - Subtotal vs Total: 43 / 43 correct $\rightarrow$ **100.00%**.
     - Parent Chain: 43 / 43 correct $\rightarrow$ **100.00%**.
  6. **Layer 5: Invariants**:
     - 20 / 20 accounting identities verified $\rightarrow$ **All Invariants Passed**.
- **Final Report Generated**: Formatted via `eval/report.py` and saved to `out/improved_report.txt`.
