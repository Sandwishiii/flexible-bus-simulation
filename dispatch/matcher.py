"""
二分图匹配算法
KM (Kuhn-Munkres) 算法求解带权二分图最优匹配
"""
import numpy as np
from typing import List, Tuple, Optional
from scipy.optimize import linear_sum_assignment


class BipartiteMatcher:
    def __init__(self, method: str = 'km'):
        assert method in ('km', 'greedy')
        self.method = method

    def match(self, score_matrix: List[List[float]]) -> List[Tuple[int, int, float]]:
        if not score_matrix or not score_matrix[0]:
            return []
        n_vehicles = len(score_matrix)
        n_orders = len(score_matrix[0])
        if self.method == 'km':
            return self._km_match(score_matrix, n_vehicles, n_orders)
        else:
            return self._greedy_match(score_matrix, n_vehicles, n_orders)

    def _km_match(self, score_matrix, n_vehicles, n_orders):
        if n_vehicles * n_orders > 500000:
            return self._greedy_match(score_matrix, n_vehicles, n_orders)
        cost_matrix = -np.array(score_matrix, dtype=np.float64)
        max_dim = max(n_vehicles, n_orders)
        if n_vehicles != n_orders:
            padded = np.full((max_dim, max_dim), 1e6)
            padded[:n_vehicles, :n_orders] = cost_matrix
            cost_matrix = padded
        row_indices, col_indices = linear_sum_assignment(cost_matrix)
        results = []
        for r, c in zip(row_indices, col_indices):
            if r < n_vehicles and c < n_orders:
                score = score_matrix[r][c]
                if score > 0:
                    results.append((r, c, score))
        return results

    def _greedy_match(self, score_matrix, n_vehicles, n_orders):
        matrix = [row[:] for row in score_matrix]
        used_vehicles = set()
        used_orders = set()
        results = []
        while True:
            best_score = -1
            best_i, best_j = -1, -1
            for i in range(n_vehicles):
                if i in used_vehicles:
                    continue
                for j in range(n_orders):
                    if j in used_orders:
                        continue
                    if matrix[i][j] > best_score:
                        best_score = matrix[i][j]
                        best_i, best_j = i, j
            if best_score <= 0 or best_i == -1:
                break
            results.append((best_i, best_j, best_score))
            used_vehicles.add(best_i)
            used_orders.add(best_j)
        return results

    @staticmethod
    def calc_total_score(matches):
        return sum(score for _, _, score in matches)
