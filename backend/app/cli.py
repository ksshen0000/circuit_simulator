"""Local Python CLI: no web server, database, frontend or Node.js required."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
from contextlib import nullcontext
from .models.netlist import SimulateRequest
from .spice import parse_spice, export_spice
from .simulation.engine import run_simulation


def write_csv(result, stream):
    axis = {"dc": "point", "ac": "frequency_Hz", "transient": "time_s"}[result.mode]
    columns = {}
    if result.mode == "ac":
        for prefix, magnitudes, phases in (
            ("V", result.node_voltages_mag, result.node_voltages_phase),
            ("I", result.branch_currents_mag, result.branch_currents_phase),
        ):
            for name, values in magnitudes.items():
                columns[f"{prefix}({name})_mag"] = values
                columns[f"{prefix}({name})_phase_deg"] = phases[name]
    else:
        columns.update({f"V({key})_V": value for key, value in result.node_voltages.items()})
        columns.update({f"I({key})_A": value for key, value in result.branch_currents.items()})
    writer = csv.writer(stream)
    writer.writerow([axis, *columns])
    for index, x in enumerate(result.x_values):
        writer.writerow([x, *(values[index] for values in columns.values())])


def main(argv=None):
    parser = argparse.ArgumentParser(description="本地电路仿真：SPICE/JSON → JSON/CSV，无需启动服务")
    parser.add_argument("input", help="输入 .cir/.sp 或网表 .json；- 表示标准输入")
    parser.add_argument("--input-format", choices=("spice", "json"), help="默认根据扩展名判断；stdin 默认 SPICE")
    parser.add_argument("--format", choices=("json", "csv"), default="json", help="仿真结果格式")
    parser.add_argument("-o", "--output", help="输出文件；默认标准输出")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--parse-only", action="store_true", help="只解析，输出网表 JSON")
    operation.add_argument("--export-spice", action="store_true", help="将输入网表导出为 SPICE 文本")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            text = sys.stdin.read(1_000_001)
        else:
            path = Path(args.input)
            if path.stat().st_size > 1_000_000:
                raise ValueError("输入文件不能超过 1 MB")
            text = path.read_text(encoding="utf-8-sig")
        if len(text.encode("utf-8")) > 1_000_000:
            raise ValueError("输入文件不能超过 1 MB")
        kind = args.input_format or ("json" if args.input.lower().endswith(".json") else "spice")
        if kind == "json":
            request, title = SimulateRequest.model_validate_json(text), "Circuit Simulator"
        else:
            parsed = parse_spice(text)
            request, title = parsed.request, parsed.title
        # Finish calculation/validation before opening the destination file.
        result = None
        if args.parse_only:
            output = request.model_dump_json(indent=2) + "\n"
        elif args.export_spice:
            output = export_spice(request, title)
        else:
            result = run_simulation(request)
            output = result.model_dump_json(indent=2) + "\n" if args.format == "json" else None
        with (open(args.output, "w", encoding="utf-8", newline="") if args.output else nullcontext(sys.stdout)) as stream:
            if output is None:
                write_csv(result, stream)
            else:
                stream.write(output)
        return 0
    except (ValueError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
