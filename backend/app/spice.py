"""Non-executing SPICE subset. Syntax and conversion live exclusively in Python."""
from __future__ import annotations

import math
import re

from pydantic import ValidationError

from .models.netlist import MAX_ELEMENTS, ACSettings, DCSettings, NetlistElement, SimulateRequest, TransientSettings
from .models.spice import ParsedSpice

SCALES = dict(t=1e12, g=1e9, meg=1e6, k=1e3, m=1e-3, u=1e-6, n=1e-9, p=1e-12, f=1e-15, mil=25.4e-6)
OP_PARAMS = dict(A0="open_loop_gain", GBW="gain_bandwidth", RIN="input_resistance", ROUT="output_resistance",
                 VMIN="output_min", VMAX="output_max", SR="slew_rate", VOS="input_offset")
KINDS = dict(R="resistor", C="capacitor", L="inductor", V="voltage_source", I="current_source",
             X="opamp", D="diode", E="vcvs", G="vccs", F="cccs", H="ccvs")


def spice_number(token: str) -> float:
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)(meg|mil|[tgkmunpf])?([a-zΩ]*)", token, re.I)
    if not match:
        raise ValueError(f"无效数值「{token}」")
    result = float(match[1]) * SCALES.get((match[2] or "").lower(), 1)
    if not math.isfinite(result):
        raise ValueError(f"数值超出范围「{token}」")
    return result


def _positive(token: str) -> float:
    value = spice_number(token)
    if value <= 0:
        raise ValueError(f"数值必须为正：「{token}」")
    return value


def _node(token: str) -> str:
    if not re.fullmatch(r"[a-z0-9_][a-z0-9_.:-]*", token, re.I):
        raise ValueError(f"无效节点名「{token}」")
    return "GND" if token.upper() in ("0", "GND") else token.upper()


def _analysis(tokens):
    command = tokens[0].upper()
    if command == ".OP":
        if len(tokens) != 1:
            raise ValueError("格式：.op")
        return DCSettings(mode="dc")
    if command == ".AC":
        if len(tokens) != 5 or tokens[1].upper() not in ("DEC", "LIN"):
            raise ValueError("格式：.ac dec|lin 点数 起始频率 结束频率")
        points = _positive(tokens[2])
        if not points.is_integer() or not 2 <= points <= 10000:
            raise ValueError("AC 点数须为 2～10000 的整数")
        start, stop = _positive(tokens[3]), _positive(tokens[4])
        if stop < start:
            raise ValueError("结束频率不能小于起始频率")
        if tokens[1].upper() == "DEC" and (math.log10(stop) - math.log10(start)) * points > 200000:
            raise ValueError("AC 扫频最多 200000 点")
        return ACSettings(mode="ac", f_start=start, f_stop=stop, points_per_decade=int(points),
                          sweep_type="log" if tokens[1].upper() == "DEC" else "linear")
    if len(tokens) not in (3, 4):
        raise ValueError("格式：.tran 步长 结束时间 [0]")
    step, stop = _positive(tokens[1]), spice_number(tokens[2])
    start = spice_number(tokens[3]) if len(tokens) == 4 else 0
    if start != 0:
        raise ValueError("当前 .tran 仅支持开始时间 0，避免与 SPICE 的输出延迟语义混淆")
    return TransientSettings(mode="transient", t_step=step, t_stop=stop, t_start=0)


def _element(tokens) -> NetlistElement:
    name = tokens[0].upper()
    prefix = name[0]
    if prefix not in KINDS:
        raise ValueError(f"不支持元件「{tokens[0]}」")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name, re.I):
        raise ValueError("元件名称只接受字母、数字和下划线")
    if len(tokens) < (5 if prefix == "X" else 4):
        raise ValueError("缺少节点或元件值")
    values = dict(id=name, type=KINDS[prefix], node_a=_node(tokens[1]), node_b=_node(tokens[2]))
    if prefix in "RCL":
        if len(tokens) != 4:
            raise ValueError("R/C/L 格式：名称 节点A 节点B 数值")
        values["value"] = _positive(tokens[3])
    elif prefix == "D":
        if len(tokens) < 3:
            raise ValueError("二极管格式：D名称 阳极 阴极 [Is=…] [N=…]")
        for token in tokens[3:]:
            pair = token.split("=")
            key = pair[0].upper()
            if len(pair) != 2 or key not in ("IS", "N") or key in values:
                raise ValueError(f"未知或重复二极管参数「{token}」")
            values["diode_is" if key == "IS" else "diode_n"] = _positive(pair[1])
    elif prefix in "EG":
        if len(tokens) != 6:
            raise ValueError(f"{prefix} 源格式：名称 n+ n- 控制+ 控制- 增益")
        values["control_node_a"] = _node(tokens[3])
        values["control_node_b"] = _node(tokens[4])
        values["value"] = spice_number(tokens[5])
    elif prefix in "FH":
        if len(tokens) != 5:
            raise ValueError(f"{prefix} 源格式：名称 n+ n- 控制电压源名 增益")
        values["control_element"] = tokens[3].upper()
        values["value"] = spice_number(tokens[4])
    elif prefix == "X":
        if tokens[4].upper() != "CS_OPAMP":
            raise ValueError("当前仅支持内置三端模型 CS_OPAMP；暂不支持厂商子电路")
        values["node_out"] = _node(tokens[3])
        seen = set()
        for token in tokens[5:]:
            pair = token.split("=")
            key = pair[0].upper()
            if len(pair) != 2 or key not in OP_PARAMS or key in seen:
                raise ValueError(f"未知或重复运放参数「{token}」")
            seen.add(key)
            values[OP_PARAMS[key]] = spice_number(pair[1]) if key in ("VMIN", "VMAX", "VOS") else _positive(pair[1])
    else:
        i, seen = 3, set()
        if tokens[i].upper() not in ("DC", "AC"):
            values["value"] = spice_number(tokens[i])
            seen.add("DC")
            i += 1
        while i < len(tokens):
            key = tokens[i].upper()
            i += 1
            if key not in ("DC", "AC") or key in seen or i >= len(tokens):
                raise ValueError("源支持 [DC 数值] [AC 幅值 [相位]]；暂不支持 SIN/PULSE 或重复指定")
            seen.add(key)
            if key == "DC":
                values["value"] = spice_number(tokens[i])
                i += 1
            else:
                values["ac_amplitude"] = spice_number(tokens[i])
                i += 1
                if i < len(tokens) and tokens[i].upper() not in ("DC", "AC"):
                    values["ac_phase"] = spice_number(tokens[i])
                    i += 1
        values.setdefault("ac_amplitude", 0)
    return NetlistElement(**values)


def parse_spice(text: str) -> ParsedSpice:
    if len(text.encode("utf-8")) > 1_000_000:
        raise ValueError("文件不能超过 1 MB")
    text = text.removeprefix("\ufeff")
    first = text.lstrip().splitlines()
    title = (first[0][1:].strip() if first and first[0].startswith("*") else "") or "文本电路"
    lines: list[tuple[int, str]] = []
    for number, original in enumerate(text.splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("*"):
            continue
        line = re.split(r"[;$]", line, maxsplit=1)[0].strip()
        if not line:
            continue
        if line.startswith("+"):
            if not lines:
                raise ValueError(f"第 {number} 行：续行前没有内容")
            previous, content = lines[-1]
            lines[-1] = (previous, content + " " + line[1:].strip())
        else:
            lines.append((number, line))
    elements: list[NetlistElement] = []
    labels: set[str] = set()
    settings, ended, analysis = DCSettings(mode="dc"), False, False
    for number, line in lines:
        try:
            tokens = line.split()
            command = tokens[0].upper()
            if ended:
                raise ValueError(".end 后不能再有语句")
            if command == ".TITLE":
                title = " ".join(tokens[1:]) or title
            elif command == ".END":
                if len(tokens) != 1:
                    raise ValueError(".end 不接受参数")
                ended = True
            elif command in (".OP", ".AC", ".TRAN"):
                if analysis:
                    raise ValueError("一次只支持一种分析命令")
                settings, analysis = _analysis(tokens), True
            elif command.startswith("."):
                raise ValueError(f"暂不支持 {tokens[0]}；不会忽略或执行文件引用、控制脚本及任意模型")
            else:
                if command in labels:
                    raise ValueError(f"元件名称重复：{tokens[0]}")
                if len(elements) >= MAX_ELEMENTS:
                    raise ValueError(f"最多支持 {MAX_ELEMENTS} 个元件")
                elements.append(_element(tokens))
                labels.add(command)
        except ValidationError as exc:
            message = "; ".join(error["msg"] for error in exc.errors())
            raise ValueError(f"第 {number} 行：{message}") from exc
        except ValueError as exc:
            raise ValueError(f"第 {number} 行：{exc}") from exc
    if not elements:
        raise ValueError("没有可仿真的元件")
    if not any("GND" in (el.node_a, el.node_b, el.node_out) for el in elements):
        raise ValueError("必须有接地节点 0（或 GND）")
    return ParsedSpice(title=title, request=SimulateRequest(elements=elements, settings=settings))


def export_spice(request: SimulateRequest, title: str = "Circuit Simulator") -> str:
    node_origins: dict[str, str] = {}

    def net(value):
        if value == request.ground_node:
            return "0"
        normalized = _node(value)
        if normalized == "GND":
            raise ValueError(f"节点「{value}」不是当前参考地，不能导出为 SPICE 接地别名")
        previous = node_origins.get(normalized)
        if previous is not None and previous != value:
            raise ValueError(f"节点「{previous}」与「{value}」在 SPICE 中大小写相同，导出会改变连接")
        node_origins[normalized] = value
        return normalized

    def num(value):
        if not math.isfinite(value):
            raise ValueError("电路包含无效数值")
        return format(value, ".17g")

    lines = ["* " + title.replace("\r", " ").replace("\n", " ")]
    names = set()
    prefixes = {kind: prefix for prefix, kind in KINDS.items()}
    for el in request.elements:
        if el.type == "ground":
            continue
        prefix = prefixes[el.type]
        name = el.id.upper() if el.id.upper().startswith(prefix) else prefix + el.id.upper()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name, re.I) or name in names:
            raise ValueError(f"元件名称无效或导出后重复：{name}")
        names.add(name)
        pins = f"{net(el.node_a)} {net(el.node_b)}"
        if el.type == "opamp":
            params = " ".join(f"{key}={num(getattr(el, field))}" for key, field in OP_PARAMS.items())
            lines.append(f"{name} {pins} {net(el.node_out)} CS_OPAMP {params}")
        elif el.type == "diode":
            lines.append(f"{name} {pins} IS={num(el.diode_is)} N={num(el.diode_n)}")
        elif el.type in ("vcvs", "vccs"):
            lines.append(f"{name} {pins} {net(el.control_node_a)} {net(el.control_node_b)} {num(el.value)}")
        elif el.type in ("cccs", "ccvs"):
            lines.append(f"{name} {pins} {el.control_element} {num(el.value)}")
        elif el.type in ("voltage_source", "current_source"):
            if el.source_waveform != "dc":
                raise ValueError(f"{el.id}：当前文本格式尚不支持 {el.source_waveform} 波形，导出已停止")
            amp = el.ac_amplitude if el.ac_amplitude is not None else el.value
            lines.append(f"{name} {pins} DC {num(el.value)} AC {num(amp)} {num(el.ac_phase)}")
        else:
            lines.append(f"{name} {pins} {num(el.value)}")
    if any(el.type == "opamp" for el in request.elements):
        lines[1:1] = ["* CS_OPAMP is a built-in application model, not a standard SPICE device.",
                      "* External simulators require a matching .SUBCKT model library."]
    settings = request.settings
    if settings.mode == "dc":
        lines.append(".op")
    elif settings.mode == "ac":
        sweep = "dec" if settings.sweep_type == "log" else "lin"
        lines.append(f".ac {sweep} {settings.points_per_decade} {num(settings.f_start)} {num(settings.f_stop)}")
    else:
        if settings.t_start != 0:
            raise ValueError(".tran 导出仅支持开始时间 0")
        if settings.method != "trapezoidal":
            raise ValueError("文本导出暂只支持梯形积分；请先切换积分方法，以免丢失设置")
        lines.append(f".tran {num(settings.t_step)} {num(settings.t_stop)} 0")
    lines.append(".end")
    text = "\n".join(lines) + "\n"
    # Detect case-folded node/name collisions or unsupported exported content before returning.
    parse_spice(text)
    return text
