"""
Order-preserving dynamic-programming alignment for financial table rows.
Implements edit-distance style DP with match, insert, and delete operations.
Uses normalized label similarity, document order, and section context.
Never uses cell numbers in alignment to prevent circular evaluation.
"""

import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple
from rapidfuzz import fuzz


def normalize_label(text: Optional[str]) -> str:
    """Normalizes label text using NFKC and strips all whitespace."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", str(text))
    return "".join(norm.split())


def get_section_context(rows: List[Dict[str, Any]], idx: int) -> List[str]:
    """
    Extracts the section context (preceding header hierarchy) for a row.
    Walks up the parent chain if available; otherwise uses preceding header rows.
    """
    if idx < 0 or idx >= len(rows):
        return []
    
    row = rows[idx]
    # If parent_row_idx is present and valid
    chain = []
    curr = row.get("parent_row_idx")
    visited = {idx}
    while curr is not None and curr >= 0 and curr < len(rows) and curr not in visited:
        visited.add(curr)
        chain.append(normalize_label(rows[curr].get("label_raw", "")))
        curr = rows[curr].get("parent_row_idx")
    
    if chain:
        return list(reversed(chain))
    
    # Fallback heuristic: find preceding header rows
    headers = []
    for i in range(idx - 1, -1, -1):
        r = rows[i]
        if r.get("type") == "header":
            headers.append(normalize_label(r.get("label_raw", "")))
            if len(headers) >= 3:
                break
    return list(reversed(headers))


def section_similarity(ctx1: List[str], ctx2: List[str]) -> float:
    """Computes similarity between two section context chains."""
    if not ctx1 and not ctx2:
        return 1.0
    if not ctx1 or not ctx2:
        return 0.5  # Neutral penalty if one side lacks context
    
    # Check overlap of normalized headers
    set1, set2 = set(ctx1), set(ctx2)
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    if not union:
        return 1.0
    jaccard = len(intersection) / len(union)
    
    # Immediate parent match bonus
    parent_bonus = 0.5 if (ctx1[-1] == ctx2[-1]) else 0.0
    return min(1.0, 0.5 * jaccard + parent_bonus)


class RowAligner:
    """
    DP Aligner for table rows.
    """
    def __init__(
        self,
        similarity_threshold: float = 0.70,
        delete_cost: float = 1.0,
        insert_cost: float = 1.0,
        section_weight: float = 0.6,
        order_weight: float = 0.3,
    ):
        self.similarity_threshold = similarity_threshold
        self.delete_cost = delete_cost
        self.insert_cost = insert_cost
        self.section_weight = section_weight
        self.order_weight = order_weight

    def match_cost(
        self,
        gt_row: Dict[str, Any],
        gt_idx: int,
        gt_total: int,
        pred_row: Dict[str, Any],
        pred_idx: int,
        pred_total: int,
        gt_ctx: List[str],
        pred_ctx: List[str],
    ) -> Tuple[float, float, bool]:
        """
        Computes match cost between a ground truth row and predicted row.
        Returns: (cost, label_similarity, is_allowed)
        """
        norm_gt = normalize_label(gt_row.get("label_raw", ""))
        norm_pred = normalize_label(pred_row.get("label_raw", ""))
        
        # Character-level similarity via rapidfuzz ratio
        ratio = fuzz.ratio(norm_gt, norm_pred) / 100.0
        
        if ratio < self.similarity_threshold:
            # Not a viable match; cost exceeds insert + delete
            return (self.delete_cost + self.insert_cost + 1.0, ratio, False)
        
        # Section context similarity
        sec_sim = section_similarity(gt_ctx, pred_ctx)
        
        # Document order difference
        pos_gt = gt_idx / max(1, gt_total - 1)
        pos_pred = pred_idx / max(1, pred_total - 1)
        order_diff = abs(pos_gt - pos_pred)
        
        # Base cost from label dissimilarity
        label_cost = 1.0 - ratio
        sec_penalty = (1.0 - sec_sim) * self.section_weight
        order_penalty = order_diff * self.order_weight
        
        total_cost = label_cost + sec_penalty + order_penalty
        return (total_cost, ratio, True)

    def align(
        self,
        gt_rows: List[Dict[str, Any]],
        pred_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Executes order-preserving DP alignment.
        Returns alignment result including:
        - pairings: list of (gt_idx, pred_idx, outcome, cost, label_sim)
        - exact_count, fuzzy_count, unresolved_count, dropped_count, inserted_count
        - total_cost
        - diagnostics: possible merges, splits
        """
        M = len(gt_rows)
        N = len(pred_rows)
        
        if M == 0 and N == 0:
            return {
                "pairings": [],
                "exact": 0, "fuzzy": 0, "unresolved": 0, "dropped": 0, "inserted": 0,
                "total_cost": 0.0,
                "diagnostics": {"splits": [], "merges": []}
            }
        
        # Precompute section contexts
        gt_contexts = [get_section_context(gt_rows, i) for i in range(M)]
        pred_contexts = [get_section_context(pred_rows, j) for j in range(N)]
        
        # DP table: dp[i][j] = (min_cost, operation, prev_i, prev_j)
        # operations: 'M' (match), 'D' (delete GT), 'I' (insert Pred)
        dp = [[0.0] * (N + 1) for _ in range(M + 1)]
        backtrack = [[None] * (N + 1) for _ in range(M + 1)]
        
        for i in range(1, M + 1):
            dp[i][0] = i * self.delete_cost
            backtrack[i][0] = ("D", i - 1, 0)
            
        for j in range(1, N + 1):
            dp[0][j] = j * self.insert_cost
            backtrack[0][j] = ("I", 0, j - 1)
            
        for i in range(1, M + 1):
            for j in range(1, N + 1):
                # Option 1: Delete GT row i-1
                cost_del = dp[i - 1][j] + self.delete_cost
                # Option 2: Insert Pred row j-1
                cost_ins = dp[i][j - 1] + self.insert_cost
                
                # Option 3: Match
                m_cost, ratio, allowed = self.match_cost(
                    gt_rows[i - 1], i - 1, M,
                    pred_rows[j - 1], j - 1, N,
                    gt_contexts[i - 1], pred_contexts[j - 1]
                )
                
                cost_match = dp[i - 1][j - 1] + m_cost if allowed else float("inf")
                
                best_cost = cost_match
                best_op = "M"
                prev_step = (i - 1, j - 1)
                
                if cost_del < best_cost:
                    best_cost = cost_del
                    best_op = "D"
                    prev_step = (i - 1, j)
                if cost_ins < best_cost:
                    best_cost = cost_ins
                    best_op = "I"
                    prev_step = (i, j - 1)
                    
                dp[i][j] = best_cost
                backtrack[i][j] = (best_op, prev_step[0], prev_step[1])
                
        # Traceback to extract operations
        curr_i, curr_j = M, N
        raw_ops = []
        while curr_i > 0 or curr_j > 0:
            info = backtrack[curr_i][curr_j]
            if info is None:
                break
            op, pi, pj = info
            raw_ops.append((op, curr_i, curr_j, pi, pj))
            curr_i, curr_j = pi, pj
            
        raw_ops.reverse()
        
        # Check for ambiguity / unresolved matches (especially repeated labels)
        # Find candidate matches for each GT row to detect ties
        gt_candidates: Dict[int, List[Tuple[int, float]]] = {i: [] for i in range(M)}
        for i in range(M):
            for j in range(N):
                c, r, allowed = self.match_cost(
                    gt_rows[i], i, M,
                    pred_rows[j], j, N,
                    gt_contexts[i], pred_contexts[j]
                )
                if allowed and r >= self.similarity_threshold:
                    gt_candidates[i].append((j, c))
                    
        gt_to_pred: Dict[int, Tuple[int, str, float, float]] = {}
        pred_matched: Set[int] = set()
        
        for op, ci, cj, pi, pj in raw_ops:
            if op == "M":
                g_idx = pi
                p_idx = pj
                norm_g = normalize_label(gt_rows[g_idx].get("label_raw", ""))
                norm_p = normalize_label(pred_rows[p_idx].get("label_raw", ""))
                ratio = fuzz.ratio(norm_g, norm_p) / 100.0
                
                # Check if there is an unresolved tie:
                # multiple candidates with nearly identical match cost (< 1e-3)
                cands = gt_candidates[g_idx]
                if len(cands) > 1:
                    sorted_cands = sorted(cands, key=lambda x: x[1])
                    if abs(sorted_cands[0][1] - sorted_cands[1][1]) < 1e-3 and sorted_cands[0][0] != sorted_cands[1][0]:
                        # Tie remains unresolved! Never force!
                        gt_to_pred[g_idx] = (p_idx, "Unresolved", sorted_cands[0][1], ratio)
                        pred_matched.add(p_idx)
                        continue
                        
                outcome = "Exact" if norm_g == norm_p else "Fuzzy"
                gt_to_pred[g_idx] = (p_idx, outcome, dp[ci][cj] - dp[pi][pj], ratio)
                pred_matched.add(p_idx)
            elif op == "D":
                g_idx = pi
                gt_to_pred[g_idx] = (None, "Dropped", self.delete_cost, 0.0)
                
        # Check predicted rows that were not matched (Inserted)
        inserted_rows = [j for j in range(N) if j not in pred_matched]
        
        # Count outcomes per GT row
        exact_cnt = 0
        fuzzy_cnt = 0
        unres_cnt = 0
        drop_cnt = 0
        
        aligned_pairs = []
        for i in range(M):
            p_idx, outcome, cost, ratio = gt_to_pred.get(i, (None, "Dropped", self.delete_cost, 0.0))
            if outcome == "Exact":
                exact_cnt += 1
            elif outcome == "Fuzzy":
                fuzzy_cnt += 1
            elif outcome == "Unresolved":
                unres_cnt += 1
            else:
                drop_cnt += 1
            aligned_pairs.append({
                "gt_idx": i,
                "pred_idx": p_idx,
                "outcome": outcome,
                "cost": round(cost, 4),
                "label_sim": round(ratio, 4),
            })
            
        # Diagnostics: detect splits and merges
        splits = []
        merges = []
        # A split candidate: 1 GT row whose label matches prefix/substring of 2 consecutive pred rows
        # A merge candidate: 2 GT rows whose combined label matches 1 pred row
        for i in range(M):
            norm_g = normalize_label(gt_rows[i].get("label_raw", ""))
            for j in range(N - 1):
                norm_p1 = normalize_label(pred_rows[j].get("label_raw", ""))
                norm_p2 = normalize_label(pred_rows[j + 1].get("label_raw", ""))
                if norm_g and (norm_p1 + norm_p2) == norm_g:
                    splits.append({"gt_idx": i, "pred_indices": [j, j + 1], "gt_label": norm_g})
                    
        for i in range(M - 1):
            norm_g1 = normalize_label(gt_rows[i].get("label_raw", ""))
            norm_g2 = normalize_label(gt_rows[i + 1].get("label_raw", ""))
            for j in range(N):
                norm_p = normalize_label(pred_rows[j].get("label_raw", ""))
                if norm_p and (norm_g1 + norm_g2) == norm_p:
                    merges.append({"gt_indices": [i, i + 1], "pred_idx": j, "pred_label": norm_p})
                    
        return {
            "pairings": aligned_pairs,
            "inserted_pred_indices": inserted_rows,
            "exact": exact_cnt,
            "fuzzy": fuzzy_cnt,
            "unresolved": unres_cnt,
            "dropped": drop_cnt,
            "inserted": len(inserted_rows),
            "total_cost": round(dp[M][N], 4),
            "diagnostics": {
                "splits": splits,
                "merges": merges,
            }
        }
