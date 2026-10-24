# Architectural & Engineering Decisions (DECISIONS.md)

This log documents every major technical decision, design rationale, trade-off, and dead end encountered during the development of the Japanese Consolidated Financial Statement Parser.

---

### Decision 1: Evaluation-First Development (TDD for Document Intelligence)
- **Context**: The screening requires building and testing the evaluator *before* trusting the parser.
- **Decision**: Developed `eval/aligner.py`, `eval/scorer.py`, and `data/ground_truth_v0.json` alongside comprehensive corruption tests in `tests/test_evaluator.py` before writing the extraction pipeline.
- **Rationale**: Prevents accidental leakage of evaluation heuristics into parser code, eliminates confirmation bias, and guarantees the metric suite detects subtle regressions (e.g. dropped rows, split/merged lines, transposed digits).

---

### Decision 2: DP Alignment Cost Metric & Circularity Prevention
- **Context**: Ground-truth to predicted row alignment must resolve duplicates without greedy matching or using numerical cell values.
- **Decision**: Implemented an order-preserving dynamic programming alignment (edit-distance style) using:
  1. Character-level normalized label similarity ($1.0 - \text{fuzz.ratio}$).
  2. Section context similarity ($1.0 - \text{Jaccard}(\text{header\_chains})$) with parent match bonus.
  3. Document order drift penalty ($|(i/M) - (j/N)|$).
  4. Cell numbers are explicitly excluded from the alignment cost function.
- **Ambiguity & Ties**: If multiple candidates have tied match costs (within $\epsilon = 10^{-3}$), the match is flagged as `Unresolved` and never forced.
- **Dead End Explored**: Considered using visual y-coordinate proximity directly in the DP cost.
  - *Why rejected*: Page re-layouts, multi-page documents, and different font scale factors break coordinate-based distance between GT and predictions. Relative document order ($i/M$ vs $j/N$) is invariant to DPI and vertical offsets.

---

### Decision 3: Schema Representation for Header Rows vs Data Rows
- **Context**: The prompt schema defines `"cells": {"c1": {"raw": str|null, "status": "present"|"nil"|"unreadable", "value_in_unit": int|null}}`. Header rows (`資産の部`, `流動資産`, etc.) have no data values.
- **Decision**: Set `cells: {}` for rows of `type: "header"`.
- **Rationale**: In Japanese financial balance sheets, section headers span the entire table width as category banners. Creating synthetic `{"c1": {"raw": null, ...}}` entries for header rows would artificially inflate the GT cell count and conflate unreadable data cells with non-existent data cells.

---

### Decision 4: Number and Date Parsing Rules
- **Context**: Cells contain negative signs (`△`, `▲`, `(1,234)`), nil markers (`－`, `-`, `—`), full-width numerals, and Japanese date strings (`2025 年３月 31 日`).
- **Decision**:
  - Implemented pure functions `parse_number` and `normalize_date_to_iso` using NFKC normalization.
  - Special case `"△0"`: Preserves `raw="△0"`, parses `status="present"`, `value_in_unit=0`.
  - Nil markers: Maps `－`, `-`, `—`, `―` to `status="nil"`, `value_in_unit=None`.
  - Unreadable: Missing or malformed data maps to `status="unreadable"`, never using nil to mean "parser gave up".

---

### Decision 5: Typographic Indentation vs Accounting Logic for Hierarchy
- **Context**: The prompt allows visible x-indentation or accounting logic to define `parent_row_idx`.
- **Decision**: Combined typographic indentation-grid geometry with accounting logic:
  - Base x-indentation step was measured at $\approx 12.9\,\text{pt}$ across 5 discrete levels ($L_0=62.3, L_1=75.2, L_2=88.2, L_3=101.3, L_4=114.2$).
  - Preceding stack traversal assigns each row's parent to the enclosing header at level $L-1$.
  - Special accounting exceptions:
    - Contra accounts (`減価償却累計額` at $L_4$): Attached directly to the gross asset immediately above it ($i-1$).
    - Net accounts (`...（純額）` at $L_4$): Attached to the section header ($L_2$/$L_3$), with `derived_from=[i-2, i-1]`.
    - Grand total (`資産合計`): Attached to `資産の部` ($L_0$).

---

### Decision 6: Router Signal Design and Escalation Stub
- **Context**: The router must decide if the native text layer is trustworthy before table parsing.
- **Decision**: Evaluates 3 signals:
  1. Character plausibility: Ratio of valid CJK / digits / Japanese punctuation vs replacement (`\ufffd`) or private-use code points (threshold: 85%).
  2. Word coverage: Minimum word count threshold ($\ge 15$ words).
  3. Table sanity: Count of numeric token candidates ($\ge 5$).
- **Stub Behavior**: If any check fails, routes to `ocr` with explicit diagnosis in `route_reason`. In v1, the OCR backend returns stub metadata rather than fabricating ungrounded predictions.

---

### Decision 7: Handling Invariant Sum Tolerances
- **Context**: Financial filing line items are rounded to thousands of yen (`千円`), causing section sums to differ by $\pm 1$ to $\pm 3$ units from printed totals (e.g. current year 流動資産合計 + 固定資産合計 is 1 unit off from 資産合計; 有形固定資産合計 is 3 units off).
- **Decision**: Parameterized tolerance as $k \times \text{tolerance\_per\_term}$ (where $k$ is number of summed terms and default tolerance is $1\,\text{unit}$). All differences are explicitly reported and never silently suppressed.

---

### Decision 8: Adaptive Column Discovery via 1D Right-Edge Projection
- **Context**: The original parser used hardcoded coordinates (`split_x = 415.0`, `max_label_x = 280.0`). When documents were scaled (0.8x, 1.2x), margins shifted, or had 3 numeric columns, cells were either dropped or assigned to the wrong column.
- **Decision**:
  1. Detect body numeric tokens across table rows.
  2. Project and cluster token right edges ($x_1$) using 1D gap clustering ($> 18\,\text{pt}$). In financial tables, numbers are strictly right-aligned, making right edges invariant to token digit count.
  3. Derive $N$ columns, boundary split dividers between columns, and the label/number gutter ($x_{\text{gutter}}$).
  4. Header text (dates, period labels) is dynamically mapped to detected columns via horizontal mid-point overlap.
- **Dead End Explored**: Tried using token horizontal centers ($(x_0 + x_1)/2$) for clustering.
  - *Why rejected*: Small numbers (e.g. `－` or `235`) have centers far to the right of large numbers (e.g. `12,659,622`), causing center-based clustering to create fake intermediate columns. Right edges align to the column border regardless of string length.

---

### Decision 9: Dynamic Indentation Tier Clustering
- **Context**: The original parser assumed a fixed `indent_step = 12.9 pt`. Other corporate templates (or scaled pages) use 9pt, 10pt, or 20pt offsets, causing parent assignment to collapse.
- **Decision**: Implemented 1D density clustering on label $x_0$ positions with a $3.5\,\text{pt}$ jitter radius. Clusters are sorted into ascending depth tiers ($L_0 < L_1 < \dots < L_k$). Rows are assigned to the nearest tier.
- **Dead End Explored**: Attempted deriving indentation step from the greatest common divisor (GCD) of pairwise differences.
  - *Why rejected*: Minor font kerning and PDF float rounding noise (e.g. $12.92$ vs $13.04$) causes GCD to collapse to $0.1\,\text{pt}$. Gap-based density clustering is robust to noise.
- **Fail Loud Behavior**: If fewer than 2 tiers exist (flat table), the parser flags `hierarchy_unavailable` and sets `parent_row_idx = None` rather than guessing a false hierarchy.

---

### Decision 10: General Suffixes and Dynamic Numeric Lineage
- **Context**: The original parser hardcoded specific account strings (`流動資産合計`, `有形固定資産合計`, etc.) to find `derived_from`.
- **Decision**:
  1. Replaced hardcoded names with general suffixes (`合計`, `小計`, `純額`, `計`) and accounting totals (`資産合計`, `負債及び純資産合計`, `総計`).
  2. Evaluates candidate subsets of preceding leaf items and section subtotals using mathematical sum checks ($|\sum - \text{reported}| \le k \times \text{tolerance}$).
  3. Correctly treats printed nil (`－`, value `None`) as contributing $0$ to accounting sums.
- **Dead End Explored**: Checked `計` as an arbitrary substring.
  - *Why rejected*: `計` appears inside normal non-total words like `減価償却累計額` (accumulated depreciation). Changed to suffix match `endswith("計")`, `小計`, `合計`, or `純額`.

---

### Decision 11: Fail-Loud Diagnostic Protocol (`confidence_flags`)
- **Context**: In live testing or production, a parser must never emit confident wrong data on ambiguous layouts.
- **Decision**: Added root-level `confidence_flags: List[str]` output. Flags include:
  - `column_boundaries_ambiguous`: numeric tokens don't form clear right-edge clusters.
  - `hierarchy_unavailable`: single-tier indentation.
  - `invariants_failed`: domain invariant checks failed (with item names).
  - `escalate_to_ocr`, `text_layer_missing`, `low_char_plausibility`: router flags.
  - `header_or_unit_not_found`: missing metadata.
