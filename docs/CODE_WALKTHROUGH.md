# Japanese Financial Table Parser — File-by-File Code Walkthrough (`CODE_WALKTHROUGH.md`)

This guide walks through every module and function in the repository in **exact runtime execution order**, explaining why each file exists, its function signatures, step-by-step internal logic, data transformations, and algorithms.

---

## 1. Orchestration Entry Point: `run_pipeline.py`

### A. File Purpose
- **Why it exists**: Serves as the primary operational entry point for running the extraction pipeline on sample documents, scoring predictions against ground truth, testing OCR escalation fallback, and outputting comparative performance reports.
- **Dependencies**: Uses `src.parser.FinancialTableParser`, `eval.scorer.TableScorer`, and `eval.report.format_report`.
- **What breaks if removed**: Automated regression benchmarking and evaluation reporting across baseline and improved modes cannot be triggered from a single command.

### B. Important Code Blocks
- **File**: `run_pipeline.py`
- **Function**: `run_pipeline()` ([Lines 22–114](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/run_pipeline.py#L22-L114))
  - **Inputs**: None (reads from `data/balance_sheet_page4.pdf` and `data/ground_truth_v0.json`).
  - **Outputs**: None (writes `out/page4_baseline.json`, `out/page4.json`, `out/baseline_report.txt`, `out/improved_report.txt`, and `out/evaluation_summary.json`).
  - **Side Effects**: Reads disk files, runs PyMuPDF raster rendering for a synthetic scanned PDF test, writes evaluation files to `out/`.
  - **Internal Logic**:
    1. Loads ground-truth JSON from `data/ground_truth_v0.json`.
    2. Instantiates `TableScorer(tolerance_per_term=1)`.
    3. Runs `FinancialTableParser(mode="baseline")`, parses Page 4, scores against GT, and prints/writes baseline report.
    4. Runs `FinancialTableParser(mode="improved")`, parses Page 4, scores against GT, and prints/writes improved report.
    5. Creates a synthetic raster PDF (`data/scratch/synthetic_scanned_page4.pdf`) by rendering Page 4 to a pixmap and stripping the text layer.
    6. Runs the router on the synthetic scanned document to verify that it escalates to OCR rather than hallucinating numbers.
    7. Dumps a comparison dictionary to `out/evaluation_summary.json`.

---

## 2. Ingestion & Validation: `src/loader.py`

### A. File Purpose
- **Why it exists**: Provides an isolated, hardened boundary for opening PDF files. Catches file missing, decryption errors, page emptiness, or format corruption before downstream parsing begins.
- **Used by**: `src/parser.py`.
- **What breaks if removed**: Unhandled PyMuPDF C-level errors or password crashes crash the process without descriptive diagnostics.

### B. Important Code Blocks
- **File**: `src/loader.py`
- **Class**: `PDFLoadError(Exception)` ([Lines 12–14](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/loader.py#L12-L14))
  - Custom exception for all PDF loading anomalies.
- **Function**: `load_pdf(pdf_path: str, password: Optional[str] = None) -> fitz.Document` ([Lines 17–46](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/loader.py#L17-L46))
  - **Inputs**: `pdf_path` (`str`), `password` (`Optional[str]`).
  - **Outputs**: `fitz.Document` (PyMuPDF document handle).
  - **Internal Logic**:
    1. Checks `os.path.exists(pdf_path)`; raises `FileNotFoundError` if missing.
    2. Wraps `fitz.open(pdf_path)` in `try/except Exception`; raises `PDFLoadError` if corrupt.
    3. Checks `doc.is_encrypted`: if password provided, calls `doc.authenticate(password)`. If authentication fails or no password given, closes document and raises `PDFLoadError`.
    4. Checks `len(doc) == 0`; raises `PDFLoadError` if empty.

---

## 3. Trust Routing & Quality Assessment: `src/router.py`

### A. File Purpose
- **Why it exists**: Evaluates whether the native PDF text layer is clean and trustworthy before table extraction proceeds. If the document is an image scan, whitespace-only, or has corrupted font encodings, it escalates to OCR.
- **Used by**: `src/parser.py`.
- **What breaks if removed**: The parser would attempt layout reconstruction on garbage characters or empty pages, outputting confident hallucinations.

### B. Important Code Blocks
- **File**: `src/router.py`
- **Function**: `is_plausible_char(c: str) -> bool` ([Lines 16–46](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/router.py#L16-L46))
  - **Inputs**: `c` (`str`, single character).
  - **Outputs**: `bool`.
  - **Internal Logic**: Checks character unicode codepoints:
    - Rejects Unicode replacement character `0xFFFD` (`\ufffd`) and Private Use Area (`0xE000` to `0xF8FF`).
    - Accepts ASCII printable (32–126), CJK Unified Ideographs (`0x4E00`–`0x9FFF`), Hiragana/Katakana (`0x3040`–`0x30FF`), CJK Punctuation (`0x3000`–`0x303F`), Fullwidth Forms (`0xFF00`–`0xFFEF`), Geometric triangles (`△`, `▲` `0x25B3`, `0x25B2`), and Japanese financial dashes (`－`, `—`, `―`).
- **Class / Method**: `PageRouter.assess_page(page: fitz.Page) -> Dict[str, Any]` ([Lines 60–139](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/router.py#L60-L139))
  - **Inputs**: `page` (`fitz.Page`).
  - **Outputs**: `routing_info` (`Dict[str, Any]`), containing:
    - `extraction_method`: `"text_layer"` or `"ocr"`.
    - `is_trustworthy`: `bool`.
    - `route_reason`: Explanation string.
    - `confidence_flags`: List of flags (`escalate_to_ocr`, `text_layer_missing`, `low_char_plausibility`).
    - `stats`: `word_count`, `char_plausibility`, `number_token_count`.
  - **Three Gating Signals**:
    1. **Word count**: `len(words) >= 15` (fails on scanned pages).
    2. **Plausibility ratio**: `plausible_chars / total_chars >= 0.85` (fails on font encoding corruption).
    3. **Number density**: `number_tokens >= 5` (fails on non-table text pages).

---

## 4. Geometric Word Extraction: `src/extractor.py`

### A. File Purpose
- **Why it exists**: Extracts low-level word tokens and bounding boxes from the native PDF page using PyMuPDF coordinate systems.
- **Used by**: `src/parser.py`.
- **What breaks if removed**: Raw text coordinates cannot be passed to line and column clustering.

### B. Important Code Blocks
- **File**: `src/extractor.py`
- **Function**: `extract_page_elements(page: fitz.Page) -> Dict[str, Any]` ([Lines 10–35](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/extractor.py#L10-L35))
  - **Inputs**: `page` (`fitz.Page`).
  - **Outputs**: `{"page_rect": [x0, y0, x1, y1], "words": List[Dict]}`.
  - **Internal Logic**: Calls `page.get_text("words")`, which returns tuples of `(x0, y0, x1, y1, word_str, block_no, line_no, word_no)`. Unpacks each word into a structured dictionary with float coordinates rounded to 2 decimal places.

---

## 5. Row Clustering & Adaptive Column Partitioning: `src/row_clustering.py`

### A. File Purpose
- **Why it exists**: Transforms an unordered bag of word tokens with coordinates into structured table rows, detects column headers, discovers column boundaries via right-edge clustering, and assigns numbers to columns.
- **Used by**: `src/parser.py`.
- **What breaks if removed**: Bounding boxes remain unclustered; column alignment and line formation collapse.

### B. Important Code Blocks & Algorithms
- **File**: `src/row_clustering.py`
- **Function**: `compute_adaptive_y_tolerance(words: List[Dict], fallback: float = 3.5) -> float` ([Lines 15–26](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/row_clustering.py#L15-L26))
  - Computes `median([w["y1"] - w["y0"] for w in words])` and returns `max(2.0, min(8.0, 0.35 * median_height))`.
  - **Why this exists**: Eliminates hardcoded line-clustering tolerance. Scales smoothly when pages are rendered at 0.8x or 1.2x.
- **Method**: `RowClusterer.cluster_visual_lines(words: List[Dict]) -> List[List[Dict]]` ([Lines 31–59](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/row_clustering.py#L31-L59))
  - **Algorithm**: Sorts words by $(y_0, x_0)$. Loops through tokens: if $|y_{\text{mid}} - \text{last\_}y_{\text{mid}}| \le y_{\text{tol}}$, appends token to the current line; otherwise starts a new line.
- **Method**: `RowClusterer.extract_page_number(lines, fallback=4) -> int` ([Lines 61–76](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/row_clustering.py#L61-L76))
  - Inspects bottom lines with regex `^[\s\-–—]*(\d+)[\s\-–—]*$`. Eliminates hardcoded page numbering.
- **Method**: `RowClusterer.detect_columns_and_gutter(lines, start_idx)` ([Lines 78–161](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/row_clustering.py#L78-L161))
  - **1D Right-Edge Projection Algorithm**:
    1. Filters body lines (after metadata, excluding footers) for numeric tokens (`parse_number(text)[0] in ("present", "nil")`).
    2. Sorts numeric tokens by right edge coordinate ($x_1$).
    3. Groups right edges into clusters where consecutive gap $> 18.0\,\text{pt}$.
    4. Filters out noise clusters with $< 20\%$ of max cluster count.
    5. Derives column boundaries $[x_{\min}, x_{\max}]$ for $N$ columns.
    6. Sets column split dividers at midpoints: $\text{split}_k = \frac{\text{col}_k[x_1] + \text{col}_{k+1}[x_0]}{2}$.
    7. Finds maximum $x_1$ of labels before column 1 ($x_{\text{label\_max}}$) and sets label gutter: $x_{\text{gutter}} = \frac{x_{\text{label\_max}} + \text{col}_1[x_0]}{2}$.
    8. Flags `column_boundaries_ambiguous` if numeric tokens are insufficient.
- **Method**: `RowClusterer.extract_metadata(lines)` ([Lines 163–255](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/row_clustering.py#L163-L255))
  - Detects table title (`貸借対照表`, `財政状態計算書`), unit (`単位：千円`, `単位：百万円`), and column headers.
  - Maps header text blocks to the $N$ detected columns based on horizontal midpoint overlap.
  - Normalizes dates to ISO (`2025-03-31`).
- **Method**: `RowClusterer.cluster_rows(lines, start_idx, columns, col_splits, max_label_x)` ([Lines 257–364](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/row_clustering.py#L257-L364))
  - Separates line tokens into label tokens ($x_1 \le x_{\text{gutter}}$) and value tokens ($x_0 > x_{\text{gutter}}$).
  - Merges wrapped multi-line labels: if candidate $i$ has no values and is not a category header, and candidate $i+1$ has values, concatenates their labels.
  - Assigns value tokens to columns `c1 .. cN` by comparing $x_1$ with `col_splits`.
  - Calls `parse_number()` for each cell.

---

## 6. Functional Number & Date Normalization: `src/number_parser.py`

### A. File Purpose
- **Why it exists**: Provides pure functional normalization for Japanese financial numbers, signs, nil dash markers, and dates.
- **Used by**: `src/row_clustering.py` and unit tests.
- **What breaks if removed**: Negative numbers (`△`), full-width digits, zero preservation (`△0`), and nil markers fail to parse.

### B. Important Code Blocks
- **File**: `src/number_parser.py`
- **Set**: `NIL_MARKERS = {"－", "-", "—", "―", "ー", "–", "−"}` ([Line 11](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/number_parser.py#L11))
- **Function**: `parse_number(raw: Optional[str]) -> Tuple[str, Optional[int]]` ([Lines 14–64](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/number_parser.py#L14-L64))
  - **Inputs**: `raw` (`Optional[str]`).
  - **Outputs**: `(status: str, value_in_unit: Optional[int])`.
  - **Internal Logic**:
    1. If `raw is None` or empty string: returns `("unreadable", None)`.
    2. If `raw.strip() in NIL_MARKERS`: returns `("nil", None)`.
    3. Normalizes unicode with NFKC (`unicodedata.normalize("NFKC", raw_str)`). Standardizes full-width `２,００２,４２９` $\rightarrow$ `2,002,429`.
    4. Detects negative markers: leading `△`, `▲`, minus sign, or parentheses `(1,234)`. Sets `is_negative = True` and strips the marker.
    5. Removes commas (`,`).
    6. If remaining string `.isdigit()`: computes integer `val = int(cleaned)`. If `is_negative`, returns `("present", -val)`. If `val == 0`, preserves `val = 0` (even for `△0`). Returns `("present", val)`.
    7. Otherwise returns `("unreadable", None)`.
- **Function**: `normalize_date_to_iso(raw_date: str) -> Optional[str]` ([Lines 66–88](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/number_parser.py#L66-L88))
  - Uses NFKC and regex `(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日` to format dates into `YYYY-MM-DD`.

---

## 7. Structure Classification & Lineage: `src/structure.py`

### A. File Purpose
- **Why it exists**: Implements adaptive typographic indentation depth clustering, stack-based parent resolution (`parent_row_idx`), general total typing, mathematical lineage linking (`derived_from`), and internal invariant verification.
- **Used by**: `src/parser.py`.
- **What breaks if removed**: Tree depth is lost; all rows default to flat items without parent or accounting links.

### B. Important Code Blocks & Algorithms
- **File**: `src/structure.py`
- **Method**: `StructureClassifier.classify_and_link(rows, columns) -> Tuple[List[Dict], List[str]]` ([Lines 18–255](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/structure.py#L18-L255))
  - **Algorithm Stage 1: Row Typing**:
    - If row has no values and no cells: `type = "header"`.
    - If label is `資産合計`, `負債及び純資産合計`, `負債及び資本合計`, or ends with `総計`: `type = "total"`.
    - If label contains `合計`, `小計`, `純額`, or ends with `計`: `type = "subtotal"`.
    - Otherwise: `type = "item"`.
  - **Algorithm Stage 2: 1D Density Clustering on Indentation (`label_x0`)**:
    - Collects `label_x0` across all rows.
    - Clusters points within a $3.5\,\text{pt}$ jitter threshold.
    - If $< 2$ clusters exist: flags `hierarchy_unavailable` and sets `parent_row_idx = None`.
    - If $\ge 2$ clusters exist: sorts cluster centers into ascending depth tiers ($L_0 < L_1 < \dots < L_k$). Each row is assigned level `min_k |x0 - center_k|`.
  - **Algorithm Stage 3: Stack-based Parent Resolution**:
    - Grand total (`type == "total"`): assigned parent = level 0 category header (e.g. `資産の部`).
    - Contra accounts (`減価償却累計額`): assigned parent = immediately preceding gross item ($i-1$).
    - Net accounts (`純額`): assigned parent = enclosing section header, not the contra account.
    - Other items: walks `header_stack` for the nearest preceding header with strictly smaller depth level.
  - **Algorithm Stage 4: Dynamic Mathematical Lineage (`derived_from`)**:
    - **Net rows (`純額`)**: links `derived_from = [i-2, i-1]` (gross and contra).
    - **Section totals (`...合計`, `...計`)**: tests subsets of candidate preceding rows:
      - Candidate 1: Leaf items in current section (excluding gross/contra already rolled into net rows).
      - Candidate 2: Major section subtotals before row $i$.
      - Evaluates sum across columns: checks if $|\sum \text{vals} - \text{reported}| \le k \times \text{tolerance\_per\_term}$ (treating nil `－` as 0).
      - If sum matches within tolerance across columns: links `derived_from = candidates`.
  - **Algorithm Stage 5: Domain Invariant Auditing**:
    - Verifies net asset checks and section sum checks on the predicted rows.
    - If any identity fails: appends `invariants_failed: [check_name]` to `confidence_flags`.

---

## 8. Serialization & Output Formatting: `src/writer.py`

### A. File Purpose
- **Why it exists**: Formats the final dictionary according to the canonical output schema and writes UTF-8 encoded JSON to disk without ASCII escaping.
- **Used by**: `src/parser.py`.

### B. Important Code Blocks
- **File**: `src/writer.py`
- **Function**: `format_output_document(page_num, extraction_method, route_reason, tables, confidence_flags) -> Dict[str, Any]` ([Lines 11–24](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/writer.py#L11-L24))
  - Emits root-level keys: `page`, `extraction_method`, `route_reason`, `confidence_flags`, `tables`.
- **Function**: `save_output_json(doc: Dict, filepath: str) -> None` ([Lines 27–30](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/writer.py#L27-L30))
  - Uses `json.dump(doc, f, ensure_ascii=False, indent=2)`.

---

## 9. Top-Level Parser Orchestration: `src/parser.py`

### A. File Purpose
- **Why it exists**: Ties the entire parsing pipeline together into an easy-to-use Python API with `parse_pdf` and `parse_page` methods.
- **Used by**: `run_pipeline.py`, tests, and external scripts.

### B. Important Code Blocks
- **File**: `src/parser.py`
- **Class**: `FinancialTableParser` ([Lines 19–137](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/src/parser.py#L19-L137))
  - `__init__(mode="improved", tolerance_per_term=1)`: Instantiates `PageRouter`, `RowClusterer`, and `StructureClassifier`.
  - `parse_page(doc, page_idx=0, page_num=None) -> Dict[str, Any]`:
    1. Calls `router.assess_page(page)`.
    2. If `extraction_method != "text_layer"`, emits `OCR_STUB` document with router flags.
    3. Calls `extract_page_elements(page)`.
    4. Calls `clusterer.cluster_visual_lines(words)`.
    5. Extracts nominal page number from footers if `page_num is None`.
    6. Calls `clusterer.extract_metadata(lines)` $\rightarrow$ gets title, unit, columns, `col_splits`, `max_label_x`.
    7. Calls `clusterer.cluster_rows(...)`.
    8. Calls `classifier.classify_and_link(rows, columns)`.
    9. Aggregates all `confidence_flags` and returns canonical JSON.
  - `parse_pdf(pdf_path, page_idx=0, page_num=None, out_path=None)`:
    - Wraps `load_pdf`, `parse_page`, and `save_output_json` in a safe `try/finally: doc.close()`.

---

## 10. Order-Preserving Dynamic Programming Alignment: `eval/aligner.py`

### A. File Purpose
- **Why it exists**: Evaluates row extraction accuracy by aligning ground-truth rows with predicted rows using edit-distance dynamic programming.
- **Critical Design Decision**: **Excludes numbers completely from row alignment** to prevent circular evaluation (matching rows because numbers match would mask extraction errors).
- **Used by**: `eval/scorer.py`.

### B. Important Code Blocks & Algorithms
- **File**: `eval/aligner.py`
- **Function**: `normalize_label(text: Optional[str]) -> str` ([Lines 13–18](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/aligner.py#L13-L18))
  - Normalizes text with NFKC and strips all whitespace (`"".join(norm.split())`).
- **Function**: `get_section_context(rows, idx) -> List[str]` ([Lines 21–51](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/aligner.py#L21-L51))
  - Climbs the `parent_row_idx` chain to collect preceding header names (e.g. `['資産の部', '固定資産', '有形固定資産']`).
- **Method**: `RowAligner.match_cost(gt_row, gt_idx, M, pred_row, pred_idx, N, gt_ctx, pred_ctx) -> Tuple[float, float, bool]` ([Lines 91–130](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/aligner.py#L91-L130))
  - **Cost Formula**:
    $$\text{cost} = (1.0 - \text{ratio}) + 0.6 \times (1.0 - \text{sec\_sim}) + 0.3 \times \left|\frac{i}{M-1} - \frac{j}{N-1}\right|$$
  - If character similarity ratio $< 0.70$, matching is disallowed.
- **Method**: `RowAligner.align(gt_rows, pred_rows) -> Dict[str, Any]` ([Lines 132–322](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/aligner.py#L132-L322))
  - **Edit-Distance DP Matrix**:
    - State: `dp[i][j]` = minimum cost to align $i$ GT rows and $j$ predicted rows.
    - Transitions:
      - Match (`M`): `dp[i-1][j-1] + match_cost`
      - Delete GT (`D`): `dp[i-1][j] + 1.0`
      - Insert Pred (`I`): `dp[i][j-1] + 1.0`
  - **Traceback**: Reconstructs optimal alignment operations.
  - **Tie / Ambiguity Detection**: If multiple predicted rows have tied match costs ($< 10^{-3}$) for a GT row (common with repeated labels like `減価償却累計額`), flags the outcome as `Unresolved` rather than arbitrarily guessing.
  - **Merge / Split Diagnostics**: Detects 2-to-1 merges (`norm_g1 + norm_g2 == norm_p`) and 1-to-2 splits.

---

## 11. Layered Evaluation Engine: `eval/scorer.py`

### A. File Purpose
- **Why it exists**: Implements the 5-layer evaluation checklist where each layer evaluates only surviving inputs from the previous layer.
- **Used by**: `run_pipeline.py`, `scripts/run_test_set.py`, and test suites.

### B. Important Code Blocks
- **File**: `eval/scorer.py`
- **Method**: `TableScorer.score(gt_doc, pred_doc) -> Dict[str, Any]` ([Lines 20–253](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/scorer.py#L20-L253))
  - **Page Gate**: Verifies predicted document contains a table and matching column count. If failed, halts downstream scoring.
  - **Layer 1 (Alignment)**: Evaluates row recall, precision, unresolved rows, and exact label accuracy.
  - **Layer 2 (Cell Raw)**: Scored over **all ground-truth data cells** (denominator = total GT cells). Unmatched or dropped rows count as cell errors.
  - **Layer 3 (Value Parsing)**: Evaluates `status` and `value_in_unit` over confirmed rows whose raw string matched GT.
  - **Layer 4 (Structure)**: Evaluates header-vs-item accuracy, subtotal/total accuracy, and parent chain accuracy.
  - **Layer 5 (Invariants)**: Evaluates balance sheet identity, net asset identities, and section item sums against reported subtotals (ground-truth independent).
- **Method**: `TableScorer.check_invariants(table_dict) -> Dict[str, Any]` ([Lines 255–353](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/scorer.py#L255-L353))
  - Evaluates internal accounting integrity on any table dict without requiring ground truth.

---

## 12. Human-Readable Report Formatter: `eval/report.py`

### A. File Purpose
- **Why it exists**: Formats the dictionary returned by `TableScorer.score()` into a clean, human-readable terminal and text report.
- **Used by**: `run_pipeline.py`.
- **Function**: `format_report(score_dict: Dict) -> str` ([Lines 9–74](file:///c:/Users/shris/OneDrive/Desktop/UrAi_parser/eval/report.py#L9-L74))
  - Formats pass/fail status, percentages, alignment cost, cell counts, and detailed invariant difference tables.
