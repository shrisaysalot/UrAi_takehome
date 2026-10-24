# Parser Failure Report (BEFORE Adaptive Changes)

Evaluation of the UNTOUCHED parser across the entire test set (original, synthetic variants, and external real PDFs).

| Document | Route / Method | Gate | Alignment Acc | Cell Raw Acc | Parsing Acc | Parent Acc | Invariants | First Failing Layer | Diagnosis / Root Cause |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **original_page4** | `text_layer` | PASSED | 100.0% | 100.0% | 100.0% | 100.0% | PASS | **None (All Passed)** | Perfect match on original layout. |
| **scaled_08x** | `text_layer` | PASSED | 100.0% | 97.3% | 100.0% | 53.5% | PASS | **Layer 2: Extraction** | Cell raw accuracy: 97.3%. Fixed split_x=415 or max_label_x=280 misplaced cell tokens. |
| **scaled_12x** | `text_layer` | PASSED | 100.0% | 50.0% | 100.0% | 100.0% | PASS | **Layer 2: Extraction** | Cell raw accuracy: 50.0%. Fixed split_x=415 or max_label_x=280 misplaced cell tokens. |
| **shifted_margins** | `text_layer` | PASSED | 97.7% | 48.6% | 100.0% | 100.0% | FAIL | **Layer 1: Alignment** | Row recall: 97.7%, Precision: 97.7% |
| **indent_step_20pt** | `text_layer` | PASSED | 100.0% | 67.6% | 100.0% | 90.7% | PASS | **Layer 2: Extraction** | Cell raw accuracy: 67.6%. Fixed split_x=415 or max_label_x=280 misplaced cell tokens. |
| **three_columns** | `text_layer` | **FAILED** | N/A | N/A | N/A | N/A | N/A | **Gate** | Gate failure: Column count mismatch: expected 3, got 2 |
| **scanned_page** | `ocr` | N/A | N/A | N/A | N/A | N/A | N/A | **Router (Escalation)** | Correctly escalated to OCR stub: Escalated to OCR/VLM stub: Low word count (0 words; expected... |
| **garbled_text** | `ocr` | N/A | N/A | N/A | N/A | N/A | N/A | **Router (Escalation)** | Correctly escalated to OCR stub: Escalated to OCR/VLM stub: Low character plausibility (20.0%... |
| **toyota_p8** (no GT) | `text_layer` | N/A | N/A | N/A | N/A | N/A | FAIL (2/2) | **Extraction / Structure** | Extracted 31 rows, 54 numeric cells. Tailored constants (split_x=415, max_label_x=280) misaligned text boundaries. |
| **mhi_p5** (no GT) | `text_layer` | N/A | N/A | N/A | N/A | N/A | PASS | **Extraction / Structure** | Extracted 21 rows, 35 numeric cells. Tailored constants (split_x=415, max_label_x=280) misaligned text boundaries. |
| **mhi_p6** (no GT) | `text_layer` | N/A | N/A | N/A | N/A | N/A | PASS | **Extraction / Structure** | Extracted 28 rows, 47 numeric cells. Tailored constants (split_x=415, max_label_x=280) misaligned text boundaries. |
| **softbank_p33** (no GT) | `text_layer` | N/A | N/A | N/A | N/A | N/A | PASS | **Extraction / Structure** | Extracted 24 rows, 21 numeric cells. Tailored constants (split_x=415, max_label_x=280) misaligned text boundaries. |

## Detailed Root Causes of Untouched Parser Failures

1. **Scaled / Shifted Pages (`scaled_08x`, `scaled_12x`, `shifted_margins`)**:
   - `split_x = 415.0` and `max_label_x = 280.0` are rigid coordinate cutoffs.
   - When a page is scaled by 0.8x, the rightmost column moves from ~520pt to ~416pt, and column 1 moves from ~415pt to ~332pt. `split_x=415` assigns column 1 tokens as column 2, or drops them completely!
   - When a page is shifted by (+50, +40), tokens cross threshold boundaries, corrupting cell raw accuracy.

2. **Indentation Geometry (`indent_step_20pt`)**:
   - `StructureClassifier(indent_step=12.9)` assumes every indentation level is separated by exactly 12.9 pt.
   - At 20.0 pt per level, `int(round((x0 - base_x0) / 12.9))` assigns distorted indentation depths (level 1 becomes level 2, level 2 becomes level 3/4), causing parent hierarchy accuracy to collapse.

3. **3-Column Tables (`three_columns`)**:
   - The untouched parser is hardcoded to partition words into exactly `c1` and `c2` (`if v_tok['x1'] <= split_x: c1 else c2`).
   - In a 3-column table, the third column is either merged into `c2` or lost. Page-level Gate fails because GT expects 3 columns.

4. **Real External Filings (Toyota, MHI, SoftBank)**:
   - Toyota has `小計` and different column centers.
   - MHI Page 6 is `負債及び資本` (Liabilities and Equity). The parser only searches for `資産の部` or `流動資産` and assumes balance sheet = assets only.
   - SoftBank has wide tables and inline category labels.
