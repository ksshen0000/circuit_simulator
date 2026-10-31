"""Non-executing SPICE subset. Syntax and conversion live exclusively in Python."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from .models.netlist import MAX_ELEMENTS, ACSettings, DCSettings, NetlistElement, SimulateRequest, TransientSettings
from .models.spice import ParsedSpice
from .simulation.sources import ac_amplitude, dc_value
from .spice_expr import ParameterTable, spice_number, split_tokens

OP_PARAMS = dict(A0="open_loop_gain", GBW="gain_bandwidth", RIN="input_resistance", ROUT="output_resistance",
                 VMIN="output_min", VMAX="output_max", SR="slew_rate", VOS="input_offset")
KINDS = dict(R="resistor", C="capacitor", L="inductor", V="voltage_source", I="current_source",
             X="opamp", D="diode", E="vcvs", G="vccs", F="cccs", H="ccvs", M="mosfet")
MOS_PARAMS = dict(VTO="mos_vto", KP="mos_kp", LAMBDA="mos_lambda", CGSO="mos_cgs", CGDO="mos_cgd",
                  CGS="mos_cgs", CGD="mos_cgd")
DIODE_PARAMS = dict(IS="diode_is", N="diode_n")


@dataclass
class ModelCard:
    name: str
    kind: str
    params: dict[str, str] = field(default_factory=dict)
    line: int = 0


def _node(token: str) -> str:
    if not re.fullmatch(r"[a-z0-9_][a-z0-9_.:-]*", token, re.I):
        raise ValueError(f"无效节点名「{token}」")
    return "GND" if token.upper() in ("0", "GND") else token.upper()


def _num(token: str, params: ParameterTable) -> float:
    return spice_number(params.substitute(token))


def _positive(token: str, params: ParameterTable) -> float:
    value = _num(token, params)
    if value <= 0:
        raise ValueError(f"数值必须为正：「{token}」")
    return value


def _split_args(inner: str) -> list[str]:
    """Split function arguments on commas/whitespace outside nested groups."""
    args: list[str] = []
    current: list[str] = []
    depth = 0
    for char in inner:
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth = max(0, depth - 1)
        if depth == 0 and (char.isspace() or char == ","):
            if current:
                args.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        args.append("".join(current))
    return args


def _call_args(token: str, name: str) -> list[str]:
    upper = token.upper()
    if not upper.startswith(name + "(") or not token.endswith(")"):
        raise ValueError(f"格式：{name}(参数 …)")
    return _split_args(token[len(name) + 1:-1].strip())


def _options(tokens, params: ParameterTable, values: dict[str, float]) -> None:
    allowed = {"RELTOL": "reltol", "ABSTOL": "abstol"}
    for token in _split_args(" ".join(tokens[1:])):
        pair = token.split("=", 1)
        key = pair[0].upper()
        if len(pair) != 2 or key not in allowed:
            raise ValueError(f"不支持的 .options 项「{token}」；当前支持 RELTOL、ABSTOL")
        values[allowed[key]] = _positive(pair[1], params)


def _analysis(tokens, params: ParameterTable):
    command = tokens[0].upper()
    if command == ".OP":
        if len(tokens) != 1:
            raise ValueError("格式：.op")
        return DCSettings(mode="dc")
    if command == ".AC":
        if len(tokens) != 5 or tokens[1].upper() not in ("DEC", "LIN"):
            raise ValueError("格式：.ac dec|lin 点数 起始频率 结束频率")
        points = _positive(tokens[2], params)
        sweep = tokens[1].upper()
        limit = 10000 if sweep == "DEC" else 200000
        if not points.is_integer() or not 2 <= points <= limit:
            raise ValueError(f"AC 点数须为 2～{limit} 的整数")
        start, stop = _positive(tokens[3], params), _positive(tokens[4], params)
        if stop < start:
            raise ValueError("结束频率不能小于起始频率")
        if tokens[1].upper() == "DEC" and (math.log10(stop) - math.log10(start)) * points > 200000:
            raise ValueError("AC 扫频最多 200000 点")
        return ACSettings(mode="ac", f_start=start, f_stop=stop, points_per_decade=int(points),
                          sweep_type="log" if tokens[1].upper() == "DEC" else "linear")
    if len(tokens) not in (3, 4):
        raise ValueError("格式：.tran 步长 结束时间 [0]")
    step, stop = _positive(tokens[1], params), _num(tokens[2], params)
    start = _num(tokens[3], params) if len(tokens) == 4 else 0
    if start != 0:
        raise ValueError("当前 .tran 仅支持开始时间 0，避免与 SPICE 的输出延迟语义混淆")
    return TransientSettings(mode="transient", t_step=step, t_stop=stop, t_start=0)


def _parse_param_line(line: str, params: ParameterTable) -> None:
    parts = line.split(None, 1)
    text = parts[1] if len(parts) > 1 else ""
    if not text.strip():
        raise ValueError(".param 缺少参数定义")
    index = 0
    while index < len(text):
        while index < len(text) and (text[index].isspace() or text[index] == ","):
            index += 1
        if index >= len(text):
            break
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", text[index:])
        if not match:
            raise ValueError(f".param 参数名无效：「{text[index:]}」")
        name = match.group(0)
        index += len(name)
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text) or text[index] != "=":
            raise ValueError(f".param {name} 缺少等号")
        index += 1
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "{":
            start, depth = index, 0
            while index < len(text):
                if text[index] == "{":
                    depth += 1
                elif text[index] == "}":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                index += 1
            else:
                raise ValueError(f".param {name} 的花括号未闭合")
            expression = text[start:index]
        else:
            start = index
            depth = 0
            while index < len(text):
                char = text[index]
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth = max(0, depth - 1)
                elif depth == 0:
                    if char == ",":
                        break
                    # A following ``name=`` starts the next assignment; any
                    # other whitespace belongs to the current expression.
                    if char.isspace() and re.match(
                        r"\s+[A-Za-z_][A-Za-z0-9_]*\s*=", text[index:],
                    ):
                        break
                index += 1
            expression = text[start:index].strip()
        if not expression:
            raise ValueError(f".param {name} 缺少表达式")
        params.define(name, expression)


def _parse_model_line(line: str, models: dict[str, ModelCard], number: int) -> None:
    tokens = split_tokens(line)
    if len(tokens) < 3:
        raise ValueError("格式：.model 名称 NMOS|PMOS|D (参数=值 …)")
    name, kind = tokens[1].upper(), tokens[2].upper()
    if kind in ("NMOS", "PMOS"):
        kind = kind.lower()
    elif kind in ("D", "DIODE"):
        kind = "diode"
    else:
        raise ValueError(f"不支持的模型类型「{tokens[2]}」；目前支持 NMOS、PMOS 和 D")
    if name in models:
        raise ValueError(f"模型名称重复：{tokens[1]}")
    body = " ".join(tokens[3:]).strip()
    if body.startswith("(") and body.endswith(")"):
        body = body[1:-1].strip()
    params: dict[str, str] = {}
    for token in _split_args(body):
        pair = token.split("=", 1)
        if len(pair) != 2:
            raise ValueError(f"模型参数应为 KEY=VALUE：「{token}」")
        key = pair[0].upper()
        if key in params:
            raise ValueError(f"模型参数重复：{pair[0]}")
        params[key] = pair[1]
    models[name] = ModelCard(name=name, kind=kind, params=params, line=number)


def _resolve_models(models: dict[str, ModelCard], params: ParameterTable) -> dict[str, dict]:
    resolved: dict[str, dict] = {}
    for name, card in models.items():
        values: dict[str, float | str] = {}
        for key, expression in card.params.items():
            try:
                value = _num(expression, params)
            except ValueError as exc:
                raise ValueError(f"第 {card.line} 行：模型 {name} 的参数 {key}：{exc}") from exc
            if card.kind in ("nmos", "pmos"):
                if key == "LEVEL":
                    if value != 1:
                        raise ValueError(f"第 {card.line} 行：模型 {name} 仅支持 MOSFET LEVEL=1")
                    continue
                field_name = MOS_PARAMS.get(key)
                if field_name is None:
                    raise ValueError(f"第 {card.line} 行：模型 {name} 不支持 MOSFET 参数 {key}")
            else:
                field_name = DIODE_PARAMS.get(key)
                if field_name is None:
                    raise ValueError(f"第 {card.line} 行：模型 {name} 不支持二极管参数 {key}")
            if field_name in values:
                raise ValueError(f"第 {card.line} 行：模型 {name} 参数 {key} 与已有参数重复")
            values[field_name] = value
        resolved[name] = {"kind": card.kind, "values": values}
    return resolved


def _source(tokens, params: ParameterTable) -> dict:
    values: dict = {}
    seen: set[str] = set()
    dc_explicit = False
    dc_specified_value = 0.0
    waveform: str | None = None
    index = 3
    while index < len(tokens):
        token = tokens[index]
        upper = token.upper()
        if upper == "DC":
            if "DC" in seen or index + 1 >= len(tokens):
                raise ValueError("DC 只能指定一次，且必须带数值")
            dc_specified_value = _num(tokens[index + 1], params)
            dc_explicit = True
            # For PULSE, ``value`` is the high level, so a trailing DC card
            # must not overwrite it.
            if waveform != "pulse":
                values["value"] = dc_specified_value
            seen.add("DC")
            index += 2
        elif upper == "AC":
            if "AC" in seen or index + 1 >= len(tokens):
                raise ValueError("AC 只能指定一次，且必须带幅值")
            values["ac_amplitude"] = _num(tokens[index + 1], params)
            seen.add("AC")
            index += 2
            if index < len(tokens) and not _is_source_control(tokens[index]):
                values["ac_phase"] = _num(tokens[index], params)
                index += 1
        elif upper.startswith("SIN("):
            if waveform is not None:
                raise ValueError("独立源只能指定一种波形")
            args = _call_args(token, "SIN")
            if not 3 <= len(args) <= 6:
                raise ValueError("SIN 格式：SIN(偏移 幅值 频率 [延迟 [阻尼 [相位]]])")
            numbers = [_num(arg, params) for arg in args]
            values.update(
                source_waveform="sine", sine_offset=numbers[0], sine_amplitude=numbers[1],
                sine_frequency=numbers[2],
                sine_delay=numbers[3] if len(numbers) > 3 else 0.0,
                sine_damping=numbers[4] if len(numbers) > 4 else 0.0,
                sine_phase=numbers[5] if len(numbers) > 5 else 0.0,
            )
            waveform = "sine"
            index += 1
        elif upper.startswith("PULSE("):
            if waveform is not None:
                raise ValueError("独立源只能指定一种波形")
            args = _call_args(token, "PULSE")
            if not 2 <= len(args) <= 7:
                raise ValueError("PULSE 格式：PULSE(低值 高值 [延迟 上升 下降 宽度 周期])")
            numbers = [_num(arg, params) for arg in args]
            period = numbers[6] if len(numbers) > 6 else 1.0
            width = numbers[5] if len(numbers) > 5 else period / 2
            values.update(
                source_waveform="pulse", pulse_low=numbers[0], value=numbers[1],
                pulse_delay=numbers[2] if len(numbers) > 2 else 0.0,
                pulse_rise=numbers[3] if len(numbers) > 3 else 0.0,
                pulse_fall=numbers[4] if len(numbers) > 4 else 0.0,
                pulse_width=width, pulse_period=period,
            )
            if values["pulse_delay"] < 0 or values["pulse_rise"] < 0 or values["pulse_fall"] < 0:
                raise ValueError("PULSE 的延迟和边沿时间不能为负")
            if period <= 0 or width <= 0:
                raise ValueError("PULSE 的周期和宽度必须为正")
            if values["pulse_rise"] + width + values["pulse_fall"] > period:
                raise ValueError("PULSE 的上升 + 宽度 + 下降时间不能超过周期")
            waveform = "pulse"
            index += 1
        elif upper.startswith(("EXP(", "PWL(", "SFFM(")):
            raise ValueError(f"暂不支持波形「{token}」；当前支持 DC、SIN 和 PULSE")
        elif index == 3 and not values and "DC" not in seen and "AC" not in seen:
            # SPICE allows a bare value as the DC specification.
            values["value"] = _num(token, params)
            dc_specified_value = values["value"]
            dc_explicit = True
            seen.add("DC")
            index += 1
        else:
            raise ValueError("源支持 [DC 数值] [AC 幅值 [相位]] [SIN(...) | PULSE(...)]")
    if waveform is not None:
        # SPICE waveform sources use 0 V/A as the default DC operating point
        # unless an explicit DC value was supplied.
        values["dc_value"] = dc_specified_value if dc_explicit else 0.0
    values.setdefault("ac_amplitude", 0)
    return values


def _is_source_control(token: str) -> bool:
    upper = token.upper()
    return upper in ("DC", "AC") or upper.startswith(("SIN(", "PULSE(", "EXP(", "PWL(", "SFFM("))


def _element(tokens, params: ParameterTable, models: dict[str, dict]) -> NetlistElement:
    name = tokens[0].upper()
    prefix = name[0]
    if prefix not in KINDS:
        raise ValueError(f"不支持元件「{tokens[0]}」")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name, re.I):
        raise ValueError("元件名称只接受字母、数字和下划线")
    values = dict(id=name, type=KINDS[prefix])
    if prefix in "RCL":
        if len(tokens) != 4:
            raise ValueError("R/C/L 格式：名称 节点A 节点B 数值")
        values.update(node_a=_node(tokens[1]), node_b=_node(tokens[2]), value=_positive(tokens[3], params))
    elif prefix == "X":
        if len(tokens) < 5:
            raise ValueError("缺少节点或模型")
        if tokens[4].upper() != "CS_OPAMP":
            raise ValueError("当前仅支持内置三端模型 CS_OPAMP；暂不支持厂商子电路")
        values.update(node_a=_node(tokens[1]), node_b=_node(tokens[2]), node_out=_node(tokens[3]))
        seen: set[str] = set()
        for token in tokens[5:]:
            pair = token.split("=", 1)
            key = pair[0].upper()
            if len(pair) != 2 or key not in OP_PARAMS or key in seen:
                raise ValueError(f"未知或重复运放参数「{token}」")
            seen.add(key)
            values[OP_PARAMS[key]] = (_num(pair[1], params) if key in ("VMIN", "VMAX", "VOS")
                                      else _positive(pair[1], params))
    elif prefix == "M":
        if len(tokens) < 5:
            raise ValueError("MOSFET 格式：M名称 漏 栅 源 模型名 [参数=值 …]")
        model_name = tokens[4].upper()
        model = models.get(model_name)
        if model is None:
            raise ValueError(f"未知模型「{tokens[4]}」；请先用 .model 定义")
        if model["kind"] not in ("nmos", "pmos"):
            raise ValueError(f"模型「{tokens[4]}」不是 MOSFET 模型")
        values.update(node_a=_node(tokens[1]), node_g=_node(tokens[2]), node_b=_node(tokens[3]),
                      mos_type=model["kind"], **model["values"])
        seen = set()
        for token in tokens[5:]:
            pair = token.split("=", 1)
            key = pair[0].upper()
            field_name = MOS_PARAMS.get(key)
            if len(pair) != 2 or field_name is None or key in seen:
                raise ValueError(f"未知或重复 MOSFET 参数「{token}」")
            seen.add(key)
            values[field_name] = _num(pair[1], params)
    elif prefix == "D":
        if len(tokens) < 3:
            raise ValueError("二极管格式：D名称 阳极 阴极 [模型名] [Is=…] [N=…]")
        values.update(node_a=_node(tokens[1]), node_b=_node(tokens[2]))
        model_seen = False
        seen = set()
        for token in tokens[3:]:
            if "=" in token:
                pair = token.split("=", 1)
                key = pair[0].upper()
                if key not in DIODE_PARAMS or key in seen:
                    raise ValueError(f"未知或重复二极管参数「{token}」")
                seen.add(key)
                values[DIODE_PARAMS[key]] = _positive(pair[1], params)
            else:
                if model_seen:
                    raise ValueError("二极管只能指定一个模型名")
                model = models.get(token.upper())
                if model is None:
                    raise ValueError(f"未知模型「{token}」；请先用 .model 定义")
                if model["kind"] != "diode":
                    raise ValueError(f"模型「{token}」不是二极管模型")
                values.update(model["values"])
                model_seen = True
    elif prefix in "EG":
        if len(tokens) != 6:
            raise ValueError(f"{prefix} 源格式：名称 n+ n- 控制+ 控制- 增益")
        values.update(node_a=_node(tokens[1]), node_b=_node(tokens[2]),
                      control_node_a=_node(tokens[3]), control_node_b=_node(tokens[4]),
                      value=_num(tokens[5], params))
    elif prefix in "FH":
        if len(tokens) != 5:
            raise ValueError(f"{prefix} 源格式：名称 n+ n- 控制电压源名 增益")
        values.update(node_a=_node(tokens[1]), node_b=_node(tokens[2]),
                      control_element=tokens[3].upper(), value=_num(tokens[4], params))
    elif prefix in "VI":
        if len(tokens) < 3:
            raise ValueError("缺少节点")
        values.update(node_a=_node(tokens[1]), node_b=_node(tokens[2]))
        values.update(_source(tokens, params))
    else:  # pragma: no cover - KINDS and the branches above are exhaustive
        raise ValueError(f"不支持元件「{tokens[0]}」")
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

    params = ParameterTable()
    option_values: dict[str, float] = {}
    raw_models: dict[str, ModelCard] = {}
    # Model and parameter cards may appear after the elements that use them.
    for number, line in lines:
        try:
            tokens = split_tokens(line)
        except ValueError as exc:
            raise ValueError(f"第 {number} 行：{exc}") from exc
        command = tokens[0].upper()
        if command == ".END":
            break
        try:
            if command == ".PARAM":
                _parse_param_line(line, params)
            elif command == ".MODEL":
                _parse_model_line(line, raw_models, number)
        except ValueError as exc:
            raise ValueError(f"第 {number} 行：{exc}") from exc
    try:
        models = _resolve_models(raw_models, params)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    elements: list[NetlistElement] = []
    labels: set[str] = set()
    settings, ended, analysis = DCSettings(mode="dc"), False, False
    for number, line in lines:
        try:
            tokens = split_tokens(line)
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
                settings, analysis = _analysis(tokens, params), True
            elif command == ".OPTIONS":
                _options(tokens, params, option_values)
            elif command in (".PARAM", ".MODEL"):
                continue
            elif command.startswith("."):
                raise ValueError(f"暂不支持 {tokens[0]}；不会忽略或执行文件引用、控制脚本及任意模型")
            else:
                if command in labels:
                    raise ValueError(f"元件名称重复：{tokens[0]}")
                if len(elements) >= MAX_ELEMENTS:
                    raise ValueError(f"最多支持 {MAX_ELEMENTS} 个元件")
                elements.append(_element(tokens, params, models))
                labels.add(command)
        except ValidationError as exc:
            message = "; ".join(error["msg"] for error in exc.errors())
            raise ValueError(f"第 {number} 行：{message}") from exc
        except ValueError as exc:
            raise ValueError(f"第 {number} 行：{exc}") from exc
    if not elements:
        raise ValueError("没有可仿真的元件")
    if not any("GND" in (el.node_a, el.node_b, el.node_g, el.node_out,
                         el.control_node_a, el.control_node_b) for el in elements):
        raise ValueError("必须有接地节点 0（或 GND）")
    if option_values and isinstance(settings, TransientSettings):
        settings = settings.model_copy(update=option_values)
    return ParsedSpice(title=title, request=SimulateRequest(elements=elements, settings=settings))


def export_spice(request: SimulateRequest, title: str = "Circuit Simulator") -> str:
    node_origins: dict[str, str] = {}

    def net(value):
        if value is None:
            raise ValueError("元件缺少节点")
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

    header = ["* " + title.replace("\r", " ").replace("\n", " ")]
    if any(el.type == "opamp" for el in request.elements):
        header.extend([
            "* CS_OPAMP is a built-in application model, not a standard SPICE device.",
            "* External simulators require a matching .SUBCKT model library.",
        ])

    names: set[str] = set()
    element_names: dict[str, str] = {}
    prefixes = {kind: prefix for prefix, kind in KINDS.items()}
    for el in request.elements:
        if el.type == "ground":
            continue
        prefix = prefixes[el.type]
        name = el.id.upper() if el.id.upper().startswith(prefix) else prefix + el.id.upper()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name, re.I) or name in names:
            raise ValueError(f"元件名称无效或导出后重复：{name}")
        names.add(name)
        element_names[el.id] = name

    model_lines: list[str] = []
    model_names: dict[str, str] = {}
    for el in request.elements:
        if el.type != "mosfet":
            continue
        model_name = f"MOS_{element_names[el.id]}"
        model_names[el.id] = model_name
        model_lines.append(
            f".model {model_name} {el.mos_type.upper()} (VTO={num(el.mos_vto)} KP={num(el.mos_kp)} "
            f"LAMBDA={num(el.mos_lambda)} CGSO={num(el.mos_cgs)} CGDO={num(el.mos_cgd)})"
        )

    lines = header + model_lines
    for el in request.elements:
        if el.type == "ground":
            continue
        name = element_names[el.id]
        pins = f"{net(el.node_a)} {net(el.node_b)}"
        if el.type == "opamp":
            params = " ".join(f"{key}={num(getattr(el, field))}" for key, field in OP_PARAMS.items())
            lines.append(f"{name} {pins} {net(el.node_out)} CS_OPAMP {params}")
        elif el.type == "diode":
            lines.append(f"{name} {pins} IS={num(el.diode_is)} N={num(el.diode_n)}")
        elif el.type == "mosfet":
            lines.append(f"{name} {net(el.node_a)} {net(el.node_g)} {net(el.node_b)} {model_names[el.id]}")
        elif el.type in ("vcvs", "vccs"):
            lines.append(f"{name} {pins} {net(el.control_node_a)} {net(el.control_node_b)} {num(el.value)}")
        elif el.type in ("cccs", "ccvs"):
            control = next(
                (candidate for candidate in request.elements
                 if candidate.id.upper() == (el.control_element or "").upper()),
                None,
            )
            if control is None or control.type not in ("voltage_source", "vcvs", "ccvs", "inductor"):
                raise ValueError(
                    f"{el.id}: control_element must name a voltage source (or inductor in DC)"
                )
            lines.append(f"{name} {pins} {element_names[control.id]} {num(el.value)}")
        elif el.type in ("voltage_source", "current_source"):
            if el.source_waveform == "step":
                raise ValueError(f"{el.id}：文本格式尚不支持 step 波形；请改用 pulse 或 SIN")
            amp = ac_amplitude(el)
            text = f"{name} {pins} DC {num(dc_value(el))} AC {num(amp)} {num(el.ac_phase)}"
            if el.source_waveform == "sine":
                frequency = el.sine_frequency or 60.0
                amplitude = el.sine_amplitude if el.sine_amplitude is not None else amp
                phase = el.sine_phase if el.sine_phase is not None else el.ac_phase
                text += (f" SIN({num(el.sine_offset)} {num(amplitude)} {num(frequency)} "
                         f"{num(el.sine_delay)} {num(el.sine_damping)} {num(phase)})")
            elif el.source_waveform == "pulse":
                period = el.pulse_period or 1.0
                width = el.pulse_width if el.pulse_width is not None else period / 2
                text += (f" PULSE({num(el.pulse_low)} {num(el.value)} {num(el.pulse_delay)} "
                         f"{num(el.pulse_rise)} {num(el.pulse_fall)} {num(width)} {num(period)})")
            lines.append(text)
        else:
            lines.append(f"{name} {pins} {num(el.value)}")
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
        if settings.reltol != 1e-3 or settings.abstol != 1e-9:
            lines.append(f".options RELTOL={num(settings.reltol)} ABSTOL={num(settings.abstol)}")
    lines.append(".end")
    text = "\n".join(lines) + "\n"
    # Detect case-folded node/name collisions or unsupported exported content before returning.
    parse_spice(text)
    return text
