"""求解入口、库存导入和独立核验的回归测试。"""

import copy
from dataclasses import replace
import math
import time

import pytest

from re4_gems.brute_force import brute_force_total, verify_solution
from re4_gems.inventory import InventoryError, inventory_from_dict, inventory_from_json
from re4_gems.solver import MODE_TREASURE_ONLY, solve


EMPTY_GEMS = [0] * 6


@pytest.mark.parametrize(
    "changes",
    [
        {"treasure_counts": {"not_a_treasure": 0}},
        {"treasure_counts": {"flagon": -1}},
        {"treasure_counts": {"flagon": 1.9}},
        {"treasure_counts": {"flagon": True}},
        {"gem_inventory": [-1, 0, 0, 0, 0, 0]},
        {"gem_inventory": [1.9, 0, 0, 0, 0, 0]},
        {"gem_inventory": [1.0, 0, 0, 0, 0, 0]},
        {"gem_inventory": [0] * 5},
        {"gem_inventory": {"not_a_gem": 1}},
        {"reserved": [-1, 0, 0, 0, 0, 0]},
        {"reserved": [1, 0, 0, 0, 0, 0]},
        {"reserved": [0] * 5},
        {"mode": "unknown"},
        {"time_limit_seconds": 0},
        {"time_limit_seconds": -1},
        {"time_limit_seconds": math.nan},
        {"time_limit_seconds": math.inf},
        {"time_limit_seconds": 10**400},
        {"time_limit_seconds": "30"},
        {"time_limit_seconds": True},
    ],
)
def test_solver_rejects_invalid_inputs(changes):
    args = {
        "treasure_counts": {"flagon": 1},
        "gem_inventory": EMPTY_GEMS,
        "reserved": EMPTY_GEMS,
        "time_limit_seconds": 1,
    }
    args.update(changes)
    with pytest.raises(InventoryError):
        solve(**args)


def test_solver_does_not_mutate_input_inventory():
    gems = [2, 0, 0, 0, 0, 0]
    kept = [1, 0, 0, 0, 0, 0]
    treasures = {"flagon": 1, "elegant_crown": 0}
    solve(treasures, gems, kept, time_limit_seconds=1)
    assert gems == [2, 0, 0, 0, 0, 0]
    assert kept == [1, 0, 0, 0, 0, 0]
    assert treasures == {"flagon": 1, "elegant_crown": 0}


@pytest.mark.parametrize(
    "content",
    [
        b'{"gem":{"ruby":2},"treasures":{"flagon":1}}',
        b'{"gems":{}}',
        b'{"gems":null,"treasures":{}}',
        b'{"gems":{"unknown":1},"treasures":{}}',
        b'{"gems":{"ruby":1e309},"treasures":{}}',
        b'{"gems":{"ruby":NaN},"treasures":{}}',
        b'{"gems":{"ruby":Infinity},"treasures":{}}',
        b'{"gems":{"ruby":1.0},"treasures":{}}',
        b'{"gems":{"ruby":1},"reserved":{"ruby":2},"treasures":{}}',
        '{"gems":{},"treasures":{}}'.encode("utf-16"),
        b'{"gems": ',
    ],
)
def test_import_bad_json_reports_inventory_error(content):
    with pytest.raises(InventoryError):
        inventory_from_json(content)


def test_import_valid_utf8_bom_and_direct_nonfinite():
    gems, reserved, treasures = inventory_from_json(
        b'\xef\xbb\xbf{"gems":{"ruby":2},"reserved":{"ruby":1},"treasures":{"flagon":1}}'
    )
    assert gems == [2, 0, 0, 0, 0, 0]
    assert reserved == [1, 0, 0, 0, 0, 0]
    assert treasures == {"flagon": 1}
    with pytest.raises(InventoryError):
        inventory_from_dict({"gems": {"ruby": math.inf}, "treasures": {}})


def test_brute_force_is_independent_of_production_combination_enumerator(monkeypatch):
    import re4_gems.combinations as production_combinations

    def forbidden(*args, **kwargs):
        raise AssertionError("暴力对照不应调用生产组合枚举")

    monkeypatch.setattr(production_combinations, "get_combinations", forbidden)
    assert brute_force_total({"flagon": 1}, [2, 0, 0, 0, 0, 0]) == 120000


def test_verify_rejects_wrong_shape_price_and_remaining():
    gems = [2, 0, 0, 0, 0, 0]
    result = solve({"flagon": 1}, gems, time_limit_seconds=1)
    assert verify_solution({"flagon": 1}, gems, EMPTY_GEMS, result) == (True, "OK")

    wrong_shape = copy.deepcopy(result)
    assignment = wrong_shape.assignments[0]
    assignment.combination = replace(assignment.combination, vector=(0, 0, 0, 1, 0, 0))
    assert not verify_solution({"flagon": 1}, gems, EMPTY_GEMS, wrong_shape)[0]

    wrong_price = copy.deepcopy(result)
    assignment = wrong_price.assignments[0]
    assignment.combination = replace(assignment.combination, price_x10=9999990)
    assert not verify_solution({"flagon": 1}, gems, EMPTY_GEMS, wrong_price)[0]

    wrong_remaining = copy.deepcopy(result)
    wrong_remaining.remaining_gems[0] += 1
    assert not verify_solution({"flagon": 1}, gems, EMPTY_GEMS, wrong_remaining)[0]


def test_treasure_only_matches_independent_reference():
    treasures = {"flagon": 2, "butterfly_lamp": 1}
    gems = [2, 1, 1, 0, 0, 0]
    result = solve(treasures, gems, mode=MODE_TREASURE_ONLY, time_limit_seconds=5)
    assert result.status == "OPTIMAL"
    assert result.objective_x10 == brute_force_total(treasures, gems, mode=MODE_TREASURE_ONLY)
    assert verify_solution(treasures, gems, EMPTY_GEMS, result) == (True, "OK")


def test_elapsed_includes_second_pass(monkeypatch):
    import re4_gems.solver as solver_module

    def delayed_second_pass(model, solver, result, active, combos, variables, objective, available, deadline):
        assert 0 < deadline - time.perf_counter() < 1
        time.sleep(0.03)
        return result

    monkeypatch.setattr(solver_module, "_minimize_gems_second_pass", delayed_second_pass)
    result = solve({}, EMPTY_GEMS, time_limit_seconds=1)
    assert result.status == "OPTIMAL"
    assert result.elapsed_seconds >= 0.03


def test_second_pass_skips_when_global_deadline_has_expired(monkeypatch):
    import re4_gems.solver as solver_module
    from ortools.sat.python import cp_model

    class MustNotSolve:
        def __init__(self):
            self.parameters = type("Parameters", (), {})()

        def Solve(self, model):
            pytest.fail("第二轮不应在全局截止时间后求解")

    monkeypatch.setattr(solver_module.cp_model, "CpSolver", MustNotSolve)
    result = solver_module.SolveResult(status="OPTIMAL")
    returned = solver_module._minimize_gems_second_pass(
        cp_model.CpModel(), None, result, [], {}, {}, 0, EMPTY_GEMS,
        time.perf_counter() - 1,
    )
    assert returned is result
