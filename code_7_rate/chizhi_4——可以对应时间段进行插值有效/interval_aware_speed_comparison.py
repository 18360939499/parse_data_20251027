#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参比平均流速与侧扫雷达“时间段平均流速”的插值比较程序。

为什么这次不能简单地把雷达数据当成瞬时值？
------------------------------------------------
雷达文件中的每条记录都有“开始时间、结束时间、平均流速”，例如：
    2026-08-06 07:00 ～ 08:00，平均流速 -0.0072 m/s
这表示 -0.0072 m/s 是这一小时的平均值，不是 07:00 那一瞬间的值。

本程序采用的时间段处理规则：
------------------------------------------------
1. 参比时段位于某个雷达时段内部：直接采用该雷达平均流速；
2. 参比时段位于两个雷达时段之间的空档：
   在“前一雷达时段的结束时刻”和“后一雷达时段的开始时刻”之间线性插值；
3. 如果一个参比时段同时经过“雷达实测段”和“空档插值段”，自动拆成多个小段；
4. 对所有小段按持续时间加权，得到整个参比时段对应的雷达平均流速；
5. 不在雷达数据总时间范围以外进行外推。

最简单的运行方法：
------------------------------------------------
把本 Python 文件和下面两个 Excel 放在同一个文件夹，直接运行：
    1——参比平均流速(1).xlsx
    2——侧扫雷达平均流速.xlsx

程序会自动生成：
    雷达时间段插值比测结果.xlsx

也可以手动指定路径：
    python interval_aware_speed_comparison.py \
        --reference "1——参比平均流速(1).xlsx" \
        --radar "2——侧扫雷达平均流速.xlsx" \
        --output "雷达时间段插值比测结果.xlsx"
"""

# ============================== 模块 1：导入工具包 ==============================
# argparse：读取命令行参数。
# json：可选地输出 JSON 中间结果，方便复核。
# datetime、Path：处理时间与文件路径。
# numpy、pandas：数据清洗、插值和统计计算。
# openpyxl：生成新的 Excel，并设置基础格式。
import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# ============================== 模块 2：文件名与列名配置 ==============================
DEFAULT_REFERENCE_NAME = "1——参比平均流速.xlsx"
DEFAULT_RADAR_NAME = "2——侧扫雷达平均流速.xlsx"
DEFAULT_OUTPUT_NAME = "雷达时间段插值比测结果.xlsx"

REF_START = "施测时间"
REF_END = "结束时分"
REF_SPEED = "平均流速"

RADAR_START = "开始时间"
RADAR_END = "结束时间"
RADAR_SPEED = "平均流速(m/s)"


# ============================== 模块 3：自动寻找输入文件 ==============================
def find_file(folder: Path, default_name: str, keyword: str) -> Path:
    """优先按完整文件名寻找；找不到时，再按关键词寻找唯一的 xlsx 文件。"""
    default_path = folder / default_name
    if default_path.exists():
        return default_path

    candidates = [
        path for path in folder.glob("*.xlsx")
        if keyword in path.name
        and not path.name.startswith("~$")
        and path.name != DEFAULT_OUTPUT_NAME
    ]
    if len(candidates) == 1:
        print(f"没有找到默认文件名，自动选择：{candidates[0].name}")
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(
            f"没有找到包含“{keyword}”的 Excel。请把原始 Excel 与 Python 文件放在同一文件夹。"
        )
    raise RuntimeError(
        f"找到多个包含“{keyword}”的 Excel，无法判断读取哪一个："
        + "、".join(path.name for path in candidates)
    )


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """确定参比文件、雷达文件和输出文件的路径。"""
    script_folder = Path(__file__).resolve().parent
    reference_path = (
        Path(args.reference).expanduser().resolve()
        if args.reference
        else find_file(script_folder, DEFAULT_REFERENCE_NAME, "参比平均流速")
    )
    radar_path = (
        Path(args.radar).expanduser().resolve()
        if args.radar
        else find_file(script_folder, DEFAULT_RADAR_NAME, "侧扫雷达平均流速")
    )
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else script_folder / DEFAULT_OUTPUT_NAME
    )

    if not reference_path.exists():
        raise FileNotFoundError(f"找不到参比文件：{reference_path}")
    if not radar_path.exists():
        raise FileNotFoundError(f"找不到雷达文件：{radar_path}")
    if output_path in {reference_path, radar_path}:
        raise ValueError("输出文件不能与原始文件同名，以免覆盖原始数据。")
    return reference_path, radar_path, output_path


# ============================== 模块 4：统一转换 Excel 时间 ==============================
def parse_datetime_series(series: pd.Series, column_name: str) -> pd.Series:
    """
    把 Excel 时间统一转换为 pandas 时间。

    兼容两种常见格式：
    1. 文本时间，例如“2026-08-06 07:00”；
    2. Excel 日期序号，例如 46240.2916667。
    """
    def parse_one(value):
        if pd.isna(value):
            return pd.NaT
        if isinstance(value, (pd.Timestamp, datetime)):
            return pd.Timestamp(value)
        if isinstance(value, (int, float, np.integer, np.floating)):
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(float(value), unit="D")
        return pd.to_datetime(str(value).strip(), errors="coerce")

    parsed = series.map(parse_one)
    if parsed.isna().any():
        # Excel 第一行为标题，因此 DataFrame 索引 0 对应 Excel 第 2 行。
        excel_rows = (parsed[parsed.isna()].index + 2).tolist()
        raise ValueError(f"“{column_name}”存在无法识别的时间，Excel 行号：{excel_rows}")
    return pd.to_datetime(parsed)


# ============================== 模块 5：读取并校验两个 Excel ==============================
def read_and_validate(
    reference_path: Path,
    radar_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    读取源文件并校验数据。

    返回四张表：
    - reference_raw、radar_raw：保持源文件原行序，用于写入“原始数据”工作表；
    - reference、radar：按时间排序，用于插值计算。
    """
    reference_raw = pd.read_excel(reference_path)
    radar_raw = pd.read_excel(radar_path)

    missing_ref = {REF_START, REF_END, REF_SPEED} - set(reference_raw.columns)
    missing_radar = {RADAR_START, RADAR_END, RADAR_SPEED} - set(radar_raw.columns)
    if missing_ref:
        raise ValueError(f"参比文件缺少列：{sorted(missing_ref)}")
    if missing_radar:
        raise ValueError(f"雷达文件缺少列：{sorted(missing_radar)}")

    reference_raw = reference_raw.copy()
    radar_raw = radar_raw.copy()
    reference_raw[REF_START] = parse_datetime_series(reference_raw[REF_START], REF_START)
    reference_raw[REF_END] = parse_datetime_series(reference_raw[REF_END], REF_END)
    radar_raw[RADAR_START] = parse_datetime_series(radar_raw[RADAR_START], RADAR_START)
    radar_raw[RADAR_END] = parse_datetime_series(radar_raw[RADAR_END], RADAR_END)

    reference_raw[REF_SPEED] = pd.to_numeric(reference_raw[REF_SPEED], errors="coerce")
    radar_raw[RADAR_SPEED] = pd.to_numeric(radar_raw[RADAR_SPEED], errors="coerce")
    if reference_raw[REF_SPEED].isna().any():
        raise ValueError("参比文件的“平均流速”存在空值或非数字。")
    if radar_raw[RADAR_SPEED].isna().any():
        raise ValueError("雷达文件的“平均流速(m/s)”存在空值或非数字。")
    if (reference_raw[REF_END] <= reference_raw[REF_START]).any():
        raise ValueError("参比文件中存在结束时间不晚于施测时间的记录。")
    if (radar_raw[RADAR_END] <= radar_raw[RADAR_START]).any():
        raise ValueError("雷达文件中存在结束时间不晚于开始时间的记录。")

    reference = reference_raw.sort_values(REF_START).reset_index(drop=True)
    radar = radar_raw.sort_values(RADAR_START).reset_index(drop=True)

    # 检查雷达时间段是否互相重叠。若重叠，必须先明确重叠段采用哪条记录。
    for index in range(1, len(radar)):
        if radar.loc[index, RADAR_START] < radar.loc[index - 1, RADAR_END]:
            raise ValueError(
                "雷达文件存在互相重叠的时间段："
                f"{radar.loc[index - 1, RADAR_START]}～{radar.loc[index - 1, RADAR_END]} 与 "
                f"{radar.loc[index, RADAR_START]}～{radar.loc[index, RADAR_END]}"
            )

    return reference_raw, radar_raw, reference, radar


# ============================== 模块 6：线性插值的基础计算 ==============================
def linear_value(
    target_time: pd.Timestamp,# 需要计算流速的目标时间
    left_time: pd.Timestamp,# 左侧雷达时刻
    left_speed: float,# 左侧雷达流速
    right_time: pd.Timestamp,# 右侧雷达时刻
    right_speed: float,# 右侧雷达流速
) -> float:
    """
    根据两个锚点计算目标时刻的线性插值流速。

    V(t) = V左 + [(t-t左)/(t右-t左)] × (V右-V左)
    """
    # 1. 计算左右两个雷达时刻的总时间间隔
    total_seconds = (right_time - left_time).total_seconds()
    if total_seconds <= 0:
        raise ValueError("线性插值的右锚点时间必须晚于左锚点时间。")
    # 2. 计算目标时刻在整个时间间隔中的位置比例
    weight = (target_time - left_time).total_seconds() / total_seconds
    # 3. 根据时间比例计算目标时刻的流速
    target_speed = float(left_speed + weight * (right_speed - left_speed))
    return target_speed

# V(t) = V左 + [(t-t左)/(t右-t左)] × (V右-V左) =  V左 + weight × (V右-V左)
# 计算 2026年8月10日16:00—16:20 的雷达流速。
#
# 左锚点：13:00，流速 0.0608 m/s
# 右锚点：17:00，流速 0.2000 m/s
#
# left_time = 13:00    right_time = 17:00    总时间间隔：17:00−13:00=240分钟
#
# 计算16:00的流速：target_start_time = 16:00
# 目标时刻距离左侧：16:00−13:00=180分钟  插值权重：180/240=0.75  V(16:00)=0.0608+0.75×(0.2000−0.0608)=0.1652 m/s
# start_speed = 0.1652
#
# 计算16:20的流速：target_end_time = 16:20
# 目标时刻距离左侧：16:20−13:00=200分钟  插值权重：200/240=0.83333 V(16:20)=0.0608+0.833333×(0.2000−0.0608)=0.1768 m/s
# end_speed = 0.1768
#
# 由于16:00—16:20之间假设流速呈线性变化，这20分钟的平均流速为：V平均=(0.1652+0.1768)/2=0.1710 m/s

# ============================== 模块 7：判断一个小段是直接匹配还是插值 ==============================
def evaluate_small_segment(
    segment_start: pd.Timestamp,
    segment_end: pd.Timestamp,
    radar: pd.DataFrame,
) -> dict:
    """
    计算一个不跨越雷达开始/结束边界的小时间段。

    - 如果小段位于雷达实测时间段内，认为该段流速等于雷达报告的平均流速；
    - 如果小段位于两个雷达时段的空档中，使用前后雷达值进行线性插值。
    """
    midpoint = segment_start + (segment_end - segment_start) / 2

    # 查找是否存在一个雷达时段完整覆盖该小段。
    direct_rows = radar.loc[
        (radar[RADAR_START] <= midpoint) & (radar[RADAR_END] >= midpoint)
    ]
    duration_minutes = (segment_end - segment_start).total_seconds() / 60.0

    if len(direct_rows) == 1:
        radar_row = direct_rows.iloc[0]
        speed = float(radar_row[RADAR_SPEED])
        return {
            "处理方式": "雷达原时段直接采用",
            "左锚点时间": radar_row[RADAR_START],
            "左锚点流速(m/s)": speed,
            "右锚点时间": radar_row[RADAR_END],
            "右锚点流速(m/s)": speed,
            "分段开始流速(m/s)": speed,
            "分段结束流速(m/s)": speed,
            "分段平均流速(m/s)": speed,
            "分段时长(min)": duration_minutes,
            "流速时间积(m/s·min)": speed * duration_minutes,
        }

    # 小段处于空档：寻找空档左侧最近的雷达结束时刻和右侧最近的雷达开始时刻。
    previous_rows = radar.loc[radar[RADAR_END] <= segment_start]
    next_rows = radar.loc[radar[RADAR_START] >= segment_end]
    if previous_rows.empty or next_rows.empty:
        raise ValueError(
            f"时间段 {segment_start:%Y-%m-%d %H:%M}～{segment_end:%Y-%m-%d %H:%M} "
            "超出雷达有效时间范围，程序不进行外推。"
        )

    previous_row = previous_rows.iloc[-1]
    next_row = next_rows.iloc[0]
    left_time = previous_row[RADAR_END]
    right_time = next_row[RADAR_START]
    left_speed = float(previous_row[RADAR_SPEED])
    right_speed = float(next_row[RADAR_SPEED])

    start_speed = linear_value(
        segment_start, left_time, left_speed, right_time, right_speed
    )
    end_speed = linear_value(
        segment_end, left_time, left_speed, right_time, right_speed
    )

    # 线性变化小段的平均值等于首尾流速的算术平均值，也就是梯形积分。
    segment_average = (start_speed + end_speed) / 2.0
    return {
        "处理方式": "相邻雷达时段间线性插值",
        "左锚点时间": left_time,
        "左锚点流速(m/s)": left_speed,
        "右锚点时间": right_time,
        "右锚点流速(m/s)": right_speed,
        "分段开始流速(m/s)": start_speed,
        "分段结束流速(m/s)": end_speed,
        "分段平均流速(m/s)": segment_average,
        "分段时长(min)": duration_minutes,
        "流速时间积(m/s·min)": segment_average * duration_minutes,
    }


# ============================== 模块 8：计算一个参比测次的雷达时段平均流速 ==============================
def calculate_reference_interval(
    sample_no: int,
    reference_start: pd.Timestamp,
    reference_end: pd.Timestamp,
    radar: pd.DataFrame,
) -> tuple[float, list[dict], float, float]:
    """
    把一个参比测验时段按雷达边界拆分，并计算时间加权平均流速。

    例如参比时段为 16:30～17:30，而雷达在 17:00 开始一个实测时段，
    程序会拆成：
        16:30～17:00：空档线性插值；
        17:00～17:30：雷达原时段直接采用。
    """
    if reference_start < radar[RADAR_START].iloc[0]:
        raise ValueError("参比开始时间早于第一条雷达记录，不能外推。")
    if reference_end > radar[RADAR_END].iloc[-1]:
        raise ValueError("参比结束时间晚于最后一条雷达记录，不能外推。")

    # 将位于参比时段内部的所有雷达开始、结束时间加入分界点。
    boundaries = {reference_start, reference_end}
    for value in radar[RADAR_START]:
        if reference_start < value < reference_end:
            boundaries.add(value)
    for value in radar[RADAR_END]:
        if reference_start < value < reference_end:
            boundaries.add(value)
    boundaries = sorted(boundaries)

    rows = []
    total_speed_minutes = 0.0
    direct_minutes = 0.0
    interpolation_minutes = 0.0

    for segment_no, (segment_start, segment_end) in enumerate(
        zip(boundaries[:-1], boundaries[1:]), start=1
    ):
        detail = evaluate_small_segment(segment_start, segment_end, radar)
        detail.update({
            "样本序号": sample_no,
            "分段序号": segment_no,
            "参比分段开始": segment_start,
            "参比分段结束": segment_end,
        })
        rows.append(detail)
        total_speed_minutes += detail["流速时间积(m/s·min)"]

        if detail["处理方式"] == "雷达原时段直接采用":
            direct_minutes += detail["分段时长(min)"]
        else:
            interpolation_minutes += detail["分段时长(min)"]

    total_minutes = (reference_end - reference_start).total_seconds() / 60.0
    radar_average = total_speed_minutes / total_minutes
    return radar_average, rows, direct_minutes, interpolation_minutes


# ============================== 模块 9：逐条生成比测结果 ==============================
def build_results(
    reference: pd.DataFrame,
    radar: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """对所有参比记录进行时间段匹配、插值和误差计算。"""
    result_rows = []
    detail_rows = []

    for index, row in reference.iterrows():
        sample_no = index + 1
        start = row[REF_START]
        end = row[REF_END]
        total_minutes = (end - start).total_seconds() / 60.0

        radar_average, details, direct_minutes, interpolation_minutes = (
            calculate_reference_interval(sample_no, start, end, radar)
        )
        detail_rows.extend(details)

        reference_speed = float(row[REF_SPEED])
        difference = radar_average - reference_speed
        result_row = {
            "样本序号": sample_no,
            "施测时间": start,
            "结束时分": end,
            "施测时长(min)": total_minutes,
        }

        # 保留参比表中的水位、流量和截面积，方便进一步率定分析。
        for column in reference.columns:
            if column not in {REF_START, REF_END, REF_SPEED}:
                result_row[column] = row[column]

        result_row.update({
            "参比平均流速(m/s)": reference_speed,
            "雷达匹配平均流速(m/s)": radar_average,
            "差值(雷达-参比)(m/s)": difference,
            "绝对差值(m/s)": abs(difference),
            "雷达直接覆盖(min)": direct_minutes,
            "线性插值补充(min)": interpolation_minutes,
            "直接覆盖比例": direct_minutes / total_minutes,
            "分段数量": len(details),
            "匹配状态": "有效",
        })
        result_rows.append(result_row)

    detail_columns = [
        "样本序号", "分段序号", "参比分段开始", "参比分段结束", "分段时长(min)",
        "处理方式", "左锚点时间", "左锚点流速(m/s)", "右锚点时间", "右锚点流速(m/s)",
        "分段开始流速(m/s)", "分段结束流速(m/s)", "分段平均流速(m/s)",
        "流速时间积(m/s·min)",
    ]
    return pd.DataFrame(result_rows), pd.DataFrame(detail_rows)[detail_columns]


# ============================== 模块 10：计算比较指标 ==============================
def calculate_statistics(results: pd.DataFrame) -> pd.DataFrame:
    """计算偏差、MAE、RMSE 和相关系数，用于总体评价。"""
    reference_speed = results["参比平均流速(m/s)"].to_numpy(dtype=float)
    radar_speed = results["雷达匹配平均流速(m/s)"].to_numpy(dtype=float)
    errors = radar_speed - reference_speed

    rows = [
        ("有效样本数", len(results), "条"),
        ("平均偏差（雷达-参比）", float(np.mean(errors)), "m/s"),
        ("平均绝对误差 MAE", float(np.mean(np.abs(errors))), "m/s"),
        ("均方根误差 RMSE", float(np.sqrt(np.mean(errors ** 2))), "m/s"),
        ("相关系数 r", float(np.corrcoef(reference_speed, radar_speed)[0, 1]), "—"),
    ]
    return pd.DataFrame(rows, columns=["指标", "数值", "单位"])


# ============================== 模块 11：生成新的 Excel ==============================
def write_excel(
    output_path: Path,
    reference_raw: pd.DataFrame,
    radar_raw: pd.DataFrame,
    details: pd.DataFrame,
    results: pd.DataFrame,
    statistics: pd.DataFrame,
) -> None:
    """生成说明、原始数据、分段明细、比测结果和统计汇总工作表。"""
    workbook = Workbook()
    workbook.remove(workbook.active)

    navy_fill = PatternFill("solid", fgColor="1F4E78")
    blue_fill = PatternFill("solid", fgColor="5B9BD5")
    green_fill = PatternFill("solid", fgColor="E2F0D9")
    white_bold = Font(color="FFFFFF", bold=True)
    thin_line = Side(style="thin", color="D9E2F3")

    def add_table_sheet(sheet_name: str, dataframe: pd.DataFrame):
        worksheet = workbook.create_sheet(sheet_name)
        worksheet.append(list(dataframe.columns))
        for values in dataframe.itertuples(index=False, name=None):
            worksheet.append(list(values))

        for cell in worksheet[1]:
            cell.fill = blue_fill
            cell.font = white_bold
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in worksheet.iter_rows():
            for cell in row:
                cell.border = Border(bottom=thin_line)
                if isinstance(cell.value, (datetime, pd.Timestamp)):
                    cell.number_format = "yyyy-mm-dd hh:mm"
                elif isinstance(cell.value, (float, np.floating)):
                    cell.number_format = "0.0000"

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_number, cells in enumerate(worksheet.columns, start=1):
            max_length = max(len(str(cell.value or "")) for cell in cells)
            worksheet.column_dimensions[get_column_letter(column_number)].width = min(
                max(max_length + 2, 12), 28
            )
        return worksheet

    instruction = workbook.create_sheet("使用说明")
    instruction["A1"] = "雷达时间段平均流速插值比较说明"
    instruction["A1"].fill = navy_fill
    instruction["A1"].font = Font(color="FFFFFF", bold=True, size=14)
    instruction.merge_cells("A1:H1")
    notes = [
        "1. 雷达每条流速是开始时间至结束时间内的平均值，不按瞬时值处理。",
        "2. 参比时段落入雷达实测时段的部分，直接采用雷达平均流速。",
        "3. 两个雷达时段之间的空档，按前一时段末值与后一时段初值进行线性插值。",
        "4. 参比时段跨越雷达边界时自动拆分，最后按分钟加权得到雷达匹配平均流速。",
        "5. 不进行雷达总时间范围以外的外推。",
        "线性公式：V(t)=V左+(t-t左)/(t右-t左)×(V右-V左)",
        "时间加权平均：Σ(各分段平均流速×分段时长)÷参比总时长",
    ]
    for row_no, note in enumerate(notes, start=3):
        instruction.cell(row=row_no, column=1, value=note)
        if row_no >= 8:
            instruction.cell(row=row_no, column=1).fill = green_fill
            instruction.cell(row=row_no, column=1).font = Font(bold=True)
    instruction.column_dimensions["A"].width = 105

    add_table_sheet("参比原始数据", reference_raw)
    add_table_sheet("雷达原始数据", radar_raw)
    add_table_sheet("分段计算明细", details)
    add_table_sheet("插值比测结果", results)
    add_table_sheet("统计汇总", statistics)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


# ============================== 模块 12：把计算结果转换为 JSON ==============================
def dataframe_records(dataframe: pd.DataFrame) -> list[dict]:
    """把时间转换成文字后输出 JSON，避免时间对象无法序列化。"""
    copy = dataframe.copy()
    for column in copy.columns:
        if pd.api.types.is_datetime64_any_dtype(copy[column]):
            copy[column] = copy[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    copy = copy.astype(object).where(pd.notna(copy), None)
    return copy.to_dict(orient="records")


# ============================== 模块 13：主程序入口 ==============================
def main() -> None:
    parser = argparse.ArgumentParser(description="参比与雷达时间段平均流速插值比较")
    parser.add_argument("--reference", help="参比平均流速 Excel；不填写则自动寻找")
    parser.add_argument("--radar", help="侧扫雷达平均流速 Excel；不填写则自动寻找")
    parser.add_argument("--output", help=f"输出 Excel；默认生成 {DEFAULT_OUTPUT_NAME}")
    parser.add_argument("--json-out", help="可选：输出 JSON 中间结果，便于复核")
    args = parser.parse_args()

    reference_path, radar_path, output_path = resolve_paths(args)
    print(f"正在读取参比文件：{reference_path}")
    print(f"正在读取雷达文件：{radar_path}")

    reference_raw, radar_raw, reference, radar = read_and_validate(
        reference_path, radar_path
    )
    results, details = build_results(reference, radar)
    statistics = calculate_statistics(results)
    write_excel(output_path, reference_raw, radar_raw, details, results, statistics)

    if args.json_out:
        payload = {
            "reference_raw": dataframe_records(reference_raw),
            "radar_raw": dataframe_records(radar_raw),
            "details": dataframe_records(details),
            "results": dataframe_records(results),
            "statistics": dataframe_records(statistics),
        }
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"处理完成：共 {len(results)} 条参比记录。")
    print(f"结果文件：{output_path}")


if __name__ == "__main__":
    main()
