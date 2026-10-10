from __future__ import annotations

import argparse
import math
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


REQUIRED_COLUMNS = {
    "序号": "序号",
    "雷达速度vr": "雷达速度Vr",
    "参比速度vbar": "参比速度Vbar",
    "雷达速度拟合后": "雷达速度拟合后",
}


def normalize_header(value: object) -> str:
    """统一表头格式，忽略空格、换行及英文字母大小写。"""
    if value is None:
        return ""
    return "".join(str(value).split()).lower()


def choose_input_file() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askopenfilename(
        title="请选择逐个样本拟合结果 Excel",
        filetypes=[("Excel 工作簿", "*.xlsx"), ("所有文件", "*.*")],
    )
    root.destroy()
    return Path(selected) if selected else None


def choose_output_file(default_name: str) -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.asksaveasfilename(
        title="请选择结果保存位置",
        defaultextension=".xlsx",
        initialfile=default_name,
        filetypes=[("Excel 工作簿", "*.xlsx")],
    )
    root.destroy()
    return Path(selected) if selected else None


def find_columns(ws) -> dict[str, int]:
    actual = {
        normalize_header(cell.value): cell.column
        for cell in ws[1]
        if cell.value is not None
    }
    result: dict[str, int] = {}
    missing: list[str] = []
    for normalized, display_name in REQUIRED_COLUMNS.items():
        if normalized not in actual:
            missing.append(display_name)
        else:
            result[display_name] = actual[normalized]
    if missing:
        raise ValueError("缺少必要列：" + "、".join(missing))
    return result


def to_number(value: object, field_name: str, excel_row: int) -> float:
    if value is None or value == "":
        raise ValueError(f"第 {excel_row} 行的“{field_name}”为空")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"第 {excel_row} 行的“{field_name}”不是有效数字：{value!r}"
        ) from exc


def uncertainty(errors: list[float]) -> float:
    """按 2*sqrt(SUMSQ/(n-2)) 计算随机不确定度。"""
    n = len(errors)
    if n <= 2:
        raise ValueError("有效样本数必须大于 2，才能按 n-2 计算随机不确定度")
    return 2.0 * math.sqrt(sum(item * item for item in errors) / (n - 2))


def read_samples(input_path: Path):
    workbook = load_workbook(input_path, data_only=True)
    ws = workbook.active
    columns = find_columns(ws)
    samples = []

    for row in range(2, ws.max_row + 1):
        serial = ws.cell(row, columns["序号"]).value
        if serial is None or str(serial).strip() == "":
            continue

        vr = to_number(ws.cell(row, columns["雷达速度Vr"]).value, "雷达速度Vr", row)
        vbar = to_number(ws.cell(row, columns["参比速度Vbar"]).value, "参比速度Vbar", row)
        fitted = to_number(
            ws.cell(row, columns["雷达速度拟合后"]).value,
            "雷达速度拟合后",
            row,
        )

        if fitted == 0:
            raise ValueError(f"第 {row} 行拟合速度为 0，无法计算相对偏离度")

        relative_deviation = (vbar - fitted) / fitted
        log_deviation = None
        log_note = ""
        if vbar > 0 and fitted > 0:
            log_deviation = math.log(vbar) - math.log(fitted)
        else:
            log_note = "Vbar或拟合速度≤0，无法取自然对数，未纳入Ln法计算"

        samples.append(
            (serial, vr, vbar, fitted, relative_deviation, log_deviation, log_note)
        )

    if not samples:
        raise ValueError("没有读取到有效样本")
    return ws.title, samples


def write_result(output_path: Path, source_sheet: str, samples) -> tuple[float, float, int, int]:
    relative_errors = [row[4] for row in samples]
    log_errors = [row[5] for row in samples if row[5] is not None]
    relative_u = uncertainty(relative_errors)
    log_u = uncertainty(log_errors)

    wb = Workbook()
    ws = wb.active
    ws.title = "随机不确定度计算"

    headers = [
        "序号",
        "雷达速度Vr",
        "参比速度Vbar",
        "雷达速度拟合后",
        "流速相对偏离度\n(Vbar-V拟合)/V拟合",
        "流速\nln(Vbar)-ln(V拟合)",
        "备注",
    ]
    ws.append(headers)
    for sample in samples:
        ws.append(sample)

    last_data_row = len(samples) + 1
    result_start_row = last_data_row + 3
    ws.cell(result_start_row, 4, "流速——随机不确定度使用相对偏离度计算")
    ws.cell(result_start_row, 5, relative_u)
    ws.cell(result_start_row + 1, 4, "流速——随机不确定度使用Ln方法计算")
    ws.cell(result_start_row + 1, 5, log_u)
    ws.cell(result_start_row + 3, 4, "计算公式")
    ws.cell(result_start_row + 3, 5, "2×√[Σ(e²)/(n-2)]")
    ws.cell(result_start_row + 4, 4, "数据来源工作表")
    ws.cell(result_start_row + 4, 5, source_sheet)
    ws.cell(result_start_row + 5, 4, "相对偏离度有效样本数")
    ws.cell(result_start_row + 5, 5, len(relative_errors))
    ws.cell(result_start_row + 6, 4, "Ln法有效样本数")
    ws.cell(result_start_row + 6, 5, len(log_errors))

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    thin = Side(style="thin", color="A6A6A6")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row in ws.iter_rows(min_row=2, max_row=last_data_row, min_col=1, max_col=7):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row in range(2, last_data_row + 1):
        for col in (2, 3, 4):
            ws.cell(row, col).number_format = "0.000000000"
        for col in (5, 6):
            ws.cell(row, col).number_format = "0.00%"

    for row in (result_start_row, result_start_row + 1):
        ws.cell(row, 4).font = Font(bold=True)
        ws.cell(row, 5).font = Font(bold=True, color="C00000")
        ws.cell(row, 5).number_format = "0.00%"

    widths = {1: 10, 2: 17, 3: 18, 4: 20, 5: 28, 6: 25, 7: 42}
    for col, width in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[1].height = 45
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{last_data_row}"
    ws.sheet_view.showGridLines = False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return relative_u, log_u, len(relative_errors), len(log_errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="计算流速随机不确定度并生成Excel结果表")
    parser.add_argument("--input", type=Path, help="输入xlsx；不填写时弹窗选择")
    parser.add_argument("--output", type=Path, help="输出xlsx；不填写时弹窗选择")
    args = parser.parse_args()

    input_path = args.input or choose_input_file()
    if input_path is None:
        print("已取消选择，程序结束。")
        return
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在：{input_path}")

    default_name = f"{input_path.stem}_随机不确定度计算结果.xlsx"
    output_path = args.output or choose_output_file(default_name)
    if output_path is None:
        print("已取消保存，程序结束。")
        return

    try:
        source_sheet, samples = read_samples(input_path)
        relative_u, log_u, relative_n, log_n = write_result(
            output_path, source_sheet, samples
        )
        summary = (
            f"计算完成！\n\n"
            f"相对偏离度法：{relative_u:.2%}（n={relative_n}）\n"
            f"Ln方法：{log_u:.2%}（n={log_n}）\n\n"
            f"结果文件：{output_path}"
        )
        print(summary)
        if args.input is None and args.output is None:
            root = Tk()
            root.withdraw()
            messagebox.showinfo("完成", summary)
            root.destroy()
    except Exception as exc:
        if args.input is None:
            root = Tk()
            root.withdraw()
            messagebox.showerror("计算失败", str(exc))
            root.destroy()
        raise


if __name__ == "__main__":
    main()
