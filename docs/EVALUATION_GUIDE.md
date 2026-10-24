# Japanese Financial Table Parser — Evaluation & Scoring Guide (`EVALUATION_GUIDE.md`)

This guide explains the evaluation methodology, metrics, scoring formulas, denominators, error diagnosis taxonomy, and alignment algorithms used by the Japanese Financial Table Parser.

---

## 1. Evaluation Philosophy: Why Naive Metrics Fail

Evaluating document intelligence models on financial tables using naive metrics (such as BLEU, token-level Levenshtein distance, or greedy cell-coordinate matching) is flawed for three key reasons:

1. **Greedy Matching Masking Structural Errors**: If a parser drops a row in the middle of a table, greedy row-by-row matching shifts every subsequent row by 1, penalizing the entire remaining table as 0% even if all remaining rows were extracted perfectly.
2. **Circular Evaluation via Numbers**: If an evaluator uses numeric cell values to align rows (e.g., matching a row because it contains `"2,002,429"`), it creates a circular dependency: **it cannot detect when a parser extracts the wrong number into the right row**.
3. **Repeated Labels & Context Blindness**: In Japanese corporate balance sheets, account names repeat frequently (e.g., `減価償却累計額` appears under buildings, machinery, vehicles, and leases). Without section hierarchy context, string matching cannot determine which `減価償却累計額` is being scored.

To solve this, the parser uses **order-preserving dynamic programming alignment** with strict circularity prevention, followed by a **5-layer cascading evaluation pipeline**.

---

## 2. Order-Preserving Dynamic Programming Alignment

### A. Circularity Prevention Rule
> **Numbers are strictly excluded from the alignment cost function.**
Row alignment is driven solely by:
1. Normalized label character similarity.
2. Section context hierarchy (enclosing category headers).
3. Relative document vertical order drift.

### B. Match Cost Formula
For ground-truth row $i \in [0, M-1]$ and predicted row $j \in [0, N-1]$:

$$\text{cost}(i, j) = (1.0 - \text{ratio}) + w_{\text{sec}} \times (1.0 - \text{sim}_{\text{sec}}) + w_{\text{order}} \times \left|\frac{i}{M-1} - \frac{j}{N-1}\right|$$

Where:
- $\text{ratio} = \frac{\text{fuzz.ratio}(\text{norm\_label}_i, \text{norm\_label}_j)}{100.0}$
- $w_{\text{sec}} = 0.6$ (weight for section context dissimilarity)
- $w_{\text{order}} = 0.3$ (weight for relative document order drift)
- $\text{sim}_{\text{sec}}$: Jaccard similarity between parent header chains + $0.5$ bonus if the immediate parent header matches.
- **Pruning Threshold**: If $\text{ratio} < 0.70$, matching is disallowed (cost $= \infty$).

### C. DP State Transitions & Operations
The alignment matrix `dp[i][j]` computes the minimal cost edit-sequence:
- **Match (`M`)**: `dp[i-1][j-1] + cost(i-1, j-1)`
- **Delete GT Row (`D`, Dropped by parser)**: `dp[i-1][j] + 1.0`
- **Insert Pred Row (`I`, Hallucinated / Extra row)**: `dp[i][j-1] + 1.0`

### D. Tie Handling & Unresolved Outcomes
When multiple candidate predicted rows have nearly identical match costs ($|\text{cost}_1 - \text{cost}_2| < 10^{-3}$), common with repeated labels:
- **The evaluator never arbitrarily forces a match.**
- The outcome is classified as `Unresolved`.
- Unresolved rows **count as errors in both recall and precision**.

---

## 3. The 5-Layer Cascading Metrics & Exact Denominators

Evaluation progresses through five strict layers. **Each layer evaluates only surviving inputs from the previous layer.**

```
Page Gate (Table & Column Count)
   │
   ├── Layer 1: Row Alignment (Recall, Precision, Exact Label Acc)
   │      │
   │      └── Layer 2: Cell Extraction (Raw string match over ALL GT data cells)
   │             │
   │             └── Layer 3: Value Parsing (Status & Value Acc on confirmed cells)
   │                    │
   │                    └── Layer 4: Structure (Type & Parent Acc on confirmed rows)
   │
   └── Layer 5: Accounting Invariants (GT-Independent mathematical checks)
```

### Layer 0: Page-Level Gate
- **Condition**: Predicted document must contain at least one table, and its column count must match ground truth.
- **Behavior on Failure**: Halts all downstream scoring. Recall and precision are set to 0.

### Layer 1: Row Alignment
- **Confirmed Rows**: Sum of `Exact` and `Fuzzy` matched rows.
  - `Exact`: Normalized GT label $==$ normalized predicted label.
  - `Fuzzy`: Match cost acceptable, but character similarity $\in [0.70, 1.0)$.
- **Dropped Rows**: GT rows with operation `D` (missing in prediction).
- **Inserted Rows**: Predicted rows with operation `I` (spurious extra rows).
- **Unresolved Rows**: Ties with multiple candidate matches.
- **Row Recall**:
  $$\text{Recall} = \frac{\text{Confirmed Rows}}{M} = \frac{\text{Exact} + \text{Fuzzy}}{M}$$
- **Row Precision**:
  $$\text{Precision} = \frac{\text{Confirmed Rows}}{N} = \frac{\text{Exact} + \text{Fuzzy}}{N}$$
- **Exact Label Accuracy**:
  $$\text{Exact Label Acc} = \frac{\text{Exact Rows}}{\text{Confirmed Rows}}$$

### Layer 2: Cell Extraction (Raw Text Match)
- **Scored Over**: **All ground-truth data cells** (cells on rows of type `item` or `subtotal`).
- **Denominator**: Total GT data cells ($N_{\text{gt\_cells}}$).
  - *Critical Rule*: If a row is dropped or unresolved in Layer 1, all of its cells are scored as **extraction errors**.
- **Raw Cell Accuracy**:
  $$\text{Cell Raw Acc} = \frac{\sum_{i \in \text{Confirmed}} \sum_{c \in \text{Cols}} \mathbb{I}(\text{pred\_raw}_{i,c} == \text{gt\_raw}_{i,c})}{N_{\text{gt\_cells}}}$$

### Layer 3: Value Parsing
- **Scored Over**: Eligible cells (confirmed rows whose raw cell text matched GT exactly).
- **Denominator**: $N_{\text{eligible\_cells}}$.
- **Status Accuracy**:
  $$\text{Status Acc} = \frac{\sum_{e} \mathbb{I}(\text{pred\_status}_e == \text{gt\_status}_e)}{N_{\text{eligible\_cells}}}$$
- **Value Accuracy**:
  $$\text{Value Acc} = \frac{\sum_{e} \mathbb{I}(\text{pred\_val}_e == \text{gt\_val}_e)}{N_{\text{eligible\_cells}}}$$
- **Full Parsing Accuracy**: Both status and `value_in_unit` match GT.

### Layer 4: Structure & Hierarchy
- **Scored Over**: Confirmed rows from Layer 1.
- **Denominator**: $N_{\text{confirmed\_rows}}$.
- **Header-vs-Item Accuracy**:
  - Compares whether both GT and prediction agree on whether the row is a category header (`type == "header"`) vs a data row (`type != "header"`).
- **Subtotal/Total Accuracy**:
  - For rows that are subtotals or totals in either GT or prediction, evaluates exact type agreement (`type == "subtotal"` vs `type == "total"`).
- **Parent Chain Accuracy**:
  - Compares predicted `parent_row_idx` mapped into GT index space against the ground-truth `parent_row_idx`.

### Layer 5: Accounting Invariants (Ground-Truth Independent)
Evaluates domain identities directly on the parsed table:
1. **Balance Sheet Identity**:
   $$|\text{流動資産合計} + \text{固定資産合計} - \text{資産合計}| \le 2 \times \text{tolerance\_per\_term}$$
2. **Net Asset Identies**:
   $$|(\text{Gross Asset} - |\text{Contra Asset}|) - \text{Net Asset}| \le 2 \times \text{tolerance\_per\_term}$$
3. **Section Item Sums**:
   $$\left|\sum_{k \in \text{derived\_from}} \text{Item}_k - \text{Reported Subtotal}\right| \le (\#\text{Items}) \times \text{tolerance\_per\_term}$$

---

## 4. Error Diagnosis Taxonomy (Cases A–E)

This taxonomy explains how to locate and isolate bugs across the pipeline:

| Failure Case | Symptoms in Metrics & Logs | Functions to Inspect | Diagnosis & Immediate Fix |
| :--- | :--- | :--- | :--- |
| **Case A: Extraction Failure**<br>(PDF has `1,234`, extracted `1,23`) | Layer 2 Raw Cell Accuracy drops.<br>Raw mismatch reported in `diff`. | `src/extractor.py:extract_page_elements`<br>`src/row_clustering.py:cluster_rows` | Word token bounding box was clipped or trailing digit fell into the next column divider (`col_splits`). Inspect word bounding boxes returned by PyMuPDF. |
| **Case B: Number Interpretation Failure**<br>(PDF has `△1,234`, raw is correct, but value is `+1234`) | Layer 2 Raw Cell matches 100%.<br>Layer 3 Value Accuracy drops.<br>Layer 5 Net Invariant fails. | `src/number_parser.py:parse_number` | Unicode normalization issue with triangle marker (e.g. non-standard font encoding where `△` is not codepoint `0x25B3`). Check regex in `parse_number`. |
| **Case C: Layout Assignment Failure**<br>(Values assigned to wrong column or merged into label) | Layer 2 Raw Cell drops.<br>Values appear in `c2` instead of `c1`. | `src/row_clustering.py:detect_columns_and_gutter`<br>`src/row_clustering.py:cluster_rows` | Gutter threshold $x_{\text{gutter}}$ or column split divider `col_splits` was misplaced. Inspect `out/page4.json` `confidence_flags` for `column_boundaries_ambiguous`. |
| **Case D: Hierarchy Inference Failure**<br>(Labels/values correct, but row has wrong parent or type) | Layers 1, 2, 3 are 100%.<br>Layer 4 Parent Chain Accuracy drops. | `src/structure.py:classify_and_link` | Indentation tier clustering misclassified the depth level. Check `label_x0` clustering centers or `header_stack` traversal. |
| **Case E: Alignment Uncertainty**<br>(Tied match costs on repeated labels) | Layer 1 logs `Unresolved Rows > 0`.<br>Recall & Precision drop proportionally. | `eval/aligner.py:match_cost`<br>`eval/aligner.py:align` | Preceding section context strings between GT and prediction diverged. Check if preceding category header row was dropped. |

---

## 5. Worked Example with Manual Metric Calculations

Consider a small 4-row financial table evaluated against ground truth:

### Ground Truth Table ($M = 4$ rows, 2 data columns $c_1, c_2 \rightarrow 6$ total data cells):
- Row 0: `有形固定資産` (type: `header`, parent: `None`, cells: `{}`)
- Row 1: `建物` (type: `item`, parent: `0`, cells: `c1="100" (100)`, `c2="200" (200)`)
- Row 2: `減価償却累計額` (type: `item`, parent: `1`, cells: `c1="△20" (-20)`, `c2="△40" (-40)`)
- Row 3: `建物（純額）` (type: `subtotal`, parent: `0`, cells: `c1="80" (80)`, `c2="160" (160)`)

### Parser Prediction ($N = 4$ rows):
- Row 0: `有形固定資産` (type: `header`, parent: `None`, cells: `{}`)
- Row 1: `建物` (type: `item`, parent: `0`, cells: `c1="100" (100)`, `c2="200" (200)`)
- Row 2: `減価償却累計額` (type: `item`, parent: `1`, cells: `c1="△20" (20)` $\leftarrow$ **parsing sign error**, `c2="△40" (-40)`)
- Row 3: `建物（純額）` (type: `subtotal`, parent: `1` $\leftarrow$ **wrong parent**, cells: `c1="80" (80)`, `c2="160" (160)`)

---

### Step-by-Step Metric Computation:

1. **Page-Level Gate**:
   - Pred tables = 1, cols = 2 $\rightarrow$ **PASSED**.
2. **Layer 1: Row Alignment**:
   - Row 0: Exact match (cost: 0.0)
   - Row 1: Exact match (cost: 0.0)
   - Row 2: Exact match (cost: 0.0)
   - Row 3: Exact match (cost: 0.0)
   - Outcomes: Exact = 4, Fuzzy = 0, Dropped = 0, Inserted = 0, Unresolved = 0.
   - $\text{Recall} = \frac{4}{4} = 100.0\%$. $\text{Precision} = \frac{4}{4} = 100.0\%$. Exact Label Acc = $\frac{4}{4} = 100.0\%$.
3. **Layer 2: Cell Extraction**:
   - Total GT Data Cells = 6 (Rows 1, 2, 3 $\times$ 2 cols).
   - Raw string comparisons:
     - Row 1: `c1`: `"100"` == `"100"`, `c2`: `"200"` == `"200"` (2 matches)
     - Row 2: `c1`: `"△20"` == `"△20"`, `c2`: `"△40"` == `"△40"` (2 matches)
     - Row 3: `c1`: `"80"` == `"80"`, `c2`: `"160"` == `"160"` (2 matches)
   - Matched raw cells = 6.
   - $\text{Cell Raw Acc} = \frac{6}{6} = 100.0\%$.
4. **Layer 3: Value Parsing**:
   - Denominator = 6 eligible cells.
   - Row 2 `c1` parsed as `+20` instead of `-20` (Value error).
   - Matched values = 5.
   - $\text{Value Acc} = \frac{5}{6} = 83.33\%$.
5. **Layer 4: Structure & Hierarchy**:
   - Denominator = 4 confirmed rows.
   - Header-vs-Item: 4/4 correct ($100.0\%$).
   - Subtotal/Total: 4/4 correct ($100.0\%$).
   - Parent Chain: Row 3 predicted parent is `1`, GT parent is `0` (Mismatch). Rows 0, 1, 2 correct (3 matches).
   - $\text{Parent Chain Acc} = \frac{3}{4} = 75.00\%$.
6. **Layer 5: Invariants**:
   - Check Net Asset on Row 3 `c1`:
     - Reported Net: 80.
     - Calculated from pred: $100 + 20 = 120$ (since contra was positive 20).
     - Difference: $|120 - 80| = 40 > \text{tolerance} (2)$ $\rightarrow$ **FAIL**.

---

## 6. Self-Testing & Corrupted Fixture Tests

The evaluation pipeline includes regression tests in `tests/test_evaluator.py` that deliberately corrupt ground-truth fixtures:
1. `test_evaluator_perfect_match`: Verifies that scoring GT against itself yields 100.0% on all layers and 0.0000 alignment cost.
2. `test_evaluator_drop_row`: Drops `電子記録債権` $\rightarrow$ verifies that evaluator flags `dropped == 1` and drops recall and cell raw accuracy proportionally.
3. `test_evaluator_merge_two_rows`: Merges `受取手形` and `売掛金` $\rightarrow$ verifies that evaluator logs diagnostic merge.
4. `test_evaluator_swap_digits_in_number`: Swaps last two digits in `現金及び預金` $\rightarrow$ verifies that raw extraction fails and invariant detects the discrepancy.
5. `test_evaluator_change_label_slightly`: Introduces near-miss typo $\rightarrow$ flags fuzzy match.
6. `test_evaluator_gate_column_mismatch`: Tests gate halt when column count differs.
