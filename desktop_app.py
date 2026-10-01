"""《生化危机4 重制版》宝物与宝石镶嵌优化工具 — Windows 桌面版。

使用 Tkinter/ttk 制作原生窗口，Pillow 读取并等比例缩放图片。
直接复用 re4_gems/ 下经过测试的价格规则与全局优化算法（CP-SAT）。

入口不依赖 Streamlit 或 app.py；原网页版保留不动。

布局：
- 上方：库存输入（左栏 6 种宝石 + 右栏 10 种宝物）。
- 下方：横跨整个窗口宽度的计算结果，可独立滚动。

求解约定：reserved 全为 0，时限 30 秒；模式由单选项决定
（MODE_TOTAL 出售剩余宝石 / MODE_TREASURE_ONLY 保留剩余宝石）。
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from desktop.images import gem_image_path, load_image, treasure_image_path
from re4_gems.gem_data import GEMS, GEM_BY_ID, NUM_GEMS, COLOR_CN
from re4_gems.inventory import InventoryError, validate_inventory
from re4_gems.pricing import multiplier_name
from re4_gems.solver import (
    MODE_TOTAL,
    MODE_TREASURE_ONLY,
    STATUS_FEASIBLE,
    STATUS_OPTIMAL,
    STATUS_TEXT,
    SolveResult,
    solve,
)
from re4_gems.treasure_data import TREASURES, TREASURE_BY_ID

SOLVE_TIME_LIMIT = 30.0
IMAGE_SIZE = 64  # 图片边长（像素），约 64–72。
MAX_QTY = 9999  # 数量上限，防止异常大输入。


def _fmt(v: int) -> str:
    return f"{v:,}"


def _gems_text(vector: tuple[int, ...]) -> str:
    """把六维宝石向量转为中文描述。"""
    parts = []
    for i, g in enumerate(GEMS):
        cnt = vector[i]
        if cnt > 0:
            parts.append(f"{g.name_cn}×{cnt}")
    return "、".join(parts) if parts else "（不镶嵌，留空）"


def _parse_qty(raw: str, label: str) -> int | None:
    """严格解析数量：只接受非负整数，负数、小数、空串之外的非法内容都返回 None。

    返回 None 表示输入无效（调用方需提示，不能静默截断）。
    """
    s = raw.strip()
    if s == "":
        return 0  # 空输入视为 0（与网页版 number_input 行为一致）。
    # 只接受 ASCII 数字：拒绝负号、小数点、正负号、空格、全角数字、科学计数法等。
    if not s.isascii() or not s.isdigit():
        return None
    v = int(s)
    if v > MAX_QTY:
        return None
    return v


@dataclass
class AssignmentView:
    """结果展示用的一条方案（同款同方案合并后的件数展示）。"""

    treasure_id: str
    count: int
    vector: tuple[int, ...]
    multiplier: int
    price_x10: int
    gem_value: int
    empty_slots: int
    unit_price: int  # 单件售价（真实 ptas）。
    subtotal: int  # 小计 = 单件售价 × 件数。


class QuantityControl:
    """一个「− 按钮 / 可编辑输入框 / + 按钮」数量控件，三个部件操作同一个变量。

    通过 app 的回调在数量变化时使旧结果失效，并做严格校验。
    """

    def __init__(
        self,
        parent: tk.Misc,
        var: tk.StringVar,
        app: "DesktopApp",
        label: str,
    ):
        self.parent = parent
        self.var = var
        self.app = app
        self.label = label

        frame = ttk.Frame(parent)
        self.frame = frame

        self.minus_btn = ttk.Button(frame, text="−", width=3, command=self._on_minus)
        self.minus_btn.pack(side="left")

        self.entry = ttk.Entry(frame, textvariable=var, width=7, justify="center")
        self.entry.pack(side="left", padx=2)

        self.plus_btn = ttk.Button(frame, text="+", width=3, command=self._on_plus)
        self.plus_btn.pack(side="left")

        self._last_valid = 0
        var.trace_add("write", self._on_change)

    # ---------- 校验 ----------

    def _on_change(self, *_args) -> None:
        raw = self.var.get()
        if raw == "":
            return  # 允许临时清空（失焦/下一步再校验）。
        parsed = _parse_qty(raw, self.label)
        if parsed is None:
            # 无效输入：撤销到最近一次合法值。
            self.entry.after_idle(lambda: self._revert_invalid(raw))
        else:
            self._last_valid = parsed
            self.app._mark_dirty()

    def _revert_invalid(self, raw: str) -> None:
        self.var.set(str(self._last_valid))
        self.entry.icursor("end")
        self.app._show_input_error(
            f"「{self.label}」数量必须是 0～{MAX_QTY} 的非负整数，已拒绝「{raw.strip()}」。"
        )

    # ---------- 加减 ----------

    def _current(self) -> int:
        parsed = _parse_qty(self.var.get(), self.label)
        return parsed if parsed is not None else self._last_valid

    def _on_minus(self) -> None:
        cur = self._current()
        if cur <= 0:
            return
        nxt = cur - 1
        self.var.set(str(nxt))
        self._last_valid = nxt
        self.app._mark_dirty()

    def _on_plus(self) -> None:
        cur = self._current()
        if cur >= MAX_QTY:
            return
        nxt = cur + 1
        self.var.set(str(nxt))
        self._last_valid = nxt
        self.app._mark_dirty()


class DesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("《生化危机4 重制版》宝物镶嵌优化工具")
        was_withdrawn = self.root.state() == "withdrawn"
        self.root.withdraw()
        self.compact = self.root.winfo_screenheight() < 900
        self.image_size = 48 if self.compact else IMAGE_SIZE
        self.row_padding = 1 if self.compact else 3

        # 输入变量。
        self.gem_vars: list[tk.StringVar] = [tk.StringVar(value="0") for _ in range(NUM_GEMS)]
        self.treasure_vars: dict[str, tk.StringVar] = {
            t.treasure_id: tk.StringVar(value="0") for t in TREASURES
        }

        # 优化模式单选项（默认「出售剩余宝石」= MODE_TOTAL）。
        self.mode_var = tk.StringVar(value=MODE_TOTAL)

        # 结果状态。
        self.result: SolveResult | None = None
        self.result_snapshot: dict | None = None
        self._solving = False
        self._solve_token = 0  # 每次点击递增，用于丢弃过期结果。
        self._dirty = True  # 输入是否有变化导致旧结果失效。

        # 图片缓存（防止被 GC 回收）。
        self._photo_refs: list = []

        self._build_ui()
        self._configure_initial_geometry()
        if not was_withdrawn:
            self.root.deiconify()

    # ---------- UI 构建 ----------

    def _configure_initial_geometry(self) -> None:
        """先测量已创建的左栏，再确定不会遮住操作区的初始窗口尺寸。"""
        import ctypes

        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
        except Exception:
            pass
        self.root.update_idletasks()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        max_w = int(sw * 0.95)
        max_h = int(sh * 0.95)

        # 左栏只占其内容真正需要的宽度；多出来的宽度全部给宝物栏。
        left_w = max(430 if self.compact else 470, self.left_panel.winfo_reqwidth())
        right_w = max(540 if self.compact else 610, self.right_panel.winfo_reqwidth())
        self.columns.columnconfigure(0, minsize=left_w)
        self.columns.columnconfigure(1, minsize=right_w)
        target_w = max(1100 if self.compact else 1200, left_w + right_w + 64)
        w = min(target_w, max_w)

        # 结果栏保持较低高度（约为早期版本 1.5 倍），上方至少容纳左栏的所有控件。
        # 普通屏 270、小屏紧凑 203；增加的高度全部来自初始窗口增高，不挤压上方区域。
        result_h = 203 if self.compact else 270
        self.result_pane.configure(height=result_h)
        self.root.update_idletasks()
        top_h = self.input_header.winfo_reqheight() + self.left_panel.winfo_reqheight() + 36
        target_h = top_h + result_h
        h = min(target_h, max_h)

        self.root.minsize(min(max_w, left_w + right_w + 64), min(max_h, top_h + 110))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # 固定结果栏的初始高度；调整窗口大小时，新增空间都给上方输入区。
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        # ===== 上方：库存输入区（左栏固定、右栏独立滚动）=====
        self._build_input_area(self.root)

        # ===== 下方：横跨整个窗口宽度的结果区（可独立滚动）=====
        self._build_result_area(self.root)

    def _build_input_area(self, parent: tk.Misc) -> None:
        # 上方输入区：左栏固定显示（不滚动），右栏宝物列表独立滚动。
        input_pane = ttk.Frame(parent)
        input_pane.grid(row=0, column=0, sticky="nsew")
        self.input_pane = input_pane

        header = ttk.Label(
            input_pane,
            text="输入当前拥有的宝物与宝石数量，点击「生成镶嵌方案」计算全局最优镶嵌。",
            foreground="#333",
        )
        header.pack(fill="x", padx=12, pady=(10, 6))
        self.input_header = header

        # 左右两栏并列，均不使用统一的滚动容器。
        columns = ttk.Frame(input_pane)
        columns.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.columns = columns
        columns.rowconfigure(0, weight=1)
        columns.columnconfigure(0, weight=0)
        columns.columnconfigure(1, weight=1)

        # 左栏：宝石（含优化目标 + 按钮 + 状态），固定显示，首次打开完整可见。
        left = ttk.Frame(columns)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.left_panel = left
        self._build_gem_column(left)

        # 右栏：宝物库存，仅此栏独立垂直滚动。
        right = ttk.Frame(columns)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.right_panel = right
        self._build_treasure_column(right)

    def _build_treasure_scroll(self, parent: tk.Misc) -> tk.Canvas:
        """右栏专用的滚动容器：只包住宝物列表，滚轮/滚动条都作用于它。"""
        canvas = tk.Canvas(parent, highlightthickness=0)
        self.treasure_canvas = canvas
        self.treasure_scrollbar = ttk.Scrollbar(
            parent, orient="vertical", command=canvas.yview
        )
        self.treasure_frame = ttk.Frame(canvas)
        self.treasure_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._treasure_window = canvas.create_window(
            (0, 0), window=self.treasure_frame, anchor="nw"
        )
        canvas.configure(yscrollcommand=self.treasure_scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        self.treasure_scrollbar.pack(side="right", fill="y")

        def _on_canvas_configure(e):
            canvas.itemconfigure(self._treasure_window, width=e.width)

        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_wheel(event):
            # 只在鼠标悬停于右栏时滚动宝物列表（不抢结果区的滚轮）。
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"

        self._treasure_wheel_handler = _on_wheel
        canvas.bind("<MouseWheel>", _on_wheel)
        return canvas

    def _bind_wheel_to_tree(self, widget: tk.Misc, handler) -> None:
        """Tk 不会把子控件的滚轮事件自动交给父 Canvas。"""
        widget.bind("<MouseWheel>", handler)
        for child in widget.winfo_children():
            self._bind_wheel_to_tree(child, handler)

    def _build_gem_column(self, parent: tk.Misc) -> None:
        title = ttk.Label(parent, text="宝石库存", font=("Microsoft YaHei UI", 11, "bold"))
        title.pack(anchor="w", pady=(0, 2))
        ttk.Label(
            parent,
            text="已镶嵌且愿意拆下重配的宝石也应计入库存（同一颗只计数一次）。",
            foreground="#666",
            wraplength=360,
        ).pack(anchor="w", pady=(0, 4))

        self._gem_controls: list[QuantityControl] = []
        for i, g in enumerate(GEMS):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=self.row_padding)

            photo = load_image(gem_image_path(g.gem_id), self.image_size, g.name_cn)
            self._photo_refs.append(photo)
            img_lbl = ttk.Label(row, image=photo)
            img_lbl.pack(side="left", padx=(0, 8))

            info = ttk.Frame(row)
            info.pack(side="left", fill="x", expand=True)
            ttk.Label(info, text=g.name_cn, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
            shape_cn = "圆形" if g.shape == "round" else "矩形"
            ttk.Label(
                info,
                text=f"{g.name_en} · {COLOR_CN[g.color]} · {shape_cn} · 单颗 {_fmt(g.price)} ptas",
                foreground="#555",
                wraplength=200,
            ).pack(anchor="w")

            ctrl = QuantityControl(row, self.gem_vars[i], self, g.name_cn)
            ctrl.frame.pack(side="right")
            self._gem_controls.append(ctrl)

        # 优化目标：与左栏同宽、更舒展的区域，两个单选项分行摆放。
        mode_box = ttk.LabelFrame(
            parent, text="优化目标", padding=(10, 5) if self.compact else (12, 10)
        )
        mode_box.pack(fill="x", pady=(7 if self.compact else 14, 2))

        self.mode_total_rb = ttk.Radiobutton(
            mode_box,
            text="出售剩余宝石",
            variable=self.mode_var,
            value=MODE_TOTAL,
            command=self._on_mode_change,
        )
        self.mode_total_rb.pack(anchor="w", fill="x")
        if not self.compact:
            ttk.Label(
                mode_box,
                text="最大化宝物售价＋剩余宝石单卖收入，未镶嵌的宝石也卖掉。",
                foreground="#666",
                wraplength=340,
            ).pack(anchor="w", padx=(24, 0), pady=(0, 8))

        self.mode_treasure_rb = ttk.Radiobutton(
            mode_box,
            text="保留剩余宝石",
            variable=self.mode_var,
            value=MODE_TREASURE_ONLY,
            command=self._on_mode_change,
        )
        self.mode_treasure_rb.pack(anchor="w", fill="x")
        if not self.compact:
            ttk.Label(
                mode_box,
                text="只最大化宝物售价，剩余宝石留作以后使用，不计入本次收入。",
                foreground="#666",
                wraplength=340,
            ).pack(anchor="w", padx=(24, 0))
        else:
            self.mode_total_rb.configure(text="出售剩余宝石（宝物＋余宝石收入）")
            self.mode_treasure_rb.configure(text="保留剩余宝石（只计宝物售价）")

        # 生成按钮：左栏内单独一行、水平居中、宽度约 220 像素。
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=(7 if self.compact else 14, 2))
        self.generate_btn = ttk.Button(btn_row, text="生成镶嵌方案", command=self.on_generate)
        self.generate_btn.pack(anchor="center", ipadx=12, ipady=4)

        # 状态提示：按钮下方单独一行（避免状态文字变化把按钮推偏）。
        status_row = ttk.Frame(parent)
        status_row.pack(fill="x", pady=(2, 0))
        self.status_var = tk.StringVar(value="就绪。")
        self.status_label = ttk.Label(
            status_row, textvariable=self.status_var, foreground="#555", justify="center", wraplength=340
        )
        self.status_label.pack(anchor="center")

    def _build_treasure_column(self, parent: tk.Misc) -> None:
        # 右栏标题保持在滚动容器之外，始终可见。
        title = ttk.Label(parent, text="宝物库存", font=("Microsoft YaHei UI", 11, "bold"))
        title.pack(anchor="w", pady=(0, 2))
        ttk.Label(
            parent,
            text="同款多件可采用不同镶嵌方案；空槽或剩余宝石有时是优化结果。",
            foreground="#666",
            wraplength=440,
        ).pack(anchor="w", pady=(0, 4))

        # 宝物列表放入右栏专用滚动容器（独立滚动，不带动左栏）。
        canvas = self._build_treasure_scroll(parent)

        self._treasure_controls: dict[str, QuantityControl] = {}
        for t in TREASURES:
            row = ttk.Frame(self.treasure_frame)
            row.pack(fill="x", pady=self.row_padding)

            photo = load_image(treasure_image_path(t.treasure_id), self.image_size, t.name_cn)
            self._photo_refs.append(photo)
            img_lbl = ttk.Label(row, image=photo)
            img_lbl.pack(side="left", padx=(0, 8))

            info = ttk.Frame(row)
            info.pack(side="left", fill="x", expand=True)
            ttk.Label(info, text=t.name_cn, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
            # 宝物英文说明可换行，不设固定 wraplength，随右栏宽度自适应。
            ttk.Label(
                info,
                text=f"{t.name_en} · 基础价 {_fmt(t.base_price)} ptas · 圆形槽×{t.round_slots} 矩形槽×{t.rect_slots}",
                foreground="#555",
                wraplength=360,
            ).pack(anchor="w")

            ctrl = QuantityControl(row, self.treasure_vars[t.treasure_id], self, t.name_cn)
            ctrl.frame.pack(side="right")
            self._treasure_controls[t.treasure_id] = ctrl

        self._bind_wheel_to_tree(self.treasure_frame, self._treasure_wheel_handler)

    def _build_result_area(self, parent: tk.Misc) -> None:
        result_pane = ttk.Frame(parent)
        result_pane.grid(row=1, column=0, sticky="ew")
        result_pane.pack_propagate(False)
        self.result_pane = result_pane

        self.result_title = ttk.Label(
            result_pane, text="计算结果", font=("Microsoft YaHei UI", 11, "bold")
        )
        self.result_title.pack(anchor="w", padx=12, pady=(6, 2))

        # 结果主体放在独立的可滚动画布中，横跨整个窗口宽度。
        canvas = tk.Canvas(result_pane, highlightthickness=0)
        vscroll = ttk.Scrollbar(result_pane, orient="vertical", command=canvas.yview)
        self.result_frame = ttk.Frame(canvas)
        self.result_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._result_window = canvas.create_window((0, 0), window=self.result_frame, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0))
        vscroll.pack(side="right", fill="y", padx=(0, 4))

        def _on_canvas_configure(e):
            # 让结果内容宽度跟随画布实际宽度，自适应换行，避免固定 850/820。
            canvas.itemconfigure(self._result_window, width=e.width)

        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_wheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"

        self._result_wheel_handler = _on_wheel
        canvas.bind("<MouseWheel>", _on_wheel)

        # 首次打开时显示占位提示。
        self._show_result_placeholder()

    def _section_label(self, parent, text: str) -> ttk.Label:
        return ttk.Label(parent, text=text, font=("Microsoft YaHei UI", 11, "bold"))

    # ---------- 状态与失效 ----------

    def _mark_dirty(self) -> None:
        """任何数量/模式变化使旧结果失效。"""
        if not self._dirty:
            self._dirty = True
        # 已有结果被改动后立即清除展示，并提示需要重新计算。
        if self.result is not None or self.result_snapshot is not None:
            self.result = None
            self.result_snapshot = None
            self._show_result_placeholder()
            if not self._solving:
                self.status_var.set("输入已变化，请重新生成方案。")
                self.status_label.configure(foreground="#b9770e")

    def _on_mode_change(self) -> None:
        self._mark_dirty()

    def _show_input_error(self, message: str) -> None:
        self.status_var.set(message)
        self.status_label.configure(foreground="#c0392b")

    # ---------- 求解逻辑 ----------

    def _read_inventory(self) -> tuple[list[int], dict[str, int]] | None:
        """读取并校验输入。返回 (gem_inventory, treasure_counts)；无效则弹提示并返回 None。"""
        gem_inventory = []
        for i, g in enumerate(GEMS):
            parsed = _parse_qty(self.gem_vars[i].get(), g.name_cn)
            if parsed is None:
                self._show_input_error(f"「{g.name_cn}」数量无效，必须是 0～{MAX_QTY} 的非负整数。")
                return None
            gem_inventory.append(parsed)

        treasure_counts: dict[str, int] = {}
        for t in TREASURES:
            parsed = _parse_qty(self.treasure_vars[t.treasure_id].get(), t.name_cn)
            if parsed is None:
                self._show_input_error(f"「{t.name_cn}」数量无效，必须是 0～{MAX_QTY} 的非负整数。")
                return None
            if parsed > 0:
                treasure_counts[t.treasure_id] = parsed

        return gem_inventory, treasure_counts

    def on_generate(self) -> None:
        if self._solving:
            # 重复点击：忽略（已有任务在进行）。
            return
        inv = self._read_inventory()
        if inv is None:
            return
        gem_inventory, treasure_counts = inv
        mode = self.mode_var.get()

        # 固定输入快照（含模式），清空旧结果。
        self.result = None
        self.result_snapshot = None
        self._clear_result_display()

        # 校验（保留数量全 0）。
        reserved = [0] * NUM_GEMS
        try:
            validate_inventory(gem_inventory.copy(), reserved.copy(), treasure_counts.copy())
        except InventoryError as e:
            self._show_input_error(f"输入错误：{e}")
            return

        token = self._solve_token + 1
        self._solve_token = token
        self._solving = True
        self._dirty = False
        self.generate_btn.configure(state="disabled")
        self.status_var.set("正在计算全局最优方案…")
        self.status_label.configure(foreground="#555")

        snapshot = {
            "gems": gem_inventory.copy(),
            "treasures": treasure_counts.copy(),
            "mode": mode,
        }

        threading.Thread(target=self._solve_worker, args=(token, snapshot), daemon=True).start()

    def _solve_worker(self, token: int, snapshot: dict) -> None:
        try:
            result = solve(
                snapshot["treasures"],
                snapshot["gems"],
                reserved=[0] * NUM_GEMS,
                mode=snapshot["mode"],
                time_limit_seconds=SOLVE_TIME_LIMIT,
            )
        except Exception as e:  # noqa: BLE001
            result = None
            err = str(e)
        else:
            err = None

        # 回到主线程更新 UI。
        self.root.after(0, lambda: self._on_solve_done(token, snapshot, result, err))

    def _on_solve_done(self, token: int, snapshot: dict, result: SolveResult | None, err: str | None) -> None:
        self._solving = False
        self.generate_btn.configure(state="normal")

        if token != self._solve_token:
            return  # 过期结果，丢弃。

        if err is not None:
            self.status_var.set(f"求解出错：{err}")
            self.status_label.configure(foreground="#c0392b")
            return

        self.result = result
        self.result_snapshot = snapshot
        self._render_result(result, snapshot)

    def _clear_result_display(self) -> None:
        self.result_title.configure(text="计算结果", foreground="")
        self._destroy_result_children()

    def _destroy_result_children(self) -> None:
        for child in self.result_frame.winfo_children():
            child.destroy()

    def _show_result_placeholder(self) -> None:
        """尚未计算时显示清晰的标题和简短占位提示。"""
        self._destroy_result_children()
        self.result_title.configure(text="计算结果", foreground="")
        ttk.Label(
            self.result_frame,
            text="尚未计算。填写上方宝石与宝物数量后，点击「生成镶嵌方案」。",
            foreground="#888",
        ).pack(anchor="w", pady=(4, 0))
        self._bind_wheel_to_tree(self.result_frame, self._result_wheel_handler)

    # ---------- 结果渲染 ----------

    def _render_result(self, result: SolveResult, snapshot: dict) -> None:
        self._clear_result_display()
        mode = snapshot.get("mode", MODE_TOTAL)
        keep_gems = mode == MODE_TREASURE_ONLY

        status = result.status
        if status == STATUS_OPTIMAL:
            status_text = "已证明全局最优"
            color = "#1e8449"
        elif status == STATUS_FEASIBLE:
            status_text = "当前可行方案，尚未证明最优"
            color = "#b9770e"
        else:
            # UNKNOWN / INFEASIBLE / MODEL_INVALID / 其他。
            self.status_var.set(STATUS_TEXT.get(status, status))
            self.status_label.configure(foreground="#c0392b")
            self.result_title.configure(text="无法给出方案", foreground="#c0392b")
            msg = result.message or "计算未得到可报告的解。"
            ttk.Label(
                self.result_frame,
                text=f"{STATUS_TEXT.get(status, status)}：{msg}",
                foreground="#c0392b",
            ).pack(anchor="w", fill="x")
            self._bind_wheel_to_tree(self.result_frame, self._result_wheel_handler)
            return

        # 正常结果。
        self.status_var.set("计算完成。")
        self.status_label.configure(foreground="#1e8449")
        self.result_title.configure(
            text=f"结果（{status_text}，耗时 {result.elapsed_seconds:.2f} 秒）",
            foreground=color,
        )

        # 汇总。
        summary = ttk.Frame(self.result_frame)
        summary.pack(fill="x", pady=4)

        def _metric(parent, label, value):
            f = ttk.Frame(parent)
            f.pack(side="left", padx=(0, 24))
            ttk.Label(f, text=label, foreground="#666").pack(anchor="w")
            ttk.Label(f, text=value, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
            return f

        _metric(summary, "总收益", f"{_fmt(result.objective)} ptas")
        _metric(summary, "宝物售出价合计", f"{_fmt(result.treasure_sale)} ptas")
        if keep_gems:
            # 保留模式：剩余宝石不计入收入，措辞改为「保留的宝石」。
            _metric(summary, "保留的宝石（未计入收入）", f"{_fmt(result.gem_sale)} ptas")
        else:
            _metric(summary, "未镶宝石单卖收入", f"{_fmt(result.gem_sale)} ptas")

        if status == STATUS_FEASIBLE:
            upper = (result.upper_bound_x10 + 9) // 10
            ttk.Label(
                summary,
                text=f"收入上界 {_fmt(upper)} ptas，尚未证明最优。",
                foreground="#b9770e",
            ).pack(side="left")

        # 镶嵌方案（按实际方案分组展示，同款不同方案分别显示）。
        ttk.Separator(self.result_frame, orient="horizontal").pack(fill="x", pady=8)
        self._section_label(self.result_frame, "镶嵌方案").pack(anchor="w", pady=(0, 2))

        assignments = self._group_assignments(result)
        if not assignments:
            ttk.Label(self.result_frame, text="没有需要镶嵌的宝物（或全部留空）。", foreground="#666").pack(anchor="w")
        else:
            for av in assignments:
                self._render_assignment(av)

        # 剩余宝石。
        ttk.Separator(self.result_frame, orient="horizontal").pack(fill="x", pady=8)
        self._section_label(self.result_frame, "剩余宝石").pack(anchor="w", pady=(0, 2))
        remaining_text = self._remaining_text(result)
        ttk.Label(self.result_frame, text=remaining_text).pack(anchor="w", fill="x", pady=(0, 4))

        hint = ttk.Label(
            self.result_frame,
            text="提示：空槽或剩余宝石有时是优化结果；同形状槽位内的具体摆放位置可自行决定。",
            foreground="#888",
        )
        hint.pack(anchor="w")
        self._bind_wheel_to_tree(self.result_frame, self._result_wheel_handler)

    def _group_assignments(self, result: SolveResult) -> list[AssignmentView]:
        """把 result.assignments 按 (treasure_id, vector) 分组，产出展示列表。"""
        grouped: dict[tuple, list] = {}
        for a in result.assignments:
            key = (a.treasure_id, a.combination.vector)
            grouped.setdefault(key, []).append(a)

        views: list[AssignmentView] = []
        for (tid, vec), items in grouped.items():
            combo = items[0].combination
            total_count = sum(x.count for x in items)
            unit_price = combo.price_x10 // 10
            views.append(
                AssignmentView(
                    treasure_id=tid,
                    count=total_count,
                    vector=vec,
                    multiplier=combo.multiplier,
                    price_x10=combo.price_x10,
                    gem_value=combo.gem_value,
                    empty_slots=combo.empty_slots,
                    unit_price=unit_price,
                    subtotal=unit_price * total_count,
                )
            )
        # 保持稳定顺序（按宝物在 TREASURES 中的顺序，再按方案）。
        order = {t.treasure_id: i for i, t in enumerate(TREASURES)}
        views.sort(key=lambda v: (order.get(v.treasure_id, 999), v.vector))
        return views

    def _render_assignment(self, av: AssignmentView) -> None:
        treasure = TREASURE_BY_ID[av.treasure_id]
        card = ttk.Frame(self.result_frame, relief="groove", padding=8)
        card.pack(fill="x", pady=4)

        # 标题行。
        title = ttk.Label(
            card,
            text=f"{treasure.name_cn}（{treasure.name_en}）×{av.count} 件",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        title.pack(anchor="w")

        # 所需宝石。
        gems_text = _gems_text(av.vector)
        ttk.Label(card, text=f"所需宝石：{gems_text}").pack(anchor="w")

        # 倍率、售价、小计。
        ttk.Label(
            card,
            text=f"倍率 {av.multiplier / 10:.1f}（{multiplier_name(av.multiplier)}）",
            foreground="#555",
        ).pack(anchor="w")
        ttk.Label(
            card,
            text=f"单件售价 {_fmt(av.unit_price)} ptas · 小计 {_fmt(av.subtotal)} ptas",
            foreground="#555",
        ).pack(anchor="w")

    def _remaining_text(self, result: SolveResult) -> str:
        parts = []
        for i, g in enumerate(GEMS):
            remaining = result.remaining_gems[i]
            consumed = result.consumed_gems[i]
            total = self.result_snapshot["gems"][i] if self.result_snapshot else consumed + remaining
            if remaining > 0:
                parts.append(f"{g.name_cn} 剩 {remaining}")
            elif total > 0:
                parts.append(f"{g.name_cn} 已用完")
        if not parts:
            return "无剩余宝石。"
        return "；".join(parts)


def main() -> None:
    root = tk.Tk()
    app = DesktopApp(root)
    root.mainloop()


def _smoke_test() -> int:
    """打包后自检：不启动 GUI，直接跑一次示例求解并把结果写到文件。

    供构建/CI 验证 exe 内部 ortools 动态库与求解链路是否正常。
    返回 0 表示成功，非 0 表示失败。普通用户不会触发此路径。
    由于 exe 无控制台窗口，结果写入同目录的 smoke_test_result.txt。
    """
    import tempfile
    out_path = Path(sys.executable).resolve().parent / "smoke_test_result.txt" \
        if getattr(sys, "frozen", False) else \
        Path(tempfile.gettempdir()) / "re4_smoke_test_result.txt"
    try:
        result = solve(
            {"flagon": 1, "butterfly_lamp": 1},
            _gem_inventory_smoke(),
            reserved=[0] * NUM_GEMS,
            mode=MODE_TOTAL,
            time_limit_seconds=30.0,
        )
    except Exception as e:  # noqa: BLE001
        out_path.write_text(f"SMOKE_FAIL: {e}", encoding="utf-8")
        return 1
    if result.status == STATUS_OPTIMAL and result.objective == 49800:
        out_path.write_text(
            f"SMOKE_OK status={result.status} objective={result.objective} "
            f"elapsed={result.elapsed_seconds:.3f}",
            encoding="utf-8",
        )
        return 0
    out_path.write_text(
        f"SMOKE_UNEXPECTED status={result.status} objective={result.objective}",
        encoding="utf-8",
    )
    return 2


def _gem_inventory_smoke() -> list[int]:
    v = [0] * NUM_GEMS
    ids = [g.gem_id for g in GEMS]
    v[ids.index("ruby")] = 2
    v[ids.index("yellow_diamond")] = 3
    return v


if __name__ == "__main__":
    import sys

    if "--smoke-test" in sys.argv:
        sys.exit(_smoke_test())
    main()
