"""Streamlit 交互回归：输入状态、导入、错误与结果快照。"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from re4_gems.solver import (
    STATUS_FEASIBLE,
    STATUS_INFEASIBLE,
    STATUS_MODEL_INVALID,
    STATUS_UNKNOWN,
    SolveResult,
)


def app():
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
    at.run(timeout=30)
    assert not at.exception
    return at


def click(at, label):
    next(button for button in at.button if button.label == label).click().run(timeout=30)
    assert not at.exception
    return at


def number(at, key):
    return next(widget for widget in at.number_input if widget.key == key)


def test_example_and_clear_update_actual_widgets():
    at = app()
    click(at, "加载示例")
    assert number(at, "gem_inv_ruby").value == 2
    assert number(at, "gem_inv_yellow_diamond").value == 3
    assert number(at, "treasure_q_flagon").value == 1
    assert number(at, "treasure_q_butterfly_lamp").value == 1

    click(at, "清空")
    assert all(widget.value == 0 for widget in at.number_input)
    assert at.session_state["result"] is None


def test_json_import_is_explicit_and_runs_only_once():
    at = app()
    payload = json.dumps(
        {"gems": {"ruby": 2}, "reserved": {"ruby": 1}, "treasures": {"flagon": 1}}
    ).encode("utf-8")
    at.get("file_uploader")[0].upload("inventory.json", payload, "application/json").run(timeout=30)
    assert number(at, "gem_inv_ruby").value == 0

    click(at, "导入所选 JSON")
    assert number(at, "gem_inv_ruby").value == 2
    assert number(at, "gem_res_ruby").value == 1
    assert number(at, "treasure_q_flagon").value == 1

    number(at, "gem_inv_ruby").set_value(3).run(timeout=30)
    at.run(timeout=30)
    assert not at.exception
    assert number(at, "gem_inv_ruby").value == 3


@pytest.mark.parametrize(
    "payload",
    [
        b'{"gem":{"ruby":2},"treasures":{"flagon":1}}',
        b'{"gems":{"ruby":1e309},"treasures":{}}',
        b'{"gems":{"ruby":NaN},"treasures":{}}',
        '{"gems":{"ruby":2},"treasures":{}}'.encode("utf-16"),
    ],
)
def test_bad_json_preserves_inventory_and_shows_error(payload):
    at = app()
    click(at, "加载示例")
    at.get("file_uploader")[0].upload("bad.json", payload, "application/json").run(timeout=30)
    click(at, "导入所选 JSON")
    assert number(at, "gem_inv_ruby").value == 2
    assert any("导入失败" in item.value for item in at.error)


def test_manual_reservation_above_inventory_rejected():
    at = app()
    number(at, "gem_inv_ruby").set_value(1).run(timeout=30)
    number(at, "gem_res_ruby").set_value(2).run(timeout=30)
    number(at, "treasure_q_flagon").set_value(1).run(timeout=30)
    click(at, "🚀 计算全局最优方案")
    assert any("输入错误" in item.value and "保留" in item.value for item in at.error)
    assert at.session_state["result"] is None
    assert not any(item.label == "总收入" for item in at.metric)


def test_result_hides_when_inputs_change_and_reconciles_reservations():
    at = app()
    number(at, "gem_inv_ruby").set_value(2).run(timeout=30)
    number(at, "gem_res_ruby").set_value(1).run(timeout=30)
    click(at, "🚀 计算全局最优方案")
    assert at.session_state["result"].objective == 3000
    row = at.dataframe[0].value.iloc[0]
    assert row["总库存"] == 2
    assert row["保留数"] == 1
    assert row["镶嵌消耗"] == 0
    assert row["剩余可用"] == 1

    number(at, "gem_inv_ruby").set_value(3).run(timeout=30)
    assert any("重新计算" in item.value for item in at.warning)
    assert not any(item.label == "总收入" for item in at.metric)
    assert at.session_state["result_input"]["gems"][0] == 2


@pytest.mark.parametrize("status", [STATUS_UNKNOWN, STATUS_INFEASIBLE, STATUS_MODEL_INVALID])
def test_no_solution_status_does_not_render_empty_vectors(status):
    at = app()
    fake = SolveResult(status=status, elapsed_seconds=0.25, message="test status")
    with patch("re4_gems.solver.solve", return_value=fake):
        click(at, "🚀 计算全局最优方案")
    assert any("没有可报告" in item.value for item in at.info)
    assert not any(item.label == "总收入" for item in at.metric)
    assert "0.25 秒" in " ".join(item.value for item in at.caption)


def test_feasible_shows_elapsed_time_and_bound():
    at = app()
    fake = SolveResult(
        status=STATUS_FEASIBLE,
        objective_x10=10_000,
        upper_bound_x10=12_000,
        treasure_sale_x10=0,
        gem_sale_x10=10_000,
        consumed_gems=[0] * 6,
        remaining_gems=[0] * 6,
        elapsed_seconds=0.25,
    )
    with patch("re4_gems.solver.solve", return_value=fake):
        click(at, "🚀 计算全局最优方案")
    assert "0.25 秒" in " ".join(item.value for item in at.caption)
    assert any("收入上界" in item.value and "尚未证明最优" in item.value for item in at.info)
