"""桌面版关键逻辑测试。

重点测试不依赖 GUI 事件循环的纯逻辑，以及可在无显示环境下实例化的组件：
- 数量解析（拒绝负数/小数/超限，空串视为 0）。
- 数量控件加减与非法回退（输入 5 后误输非法内容回退到 5）。
- 结果分组（同款不同方案分别显示）。
- 剩余宝石文本。
- 两种优化模式（出售/保留）的目标差异。
- 输入或模式变化后旧结果失效。
- 通过 solve 的示例验证 49800。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from desktop_app import (
    _gems_text,
    _parse_qty,
    DesktopApp,
    QuantityControl,
)
from re4_gems.gem_data import GEMS, GEM_BY_ID
from re4_gems.solver import MODE_TOTAL, MODE_TREASURE_ONLY, solve


# ---------- 数量解析 ----------

@pytest.mark.parametrize("raw,expected", [
    ("", 0),          # 空串 -> 0
    ("0", 0),
    ("5", 5),
    ("  7  ", 7),     # 首尾空白
    ("9999", 9999),   # 上限允许
])
def test_parse_qty_valid(raw, expected):
    assert _parse_qty(raw, "测试") == expected


@pytest.mark.parametrize("raw", [
    "-1",             # 负数
    "3.5",            # 小数
    "1.0",            # 小数（整数形态）
    "+3",             # 正号
    "abc",            # 非数字
    "3 4",            # 中间空格
    "1e3",            # 科学计数
    "10000",          # 超上限
    "３",             # 全角数字
    "1,000",          # 千分位
])
def test_parse_qty_invalid(raw):
    assert _parse_qty(raw, "测试") is None


# ---------- 宝石文本 ----------

def test_gems_text():
    vec = [0] * len(GEMS)
    idx = list(GEM_BY_ID.keys())
    vec[idx.index("ruby")] = 2
    vec[idx.index("yellow_diamond")] = 1
    text = _gems_text(tuple(vec))
    assert "红宝石×2" in text
    assert "黄钻石×1" in text


def test_gems_text_empty():
    text = _gems_text(tuple([0] * len(GEMS)))
    assert "留空" in text


# ---------- Tk 环境 ----------

@pytest.fixture(scope="module")
def app_root():
    """共享一个 Tk root，避免多 root 导致的 PhotoImage 生命周期问题。"""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # 不显示窗口
    yield root
    root.destroy()


@pytest.fixture()
def app(app_root):
    return DesktopApp(app_root)


# ---------- 结果分组 ----------

def test_group_assignments_diff_scheme(app):
    result = solve(
        {"flagon": 2},
        _gem_inventory(ruby=2, sapphire=2),
        mode=MODE_TOTAL,
        time_limit_seconds=30.0,
    )
    app.result_snapshot = {"gems": _gem_inventory(ruby=2, sapphire=2), "treasures": {"flagon": 2}}
    views = app._group_assignments(result)
    assert len(views) == 2
    total_count = sum(v.count for v in views)
    assert total_count == 2


def test_group_assignments_same_scheme_merged(app):
    result = solve(
        {"flagon": 2},
        _gem_inventory(ruby=4),
        mode=MODE_TOTAL,
        time_limit_seconds=30.0,
    )
    app.result_snapshot = {"gems": _gem_inventory(ruby=4), "treasures": {"flagon": 2}}
    views = app._group_assignments(result)
    assert len(views) == 1
    assert views[0].count == 2


def test_remaining_text(app):
    result = solve(
        {"flagon": 1, "butterfly_lamp": 1},
        _gem_inventory(ruby=2, yellow_diamond=3),
        mode=MODE_TOTAL,
        time_limit_seconds=30.0,
    )
    app.result_snapshot = {"gems": _gem_inventory(ruby=2, yellow_diamond=3),
                           "treasures": {"flagon": 1, "butterfly_lamp": 1}}
    text = app._remaining_text(result)
    assert "无剩余宝石" in text or "已用完" in text


# ---------- 示例：49800 ----------

def test_desktop_example_49800():
    result = solve(
        {"flagon": 1, "butterfly_lamp": 1},
        _gem_inventory(ruby=2, yellow_diamond=3),
        reserved=[0] * len(GEMS),
        mode=MODE_TOTAL,
        time_limit_seconds=30.0,
    )
    assert result.status == "OPTIMAL"
    assert result.objective == 49800


# ---------- 两种模式 ----------

def test_mode_total_counts_gem_sale():
    """出售模式：只有红宝石 1、没有宝物，收入 = 3000（单卖）。"""
    result = solve(
        {},
        _gem_inventory(ruby=1),
        reserved=[0] * len(GEMS),
        mode=MODE_TOTAL,
        time_limit_seconds=30.0,
    )
    assert result.objective == 3000
    assert result.gem_sale == 3000
    assert result.remaining_gems[list(GEM_BY_ID.keys()).index("ruby")] == 1


def test_mode_treasure_only_keeps_gems():
    """保留模式：只有红宝石 1、没有宝物，宝物收入 0，红宝石仍剩余 1。"""
    result = solve(
        {},
        _gem_inventory(ruby=1),
        reserved=[0] * len(GEMS),
        mode=MODE_TREASURE_ONLY,
        time_limit_seconds=30.0,
    )
    assert result.objective == 0
    assert result.treasure_sale == 0
    assert result.remaining_gems[list(GEM_BY_ID.keys()).index("ruby")] == 1


def test_mode_switch_invalidates_result(app):
    """切换模式后旧结果失效。"""
    app.gem_vars[0].set("2")
    app.treasure_vars["flagon"].set("1")
    app.mode_var.set(MODE_TOTAL)
    # 直接构造一个结果快照模拟已有结果。
    app.result = object()
    app.result_snapshot = {"gems": [2] + [0] * 5, "treasures": {"flagon": 1}, "mode": MODE_TOTAL}
    app._dirty = False
    # 切换模式。
    app.mode_var.set(MODE_TREASURE_ONLY)
    app._on_mode_change()
    assert app.result is None
    assert app.result_snapshot is None


def test_qty_change_invalidates_result(app):
    """修改数量后旧结果失效。"""
    app.result = object()
    app.result_snapshot = {"gems": [0] * 6, "treasures": {}}
    app._dirty = False
    app._mark_dirty()
    assert app.result is None
    assert app.result_snapshot is None


# ---------- 数量控件（加减 / 边界 / 非法回退） ----------

def test_quantity_control_minus_clamped_at_zero(app_root):
    var = __import__("tkinter").StringVar(value="0")
    ctrl = QuantityControl(app_root, var, _FakeApp(), "测试")
    ctrl._on_minus()
    assert ctrl._current() == 0  # 0 不能再减


def test_quantity_control_plus_clamped_at_max(app_root):
    import tkinter as tk
    var = tk.StringVar(value="9999")
    ctrl = QuantityControl(app_root, var, _FakeApp(), "测试")
    ctrl._on_plus()
    assert ctrl._current() == 9999  # 9999 不能再加


def test_quantity_control_plus_from_typed(app_root):
    import tkinter as tk
    var = tk.StringVar(value="0")
    ctrl = QuantityControl(app_root, var, _FakeApp(), "测试")
    # 手输数字后点击 +
    var.set("5")
    ctrl._last_valid = 5
    ctrl._on_plus()
    assert ctrl._current() == 6


def test_quantity_control_revert_to_last_valid(app_root):
    """输入 5 后误输非法字符，应回退到 5（而非 0）。"""
    import tkinter as tk
    var = tk.StringVar(value="5")
    ctrl = QuantityControl(app_root, var, _FakeApp(), "测试")
    ctrl._last_valid = 5
    # 模拟非法输入。
    var.set("5x")
    ctrl._on_change()  # 触发校验，内部 after_idle 回退
    # 手动执行回退逻辑（after_idle 在无事件循环下不触发）。
    ctrl._revert_invalid("5x")
    assert var.get() == "5"
    assert ctrl._last_valid == 5


def test_quantity_control_reject_negative(app_root):
    import tkinter as tk
    var = tk.StringVar(value="3")
    ctrl = QuantityControl(app_root, var, _FakeApp(), "测试")
    ctrl._last_valid = 3
    var.set("-1")
    ctrl._revert_invalid("-1")
    assert var.get() == "3"


def _FakeApp():
    class _App:
        def _mark_dirty(self):
            pass
        def _show_input_error(self, msg):
            pass
    return _App()


# ---------- 重复点击与求解状态 ----------

def test_repeat_click_ignored_while_solving(app):
    app.gem_vars[0].set("2")
    app.treasure_vars["flagon"].set("1")
    app._solving = True
    before = app._solve_token
    app.on_generate()
    assert app._solve_token == before


def test_solve_status_unknown_not_rendered_as_optimal(app):
    from re4_gems.solver import STATUS_UNKNOWN, STATUS_INFEASIBLE, STATUS_MODEL_INVALID, SolveResult
    for status in (STATUS_UNKNOWN, STATUS_INFEASIBLE, STATUS_MODEL_INVALID):
        fake = SolveResult(status=status, message="测试状态")
        app.result = fake
        app.result_snapshot = {"gems": [0] * 6, "treasures": {}, "mode": MODE_TOTAL}
        app._render_result(fake, app.result_snapshot)
        assert "无法给出方案" in app.result_title.cget("text")


def test_solve_status_feasible_shows_not_optimal(app):
    from re4_gems.solver import STATUS_FEASIBLE, SolveResult
    fake = SolveResult(
        status=STATUS_FEASIBLE,
        objective_x10=10000,
        upper_bound_x10=12000,
        treasure_sale_x10=0,
        gem_sale_x10=10000,
        consumed_gems=[0] * 6,
        remaining_gems=[0] * 6,
        elapsed_seconds=0.25,
    )
    app.result = fake
    app.result_snapshot = {"gems": [0] * 6, "treasures": {}, "mode": MODE_TOTAL}
    app._render_result(fake, app.result_snapshot)
    text = app.result_title.cget("text")
    assert "尚未证明最优" in text
    assert "已证明全局最优" not in text


def test_optimal_shows_proved(app):
    from re4_gems.solver import STATUS_OPTIMAL, SolveResult
    fake = SolveResult(
        status=STATUS_OPTIMAL,
        objective_x10=498000,
        treasure_sale_x10=498000,
        gem_sale_x10=0,
        consumed_gems=[2, 0, 3, 0, 0, 0],
        remaining_gems=[0, 0, 0, 0, 0, 0],
        elapsed_seconds=0.1,
    )
    app.result = fake
    app.result_snapshot = {"gems": [2, 0, 3, 0, 0, 0],
                           "treasures": {"flagon": 1, "butterfly_lamp": 1}, "mode": MODE_TOTAL}
    app._render_result(fake, app.result_snapshot)
    assert "已证明全局最优" in app.result_title.cget("text")


# ---------- 布局 ----------

def test_layout_has_fixed_left_and_scrollable_right(app):
    """左栏常驻，只有宝物列表和下方结果各自滚动。"""
    assert app.left_panel.grid_info()["column"] == 0
    assert app.right_panel.grid_info()["column"] == 1
    assert app.input_pane.grid_info()["row"] == 0
    assert app.result_pane.grid_info()["row"] == 1
    assert hasattr(app, "treasure_frame")
    assert hasattr(app, "treasure_scrollbar")
    assert not hasattr(app, "input_canvas")
    assert hasattr(app, "result_frame")
    assert hasattr(app, "result_title")


def test_initial_layout_keeps_left_controls_visible(app_root):
    """实际布局后右栏更宽，结果区较矮，左栏末尾的按钮仍露出。"""
    for child in app_root.winfo_children():
        child.destroy()
    app_root.deiconify()
    try:
        app = DesktopApp(app_root)
        app_root.update()
        assert app.right_panel.winfo_width() > app.left_panel.winfo_width()
        assert 190 <= app.result_pane.winfo_height() <= 320
        button_bottom = app.status_label.winfo_rooty() + app.status_label.winfo_height()
        assert button_bottom <= app.result_pane.winfo_rooty()
        app.treasure_canvas.yview_moveto(0)
        first_image = app.treasure_frame.winfo_children()[0].winfo_children()[0]
        first_image.event_generate("<MouseWheel>", delta=-120)
        app_root.update()
        assert app.treasure_canvas.yview()[0] > 0
    finally:
        for child in app_root.winfo_children():
            child.destroy()
        app_root.withdraw()


@pytest.mark.parametrize("screen_height", [768, 900, 1120])
def test_left_controls_fit_on_different_screen_heights(app_root, monkeypatch, screen_height):
    """小屏和普通屏首次打开时，生成按钮与状态文字都应露在结果区上方。"""
    monkeypatch.setattr(app_root, "winfo_screenheight", lambda: screen_height)
    monkeypatch.setattr(app_root, "winfo_screenwidth", lambda: 1280)
    app_root.deiconify()
    try:
        app = DesktopApp(app_root)
        app_root.update()
        assert app.generate_btn.winfo_ismapped()
        assert app.status_label.winfo_ismapped()
        assert app.status_label.winfo_rooty() + app.status_label.winfo_height() <= app.result_pane.winfo_rooty()
    finally:
        for child in app_root.winfo_children():
            child.destroy()
        app_root.withdraw()


def test_result_placeholder_on_start(app):
    """未计算时结果区显示占位提示。"""
    texts = _collect_texts(app.result_frame)
    assert any("尚未计算" in t for t in texts)
    assert app.result_title.cget("text") == "计算结果"


def test_result_placeholder_cleared_after_render(app):
    """渲染结果后占位提示应被替换为实际结果。"""
    from re4_gems.solver import STATUS_OPTIMAL, SolveResult
    fake = SolveResult(
        status=STATUS_OPTIMAL,
        objective_x10=498000,
        treasure_sale_x10=498000,
        gem_sale_x10=0,
        consumed_gems=[2, 0, 3, 0, 0, 0],
        remaining_gems=[0, 0, 0, 0, 0, 0],
        elapsed_seconds=0.1,
    )
    app.result_snapshot = {"gems": [2, 0, 3, 0, 0, 0],
                           "treasures": {"flagon": 1, "butterfly_lamp": 1}, "mode": MODE_TOTAL}
    app._render_result(fake, app.result_snapshot)
    texts = _collect_texts(app.result_frame)
    assert not any("尚未计算" in t for t in texts)
    assert "总收益" in "\n".join(texts)


def test_no_fixed_wraplength_in_source():
    """结果区不应再使用固定 850/860/820 像素的 wraplength（避免缩窗时横向裁切）。"""
    import inspect
    import desktop_app as da
    src = inspect.getsource(da)
    assert "wraplength=850" not in src
    assert "wraplength=860" not in src
    assert "wraplength=820" not in src


def _collect_texts(widget):
    """递归收集一个 widget 子树内所有 Label 的文本。"""
    import tkinter as tk
    texts = []
    def walk(w):
        for c in w.winfo_children():
            try:
                if "text" in c.keys():
                    val = c.cget("text")
                    if val:
                        texts.append(val)
            except Exception:
                pass
            walk(c)
    walk(widget)
    return texts


def _gem_inventory(**kwargs):
    v = [0] * len(GEMS)
    ids = list(GEM_BY_ID.keys())
    for k, c in kwargs.items():
        v[ids.index(k)] = c
    return v
