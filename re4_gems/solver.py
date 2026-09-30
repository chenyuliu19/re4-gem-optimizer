"""CP-SAT 全局优化求解器。

将整份库存作为一个全局优化问题求解：
- 决策变量 y[t,c]：第 t 类宝物采用第 c 种组合的件数（非负整数）。
- 约束：每类宝物所有组合件数之和 = 该类宝物数量 q[t]。
        每种宝石总消耗 <= 可用数量 A[g]。
- 剩余宝石 L[g] = A[g] - 总消耗。

两种目标模式：
- "total"：最大化 全部宝物售价之和 + 剩余宝石单卖价值。
- "treasure_only"：仅最大化宝物售出价，剩余宝石保留（不计入收入）。

所有金额均放大 10 倍（整数）参与计算。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .combinations import Combination, get_combinations
from .gem_data import GEMS, NUM_GEMS
from .inventory import InventoryError, normalize_gems, normalize_treasures, validate_inventory
from .treasure_data import TREASURES, TREASURE_BY_ID

# 目标模式常量。
MODE_TOTAL = "total"
MODE_TREASURE_ONLY = "treasure_only"

# 状态常量。
STATUS_OPTIMAL = "OPTIMAL"
STATUS_FEASIBLE = "FEASIBLE"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_INFEASIBLE = "INFEASIBLE"
STATUS_MODEL_INVALID = "MODEL_INVALID"

STATUS_TEXT = {
    STATUS_OPTIMAL: "已证明全局最优",
    STATUS_FEASIBLE: "当前可行方案，尚未证明最优",
    STATUS_UNKNOWN: "尚未得到可报告的解，可增加求解时间重试",
    STATUS_INFEASIBLE: "无可行方案",
    STATUS_MODEL_INVALID: "模型无效",
}


@dataclass
class TreasureAssignment:
    """某类宝物的一种镶嵌方案的汇总（同类同方案可合并）。

    Attributes:
        treasure_id: 宝物 ID。
        count: 采用该方案的件数。
        combination: 采用的组合。
    """

    treasure_id: str
    count: int
    combination: Combination


@dataclass
class SolveResult:
    """求解结果。"""

    status: str
    objective_x10: int = 0  # 放大 10 倍的总收入。
    treasure_sale_x10: int = 0  # 放大 10 倍的宝物售出价合计。
    gem_sale_x10: int = 0  # 放大 10 倍的剩余宝石单卖价值。
    assignments: list[TreasureAssignment] = field(default_factory=list)
    remaining_gems: list[int] = field(default_factory=list)  # 六维剩余可用宝石。
    consumed_gems: list[int] = field(default_factory=list)  # 六维镶嵌消耗。
    upper_bound_x10: int = 0  # 收入上界（FEASIBLE 时用于展示差距）。
    elapsed_seconds: float = 0.0
    message: str = ""
    mode: str = MODE_TOTAL

    @property
    def objective(self) -> int:
        """真实总收入（ptas，向下取整恢复单位）。"""
        return self.objective_x10 // 10

    @property
    def treasure_sale(self) -> int:
        return self.treasure_sale_x10 // 10

    @property
    def gem_sale(self) -> int:
        return self.gem_sale_x10 // 10

    @property
    def gap(self) -> float:
        """相对差距（FEASIBLE 时 upper_bound - objective）。"""
        return max(0, self.upper_bound_x10 - self.objective_x10) / 10.0


def solve(
    treasure_counts: dict[str, int],
    gem_inventory: list[int],
    reserved: list[int] | None = None,
    mode: str = MODE_TOTAL,
    time_limit_seconds: float = 30.0,
) -> SolveResult:
    """求解全局最优镶嵌方案。

    Args:
        treasure_counts: treasure_id -> 数量（仅含数量 > 0 的宝物）。
        gem_inventory: 六维宝石库存（Ruby..Red Beryl）。
        reserved: 六维保留数量，默认全 0。
        mode: MODE_TOTAL 或 MODE_TREASURE_ONLY。
        time_limit_seconds: 求解时限（秒）。

    Returns:
        SolveResult。
    """
    if mode not in (MODE_TOTAL, MODE_TREASURE_ONLY):
        raise InventoryError(f"未知优化目标：{mode}。")
    if isinstance(time_limit_seconds, bool) or not isinstance(time_limit_seconds, (int, float)):
        raise InventoryError("求解时限必须是大于 0 的有限秒数。")
    try:
        finite_time_limit = math.isfinite(time_limit_seconds)
    except OverflowError:
        finite_time_limit = False
    if not finite_time_limit or time_limit_seconds <= 0:
        raise InventoryError("求解时限必须是大于 0 的有限秒数。")
    if gem_inventory is None or treasure_counts is None:
        raise InventoryError("请提供宝石库存和宝物库存。")

    # 先复制再校验，避免直接调用者的库存被校验逻辑修改。
    gem_inventory = normalize_gems(gem_inventory, "宝石库存")
    reserved = normalize_gems(reserved, "保留数量")
    treasure_counts = normalize_treasures(treasure_counts)
    validate_inventory(gem_inventory, reserved, treasure_counts)

    start = time.perf_counter()
    deadline = start + time_limit_seconds

    # 可用宝石数量 = 库存 - 保留。
    available = [gem_inventory[i] - reserved[i] for i in range(NUM_GEMS)]

    # 参与建模的宝物（数量 > 0）。
    active_treasures = [
        (TREASURE_BY_ID[tid], q)
        for tid, q in treasure_counts.items()
        if q > 0
    ]

    model = cp_model.CpModel()

    # 决策变量与组合缓存。
    y_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    all_combos: dict[int, list[Combination]] = {}

    for t_idx, (treasure, q) in enumerate(active_treasures):
        combos = get_combinations(treasure, tuple(available))
        all_combos[t_idx] = combos
        for c_idx, combo in enumerate(combos):
            y_vars[(t_idx, c_idx)] = model.NewIntVar(0, q, f"y_{t_idx}_{c_idx}")

    # 约束 1：每类宝物所有组合件数之和 = 该类数量。
    for t_idx, (treasure, q) in enumerate(active_treasures):
        model.Add(sum(y_vars[(t_idx, c_idx)] for c_idx in range(len(all_combos[t_idx]))) == q)

    # 约束 2：每种宝石总消耗 <= 可用数量。
    for g in range(NUM_GEMS):
        total_use = []
        for t_idx, (treasure, q) in enumerate(active_treasures):
            for c_idx, combo in enumerate(all_combos[t_idx]):
                cnt = combo.vector[g]
                if cnt > 0:
                    total_use.append(cnt * y_vars[(t_idx, c_idx)])
        if total_use:
            model.Add(sum(total_use) <= available[g])

    # 目标函数（放大 10 倍整数）。
    treasure_sale_terms = []
    for t_idx, (treasure, q) in enumerate(active_treasures):
        for c_idx, combo in enumerate(all_combos[t_idx]):
            treasure_sale_terms.append(combo.price_x10 * y_vars[(t_idx, c_idx)])
    treasure_sale_expr = sum(treasure_sale_terms)

    if mode == MODE_TOTAL:
        # 剩余宝石单卖价值：Σ gem_price[g] * 10 * L[g]。
        # 直接构造：Σ gem_price*10 * available[g] - Σ gem_price*10 * 消耗[g]。
        # 更稳妥的做法：引入 L[g] 变量。
        L_vars = {}
        for g in range(NUM_GEMS):
            total_use_g = []
            for t_idx, (treasure, q) in enumerate(active_treasures):
                for c_idx, combo in enumerate(all_combos[t_idx]):
                    cnt = combo.vector[g]
                    if cnt > 0:
                        total_use_g.append(cnt * y_vars[(t_idx, c_idx)])
            use_expr = sum(total_use_g) if total_use_g else 0
            L_vars[g] = model.NewIntVar(0, available[g], f"L_{g}")
            model.Add(L_vars[g] == available[g] - use_expr)
        gem_sale_expr = sum(GEMS[g].price * 10 * L_vars[g] for g in range(NUM_GEMS))
        objective = treasure_sale_expr + gem_sale_expr
    else:
        # MODE_TREASURE_ONLY：仅宝物售出价。
        objective = treasure_sale_expr

    model.Maximize(objective)

    solver = cp_model.CpSolver()
    remaining_time = deadline - time.perf_counter()
    if remaining_time <= 0:
        return SolveResult(
            status=STATUS_UNKNOWN,
            elapsed_seconds=time.perf_counter() - start,
            message="建模已用完求解时限。",
            mode=mode,
        )
    solver.parameters.max_time_in_seconds = remaining_time
    solver.parameters.num_workers = 8

    status_code = solver.Solve(model)

    result = SolveResult(status=STATUS_UNKNOWN, mode=mode)

    cp_status = status_code
    if cp_status == cp_model.OPTIMAL:
        result.status = STATUS_OPTIMAL
    elif cp_status == cp_model.FEASIBLE:
        result.status = STATUS_FEASIBLE
    elif cp_status == cp_model.INFEASIBLE:
        result.status = STATUS_INFEASIBLE
    elif cp_status == cp_model.MODEL_INVALID:
        result.status = STATUS_MODEL_INVALID
    else:
        result.status = STATUS_UNKNOWN

    if result.status in (STATUS_OPTIMAL, STATUS_FEASIBLE):
        result.objective_x10 = int(solver.ObjectiveValue())
        result.upper_bound_x10 = int(solver.BestObjectiveBound())

        # 读取解。
        assignments: list[TreasureAssignment] = []
        consumed = [0] * NUM_GEMS
        treasure_sale_total = 0
        for t_idx, (treasure, q) in enumerate(active_treasures):
            for c_idx, combo in enumerate(all_combos[t_idx]):
                cnt = int(solver.Value(y_vars[(t_idx, c_idx)]))
                if cnt > 0:
                    assignments.append(TreasureAssignment(treasure.treasure_id, cnt, combo))
                    treasure_sale_total += combo.price_x10 * cnt
                    for g in range(NUM_GEMS):
                        consumed[g] += combo.vector[g] * cnt

        result.assignments = assignments
        result.consumed_gems = consumed
        result.remaining_gems = [available[g] - consumed[g] for g in range(NUM_GEMS)]
        result.treasure_sale_x10 = treasure_sale_total
        result.gem_sale_x10 = result.objective_x10 - treasure_sale_total
        result.message = solver.StatusName(cp_status)

        # 第二轮：在证明主目标最优后，固定最优收入，优先选择镶嵌颗数较少的方案。
        if result.status == STATUS_OPTIMAL:
            result = _minimize_gems_second_pass(
                model, solver, result, active_treasures, all_combos, y_vars,
                objective, available, deadline,
            )
    else:
        result.message = solver.StatusName(cp_status)

    result.elapsed_seconds = time.perf_counter() - start
    return result


def _minimize_gems_second_pass(
    model, solver, result, active_treasures, all_combos, y_vars,
    objective, available, deadline,
) -> SolveResult:
    """第二轮：固定主目标最优收入，最小化总镶嵌颗数（不降低主目标收入）。"""
    # 固定主目标收入等于已求得最优值。
    model.Add(objective == result.objective_x10)

    # 新目标：最小化总镶嵌宝石颗数。
    gem_use_terms = []
    for t_idx, (treasure, q) in enumerate(active_treasures):
        for c_idx, combo in enumerate(all_combos[t_idx]):
            total_gems = sum(combo.vector)
            if total_gems > 0:
                gem_use_terms.append(total_gems * y_vars[(t_idx, c_idx)])
    model.Minimize(sum(gem_use_terms) if gem_use_terms else 0)

    solver2 = cp_model.CpSolver()
    remaining_time = deadline - time.perf_counter()
    if remaining_time <= 0:
        return result
    solver2.parameters.max_time_in_seconds = remaining_time
    solver2.parameters.num_workers = 8

    status2 = solver2.Solve(model)
    if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # 重新读取解（主目标收入不变）。
        assignments: list[TreasureAssignment] = []
        consumed = [0] * NUM_GEMS
        treasure_sale_total = 0
        for t_idx, (treasure, q) in enumerate(active_treasures):
            for c_idx, combo in enumerate(all_combos[t_idx]):
                cnt = int(solver2.Value(y_vars[(t_idx, c_idx)]))
                if cnt > 0:
                    assignments.append(TreasureAssignment(treasure.treasure_id, cnt, combo))
                    treasure_sale_total += combo.price_x10 * cnt
                    for g in range(NUM_GEMS):
                        consumed[g] += combo.vector[g] * cnt

        result.assignments = assignments
        result.consumed_gems = consumed
        result.remaining_gems = [available[g] - consumed[g] for g in range(NUM_GEMS)]
        result.treasure_sale_x10 = treasure_sale_total
        result.gem_sale_x10 = result.objective_x10 - treasure_sale_total

    return result
