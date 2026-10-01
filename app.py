"""《生化危机4 重制版》宝物与宝石镶嵌优化工具 — Streamlit 界面。"""

from __future__ import annotations

import json

import streamlit as st

from re4_gems.gem_data import GEMS, NUM_GEMS, COLOR_CN
from re4_gems.inventory import (
    InventoryError,
    example_inventory,
    inventory_from_json,
    inventory_to_dict,
    validate_inventory,
)
from re4_gems.pricing import multiplier_name
from re4_gems.solver import (
    MODE_TOTAL,
    MODE_TREASURE_ONLY,
    STATUS_FEASIBLE,
    STATUS_OPTIMAL,
    STATUS_TEXT,
    solve,
)
from re4_gems.treasure_data import TREASURES, TREASURE_BY_ID

import web_images

st.set_page_config(page_title="RE4 宝物镶嵌优化工具", page_icon="💎", layout="wide")

GEM_IDS = [g.gem_id for g in GEMS]

# 网页版缩略图边长（像素）。
THUMB_SIZE = 48


def _fmt(v: int) -> str:
    return f"{v:,}"


def _render_thumb(kind: str, item_id: str, label: str, size: int = THUMB_SIZE) -> None:
    """在名称旁显示一张缩略图；缺图/损坏时显示简洁占位，不影响计算。

    kind 取 "gems" 或 "treasures"；item_id 为英文 ID；label 为占位文字。
    """
    data = web_images.image_bytes(kind, item_id)
    if data is not None:
        try:
            st.image(data, width=size)
            return
        except Exception:
            # PNG 文件损坏时保留表单和求解功能。
            pass

    # 简洁占位：一个浅色圆角块 + 首字。
    st.markdown(
        (
            f"<div style='width:{size}px;height:{size}px;"
            "border:1px dashed #bbb;border-radius:6px;"
            "display:flex;align-items:center;justify-content:center;"
            "color:#999;font-size:18px;background:#f7f7f7;'>"
            f"{label[0]}</div>"
        ),
        unsafe_allow_html=True,
    )


def build_state_key(gem_inventory, reserved, treasure_counts, mode, time_limit) -> str:
    return json.dumps(
        {
            "gems": gem_inventory,
            "reserved": reserved,
            "treasures": treasure_counts,
            "mode": mode,
            "time": time_limit,
        },
        sort_keys=True,
    )


def _init_widget_state() -> None:
    """输入控件是库存的唯一状态来源，必须在创建控件前初始化。"""
    for g in GEMS:
        st.session_state.setdefault(f"gem_inv_{g.gem_id}", 0)
        st.session_state.setdefault(f"gem_res_{g.gem_id}", 0)
    for t in TREASURES:
        st.session_state.setdefault(f"treasure_q_{t.treasure_id}", 0)
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("result_key", None)
    st.session_state.setdefault("result_input", None)
    st.session_state.setdefault("import_notice", None)


def _read_widgets() -> tuple[list[int], list[int], dict[str, int]]:
    gems = [int(st.session_state[f"gem_inv_{g.gem_id}"]) for g in GEMS]
    reserved = [int(st.session_state[f"gem_res_{g.gem_id}"]) for g in GEMS]
    treasures = {
        t.treasure_id: int(st.session_state[f"treasure_q_{t.treasure_id}"])
        for t in TREASURES
        if st.session_state[f"treasure_q_{t.treasure_id}"] > 0
    }
    return gems, reserved, treasures


def _apply_inventory(gems: list[int], reserved: list[int], treasures: dict[str, int]) -> None:
    """按钮回调在新一轮控件创建前同步所有 key。"""
    for i, g in enumerate(GEMS):
        st.session_state[f"gem_inv_{g.gem_id}"] = gems[i]
        st.session_state[f"gem_res_{g.gem_id}"] = reserved[i]
    for t in TREASURES:
        st.session_state[f"treasure_q_{t.treasure_id}"] = treasures.get(t.treasure_id, 0)
    st.session_state.result = None
    st.session_state.result_key = None
    st.session_state.result_input = None


def _load_example() -> None:
    _apply_inventory(*example_inventory())
    st.session_state.import_notice = None


def _clear_inventory() -> None:
    _apply_inventory([0] * NUM_GEMS, [0] * NUM_GEMS, {})
    st.session_state.import_notice = None


def _import_uploaded() -> None:
    uploaded = st.session_state.get("upload")
    if uploaded is None:
        st.session_state.import_notice = ("error", "请先选择 JSON 库存文件。")
        return
    try:
        raw = uploaded.getvalue()
        if len(raw) > 2_000_000:
            raise InventoryError("文件超过 2 MB，请选择较小的库存 JSON 文件。")
        gems, reserved, treasures = inventory_from_json(raw)
        _apply_inventory(gems, reserved, treasures)
        st.session_state.import_notice = ("success", "已导入库存，可以继续编辑或计算。")
    except InventoryError as exc:
        st.session_state.import_notice = ("error", f"导入失败：{exc}")


def main() -> None:
    _init_widget_state()
    st.title("💎《生化危机4 重制版》宝物与宝石镶嵌优化工具")
    st.caption(
        "输入当前库存，程序按真实游戏规则计算全局最优镶嵌方案，并给出每件宝物的镶嵌建议、售价与剩余宝石。"
    )

    # ---------- 侧栏：优化参数 ----------
    with st.sidebar:
        st.header("⚙️ 优化参数")
        mode = st.radio(
            "优化目标",
            options=[MODE_TOTAL, MODE_TREASURE_ONLY],
            format_func=lambda m: (
                "全部变现总收入最大化（含剩余宝石单卖）"
                if m == MODE_TOTAL
                else "仅最大化宝物售出价（剩余宝石保留）"
            ),
            help="两种模式目标不同：默认模式把剩余宝石按基础价单卖计入收入；第二种模式只算宝物售价，剩余宝石全部保留。",
        )
        time_limit = st.slider("求解时限（秒）", 5, 120, 30, 5)

    # ---------- 输入区 ----------
    st.header("📥 输入库存")

    col_gem, col_treasure = st.columns([1, 1])

    with col_gem:
        st.subheader("宝石库存")
        for g in GEMS:
            c_img, c1, c2, c3, c4 = st.columns([0.7, 1.8, 2, 1.4, 1])
            with c_img:
                _render_thumb("gems", g.gem_id, g.name_cn)
            with c1:
                st.markdown(f"**{g.name_cn}**")
                st.caption(f"{g.name_en}")
            with c2:
                color_cn = COLOR_CN[g.color]
                shape_cn = "圆形" if g.shape == "round" else "矩形"
                st.markdown(f"{color_cn} · {shape_cn} · {_fmt(g.price)} ptas")
            with c3:
                st.number_input(
                    "库存",
                    min_value=0,
                    step=1,
                    key=f"gem_inv_{g.gem_id}",
                )
            with c4:
                st.number_input(
                    "保留",
                    min_value=0,
                    step=1,
                    key=f"gem_res_{g.gem_id}",
                )

        st.info(
            "已镶嵌且愿意拆下重配的宝石，也应计入库存（同一颗只计数一次）。"
            "保留的宝石不参与镶嵌、不计入出售收入。"
        )

    with col_treasure:
        st.subheader("宝物库存")
        st.caption("选择名称并填写数量；同款多件可采用不同方案。")
        for t in TREASURES:
            c_img, c1, c2 = st.columns([0.7, 3, 1])
            with c_img:
                _render_thumb("treasures", t.treasure_id, t.name_cn)
            with c1:
                st.markdown(f"**{t.name_cn}**（{t.name_en}）")
                st.caption(
                    f"基础价 {_fmt(t.base_price)} ptas · 圆形槽 ×{t.round_slots} · 矩形槽 ×{t.rect_slots}"
                )
            with c2:
                st.number_input(
                    "数量",
                    min_value=0,
                    step=1,
                    key=f"treasure_q_{t.treasure_id}",
                )

    # ---------- 库存文件操作 ----------
    st.subheader("🗂️ 库存文件")
    col_op1, col_op2, col_op3, col_op4 = st.columns([1, 1, 1, 1])
    with col_op1:
        st.file_uploader("选择库存 JSON", type=["json"], key="upload")
        st.button("导入所选 JSON", on_click=_import_uploaded)
    with col_op2:
        gem_inventory, reserved, treasure_counts = _read_widgets()
        export = inventory_to_dict(
            gem_inventory, reserved, treasure_counts
        )
        st.download_button(
            "导出 JSON",
            data=json.dumps(export, ensure_ascii=False, indent=2),
            file_name="re4_inventory.json",
            mime="application/json",
        )
    with col_op3:
        st.button("加载示例", on_click=_load_example)
    with col_op4:
        st.button("清空", on_click=_clear_inventory)

    if st.session_state.import_notice:
        level, message = st.session_state.import_notice
        (st.success if level == "success" else st.error)(message)

    # ---------- 求解 ----------
    st.divider()
    run_col, _ = st.columns([1, 3])
    with run_col:
        do_solve = st.button("🚀 计算全局最优方案", type="primary", use_container_width=True)

    current_key = build_state_key(
        gem_inventory,
        reserved,
        treasure_counts,
        mode,
        time_limit,
    )

    if do_solve:
        st.session_state.result = None
        st.session_state.result_key = None
        st.session_state.result_input = None
        try:
            validate_inventory(gem_inventory.copy(), reserved.copy(), treasure_counts.copy())
            result = solve(
                treasure_counts,
                gem_inventory,
                reserved,
                mode=mode,
                time_limit_seconds=float(time_limit),
            )
            st.session_state.result = result
            st.session_state.result_key = current_key
            st.session_state.result_input = {
                "gems": gem_inventory.copy(),
                "reserved": reserved.copy(),
                "treasures": treasure_counts.copy(),
            }
        except InventoryError as e:
            st.error(f"输入错误：{e}")
        except Exception as e:  # noqa: BLE001
            st.error(f"求解出错：{e}")

    # 旧结果标记。
    if st.session_state.result is not None and st.session_state.result_key != current_key:
        st.warning("⚠️ 库存或优化参数已改变，请重新计算后查看或导出方案。")

    # ---------- 结果区 ----------
    result = st.session_state.result
    if result is not None and st.session_state.result_key == current_key:
        render_result(result, st.session_state.result_input)

    st.divider()
    st.caption("数据与规则依据《生化危机4 重制版》官方镶嵌机制整理，价格单位为 ptas。")


def render_result(result, snapshot: dict) -> None:
    st.header("📊 优化结果")

    status_color = "green" if result.status == STATUS_OPTIMAL else ("orange" if result.status == STATUS_FEASIBLE else "red")
    st.markdown(f"**求解状态：** :{status_color}[{STATUS_TEXT.get(result.status, result.status)}]")
    st.caption(f"求解耗时：{result.elapsed_seconds:.2f} 秒")
    if result.status not in (STATUS_OPTIMAL, STATUS_FEASIBLE):
        if result.message:
            st.error(f"求解器返回：{result.message}")
        st.info("当前没有可报告的镶嵌方案。可检查库存，或提高求解时限后重试。")
        return

    mode_text = (
        "全部变现总收入最大化（含剩余宝石单卖）"
        if result.mode == MODE_TOTAL
        else "仅最大化宝物售出价（剩余宝石保留）"
    )
    st.write(f"**优化目标：** {mode_text}")

    # 汇总卡片。
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总收入", f"{_fmt(result.objective)} ptas")
    c2.metric("宝物售出价合计", f"{_fmt(result.treasure_sale)} ptas")
    c3.metric("剩余宝石单卖价值", f"{_fmt(result.gem_sale)} ptas")

    # 相比全单卖的增益。
    base_total = _baseline_sale(snapshot, result.mode)
    baseline_label = "相比全单卖多赚" if result.mode == MODE_TOTAL else "相比宝物直接单卖多赚"
    c4.metric(baseline_label, f"{_fmt(result.objective - base_total)} ptas")

    if result.status == STATUS_FEASIBLE:
        upper_bound = (result.upper_bound_x10 + 9) // 10
        st.info(f"收入上界：{_fmt(upper_bound)} ptas；当前与上界差距：{result.gap:,.1f} ptas。尚未证明最优。")

    if result.mode == MODE_TREASURE_ONLY:
        st.warning(
            "注意：当前模式仅最大化宝物售出价，剩余宝石全部保留、不计入收入，"
            "因此“总收入”并非整份库存全部变现的最大收入。"
        )

    st.divider()
    st.subheader("🔩 逐件镶嵌方案")

    # 合并同类同方案。
    from collections import defaultdict

    grouped: dict[tuple, list] = defaultdict(list)
    for a in result.assignments:
        key = (a.treasure_id, a.combination.vector)
        grouped[key].append(a)

    # 生成逐件编号。
    counter: dict[str, int] = defaultdict(int)

    for (tid, vec), items in grouped.items():
        treasure = TREASURE_BY_ID[tid]
        combo = items[0].combination
        total_count = sum(x.count for x in items)

        # 该方案下逐件编号。
        indices = []
        for x in items:
            for _ in range(x.count):
                counter[tid] += 1
                indices.append(counter[tid])

        extra_value = combo.price_x10 // 10 - treasure.base_price - combo.gem_value

        with st.expander(
            f"{treasure.name_cn}（{treasure.name_en}）共 {total_count} 件 — 售价 {_fmt(combo.price_x10 // 10)} ptas",
            expanded=False,
        ):
            st.markdown(f"**方案：** {treasure.name_cn} {treasure.name_en}")
            st.write(f"件数：{total_count} 件（编号 {', '.join('#' + str(i) for i in indices)}）")

            # 槽位展示。
            round_part = []
            rect_part = []
            for g in GEMS:
                cnt = combo.vector[GEM_IDS.index(g.gem_id)]
                if cnt <= 0:
                    continue
                (round_part if g.shape == "round" else rect_part).append(f"{g.name_cn} ×{cnt}")

            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown("**圆形槽：**")
                st.write("、".join(round_part) if round_part else "（空）")
            with c_b:
                st.markdown("**矩形槽：**")
                st.write("、".join(rect_part) if rect_part else "（空）")

            st.write(f"剩余空槽：{combo.empty_slots}")
            st.write(f"触发组合：**{multiplier_name(combo.multiplier)}**（倍率 {combo.multiplier / 10:.1f}）")

            col_d1, col_d2, col_d3 = st.columns(3)
            col_d1.metric("宝物基础价", f"{_fmt(treasure.base_price)}")
            col_d2.metric("镶嵌宝石价值", f"{_fmt(combo.gem_value)}")
            col_d3.metric("最终售价", f"{_fmt(combo.price_x10 // 10)}")
            st.caption(f"额外增值：{_fmt(extra_value)} ptas（售价 − 基础价 − 宝石价值）")

    if not result.assignments:
        st.info("没有任何宝物被分配镶嵌方案（可能没有宝物，或全部留空）。")

    st.divider()
    st.subheader("💠 宝石对账")

    gem_rows = []
    for i, g in enumerate(GEMS):
        inv = snapshot["gems"][i]
        reserved = snapshot["reserved"][i]
        consumed = result.consumed_gems[i]
        remaining = result.remaining_gems[i]
        gem_rows.append(
            {
                "宝石": f"{g.name_cn}（{g.name_en}）",
                "颜色": COLOR_CN[g.color],
                "总库存": inv,
                "保留数": reserved,
                "镶嵌消耗": consumed,
                "剩余可用": remaining,
            }
        )

    import pandas as pd

    st.dataframe(pd.DataFrame(gem_rows), use_container_width=True, hide_index=True)

    # Streamlit 代码框自带复制按钮，另外保留文件下载。
    report = build_text_report(result, snapshot)
    with st.expander("📋 复制中文操作清单（点文本框右上角复制）"):
        st.code(report, language=None)
    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "📋 下载中文操作清单",
            data=report,
            file_name="re4_镶嵌方案.txt",
            mime="text/plain",
        )
    with col_b:
        st.download_button(
            "💾 导出结果 JSON",
            data=json.dumps(build_result_json(result, snapshot), ensure_ascii=False, indent=2),
            file_name="re4_result.json",
            mime="application/json",
        )


def _baseline_sale(snapshot: dict, mode: str) -> int:
    """按求解当时库存计算对应目标的直接单卖基准。"""
    base = 0
    for tid, q in snapshot["treasures"].items():
        if q > 0 and tid in TREASURE_BY_ID:
            base += TREASURE_BY_ID[tid].base_price * q
    if mode == MODE_TOTAL:
        for i, g in enumerate(GEMS):
            base += g.price * (snapshot["gems"][i] - snapshot["reserved"][i])
    return base


def build_text_report(result, snapshot: dict) -> str:
    lines = []
    lines.append("《生化危机4 重制版》宝物镶嵌方案")
    lines.append("=" * 40)
    mode_text = (
        "全部变现总收入最大化"
        if result.mode == MODE_TOTAL
        else "仅最大化宝物售出价（剩余宝石保留）"
    )
    lines.append(f"优化目标：{mode_text}")
    lines.append(f"求解状态：{STATUS_TEXT.get(result.status, result.status)}")
    lines.append(f"总收入：{result.objective:,} ptas")
    lines.append(f"宝物售出价合计：{result.treasure_sale:,} ptas")
    lines.append(f"剩余宝石单卖价值：{result.gem_sale:,} ptas")
    lines.append("")

    from collections import defaultdict

    counter: dict[str, int] = defaultdict(int)
    grouped: dict[tuple, list] = defaultdict(list)
    for a in result.assignments:
        grouped[(a.treasure_id, a.combination.vector)].append(a)

    lines.append("【镶嵌方案】")
    for (tid, vec), items in grouped.items():
        treasure = TREASURE_BY_ID[tid]
        combo = items[0].combination
        total_count = sum(x.count for x in items)
        parts = []
        for g in GEMS:
            cnt = combo.vector[GEM_IDS.index(g.gem_id)]
            if cnt > 0:
                shape = "圆形" if g.shape == "round" else "矩形"
                parts.append(f"{shape}{g.name_cn}×{cnt}")
        desc = "、".join(parts) if parts else "留空"
        extra = combo.price_x10 // 10 - treasure.base_price - combo.gem_value
        lines.append(
            f"- {treasure.name_cn}（{treasure.name_en}）×{total_count}：{desc}"
            f" → 售价 {combo.price_x10 // 10:,} ptas"
            f"（倍率 {combo.multiplier / 10:.1f}，增值 {extra:,}）"
        )

    lines.append("")
    lines.append("【宝石对账】")
    for i, g in enumerate(GEMS):
        inv = snapshot["gems"][i]
        res = snapshot["reserved"][i]
        lines.append(
            f"- {g.name_cn}：库存 {inv}，保留 {res}，镶嵌 {result.consumed_gems[i]}，剩余 {result.remaining_gems[i]}"
        )

    return "\n".join(lines)


def build_result_json(result, snapshot: dict) -> dict:
    assignments = []
    for a in result.assignments:
        treasure = TREASURE_BY_ID[a.treasure_id]
        gem_breakdown = {}
        for g in GEMS:
            cnt = a.combination.vector[GEM_IDS.index(g.gem_id)]
            if cnt > 0:
                gem_breakdown[g.gem_id] = cnt
        assignments.append(
            {
                "treasure_id": a.treasure_id,
                "name_cn": treasure.name_cn,
                "name_en": treasure.name_en,
                "count": a.count,
                "gems": gem_breakdown,
                "multiplier": a.combination.multiplier / 10.0,
                "price": a.combination.price_x10 // 10,
                "empty_slots": a.combination.empty_slots,
            }
        )
    return {
        "mode": result.mode,
        "status": result.status,
        "total_income": result.objective,
        "treasure_sale": result.treasure_sale,
        "gem_sale": result.gem_sale,
        "elapsed_seconds": result.elapsed_seconds,
        "inventory": inventory_to_dict(snapshot["gems"], snapshot["reserved"], snapshot["treasures"]),
        "assignments": assignments,
        "remaining_gems": {GEM_IDS[i]: result.remaining_gems[i] for i in range(NUM_GEMS)},
    }


if __name__ == "__main__":
    main()
