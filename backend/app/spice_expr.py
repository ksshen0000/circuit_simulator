"""Small, non-executing expression evaluator for the SPICE text subset.

The public ``evaluate`` entry point supports the arithmetic and functions that
are useful in ``.param`` and ``.model`` cards.  Deliberately no Python ``eval``
is used: the tokenizer and recursive-descent parser below only accept numbers,
parameter names, a fixed function table and arithmetic operators.
"""
from __future__ import annotations

import math
import re
from collections.abc import Callable

SCALES = dict(t=1e12, g=1e9, meg=1e6, k=1e3, m=1e-3, u=1e-6, n=1e-9, p=1e-12, f=1e-15, mil=25.4e-6)

_NUMBER = re.compile(
    r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)(meg|mil|[tgkmunpf])?([a-zΩ]*)",
    re.I,
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "ln": math.log,
    "log": math.log10,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
    "pow": pow,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_MAX_EXPRESSION = 4096
_MAX_PARAM_DEPTH = 64
_UNITS = {
    "", "ohm", "ohms", "v", "volt", "volts", "a", "amp", "amps",
    "f", "farad", "farads", "h", "henry", "henrys", "hz",
    "s", "sec", "secs", "second", "seconds", "ω",
}


def spice_number(token: str) -> float:
    """Parse one SPICE-style number (suffixes are case-insensitive)."""
    match = _NUMBER.fullmatch(token)
    if not match:
        raise ValueError(f"无效数值「{token}」")
    unit = (match[3] or "").lower()
    if unit not in _UNITS:
        raise ValueError(f"无效数值单位「{token}」")
    result = float(match[1]) * SCALES.get((match[2] or "").lower(), 1)
    if not math.isfinite(result):
        raise ValueError(f"数值超出范围「{token}」")
    return result


def format_number(value: float) -> str:
    """Format a resolved expression as a token that ``spice_number`` accepts."""
    if not math.isfinite(value):
        raise ValueError("表达式结果不是有限数值")
    return format(value, ".17g")


def split_tokens(text: str) -> list[str]:
    """Split on whitespace, keeping ``(...)`` / ``{...}`` groups as one token.

    SPICE commonly writes ``SIN(0 1 1k)`` or ``(VTO=1 KP=100u)``.  A plain
    ``str.split`` would break those apart, so parentheses and braces are tracked.
    """
    tokens: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            current.append(char)
        elif char in "({[":
            depth += 1
            current.append(char)
        elif char in ")}]":
            depth = max(0, depth - 1)
            current.append(char)
        elif char.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    if quote:
        raise ValueError("表达式中的引号未闭合")
    if depth:
        raise ValueError("表达式中的括号未闭合")
    return tokens


def _strip_wrapping(token: str) -> str:
    """Remove matching outer braces from ``{expr}``; leave other text untouched."""
    value = token.strip()
    if len(value) >= 2 and value[0] == "{" and value[-1] == "}":
        return value[1:-1].strip()
    return value


class _Parser:
    def __init__(self, text: str, lookup: Callable[[str], float]) -> None:
        if len(text) > _MAX_EXPRESSION:
            raise ValueError("表达式过长")
        self.text = text
        self.lookup = lookup
        self.pos = 0

    def _skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _peek(self) -> str:
        self._skip()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _take(self, expected: str) -> None:
        self._skip()
        if not self.text.startswith(expected, self.pos):
            raise ValueError(f"表达式中缺少「{expected}」")
        self.pos += len(expected)

    def parse(self) -> float:
        value = self._expression()
        self._skip()
        if self.pos != len(self.text):
            raise ValueError(f"表达式无法解析：「{self.text[self.pos:]}」")
        return value

    def _expression(self) -> float:
        value = self._term()
        while True:
            operator = self._peek()
            if not operator or operator not in "+-":
                return value
            self.pos += 1
            rhs = self._term()
            value = value + rhs if operator == "+" else value - rhs

    def _term(self) -> float:
        value = self._power()
        while True:
            operator = self._peek()
            if not operator or operator not in "*/":
                return value
            self.pos += 1
            rhs = self._power()
            if operator == "/":
                if rhs == 0:
                    raise ValueError("表达式除以零")
                value /= rhs
            else:
                value *= rhs

    def _power(self) -> float:
        value = self._unary()
        self._skip()
        if self.text.startswith("**", self.pos):
            self.pos += 2
            return value ** self._power()
        if self._peek() == "^":
            self.pos += 1
            return value ** self._power()
        return value

    def _unary(self) -> float:
        operator = self._peek()
        if operator and operator in "+-":
            self.pos += 1
            value = self._unary()
            return value if operator == "+" else -value
        return self._primary()

    def _primary(self) -> float:
        self._skip()
        if self.pos >= len(self.text):
            raise ValueError("表达式缺少数值")
        char = self.text[self.pos]
        if char == "(":
            self.pos += 1
            value = self._expression()
            self._take(")")
            return value
        match = _NUMBER.match(self.text, self.pos)
        if match:
            # The suffix-letter group must not swallow a following operator or
            # identifier; regex matching already stops at those characters.
            self.pos = match.end()
            return spice_number(match.group(0))
        match = _IDENT.match(self.text, self.pos)
        if not match:
            raise ValueError(f"无法识别的表达式字符「{char}」")
        name = match.group(0)
        self.pos = match.end()
        self._skip()
        if self._peek() == "(":
            self.pos += 1
            args = [self._expression()]
            while self._peek() == ",":
                self.pos += 1
                args.append(self._expression())
            self._take(")")
            function = _FUNCTIONS.get(name.lower())
            if function is None:
                raise ValueError(f"不支持的函数「{name}」")
            try:
                return float(function(*args))
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"函数「{name}」的参数无效") from exc
        if name.lower() in _CONSTANTS:
            try:
                return self.lookup(name)
            except ValueError:
                return _CONSTANTS[name.lower()]
        return self.lookup(name)


def evaluate(token: str, lookup: Callable[[str], float] | None = None) -> float:
    """Evaluate ``token`` (optionally wrapped in braces) to a finite float."""
    text = _strip_wrapping(token)
    if not text:
        raise ValueError("空表达式")
    try:
        value = _Parser(text, lookup or _unknown_parameter).parse()
    except OverflowError as exc:
        raise ValueError("表达式结果超出范围") from exc
    except RecursionError as exc:
        raise ValueError("表达式嵌套过深") from exc
    if not math.isfinite(value):
        raise ValueError("表达式结果不是有限数值")
    return float(value)


def _unknown_parameter(name: str) -> float:
    raise ValueError(f"未定义参数「{name}」")


def substitute(token: str, lookup: Callable[[str], float] | None = None) -> str:
    """Replace an entire ``{expr}`` or bare parameter token with its value.

    Braces embedded inside a larger token (e.g. ``{R}*2``) are not valid SPICE
    element values, so they are rejected explicitly rather than silently left
    for a later parser.
    """
    text = token.strip()
    resolver = lookup or _unknown_parameter
    if text.startswith("{") and text.endswith("}"):
        return format_number(evaluate(text, resolver))
    if "{" in text or "}" in text:
        raise ValueError(f"表达式必须整体用花括号包围：「{token}」")
    try:
        return format_number(spice_number(text))
    except ValueError:
        pass
    return format_number(resolver(text))


class ParameterTable:
    """A lazy ``.param`` table supporting forward references and cycle checks."""

    def __init__(self) -> None:
        self._expressions: dict[str, str] = {}
        self._values: dict[str, float] = {}
        self._resolving: list[str] = []

    def define(self, name: str, expression: str) -> None:
        key = name.upper()
        if key in self._expressions:
            raise ValueError(f"参数重复定义：{name}")
        self._expressions[key] = expression

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name.upper() in self._expressions

    def __len__(self) -> int:
        return len(self._expressions)

    def value(self, name: str) -> float:
        key = name.upper()
        if key in self._values:
            return self._values[key]
        if key not in self._expressions:
            raise ValueError(f"未定义参数「{name}」")
        if key in self._resolving:
            cycle = " → ".join([*self._resolving, name])
            raise ValueError(f"参数存在循环引用：{cycle}")
        if len(self._resolving) >= _MAX_PARAM_DEPTH:
            raise ValueError(f"参数依赖链过深（最多 {_MAX_PARAM_DEPTH} 层）")
        self._resolving.append(key)
        try:
            value = evaluate(self._expressions[key], self.value)
        finally:
            self._resolving.pop()
        self._values[key] = value
        return value

    def values(self) -> dict[str, float]:
        return {name: self.value(name) for name in self._expressions}

    def substitute(self, token: str) -> str:
        return substitute(token, self.value)
