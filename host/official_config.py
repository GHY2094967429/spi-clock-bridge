"""Read ADI HMC704X Save Config data without executing the Python file."""
import ast
import csv
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path

MAX_STEPS = 4096
MAX_BYTES = 1024 * 1024


def hex_number(text, maximum):
    """GUI/CSV values are hexadecimal; Python numeric literals follow Python notation."""
    text = text.strip()
    if not text or any(c not in "0123456789abcdefABCDEFxX" for c in text):
        raise ValueError("请输入十六进制数，例如 0x0008 或 0008")
    value = int(text, 16)
    if not 0 <= value <= maximum:
        raise ValueError(f"数值范围为 0x0000～0x{maximum:X}")
    return value


def load_csv(path):
    """Keep the existing address,data hexadecimal CSV interface."""
    rows = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"address", "data"}.issubset(reader.fieldnames):
            raise ValueError("CSV 必须包含 address,data 两列表头；数值均为十六进制")
        for line, row in enumerate(reader, 2):
            if len(rows) >= MAX_STEPS:
                raise ValueError("单个文件最多 4096 条寄存器记录")
            try:
                if None in row or any(row.get(k) is None for k in ("address", "data")):
                    raise ValueError("列数不匹配")
                rows.append((hex_number(row["address"], 0x1FFF), hex_number(row["data"], 0xFF)))
            except ValueError as error:
                raise ValueError(f"CSV 第 {line} 行：{error}") from error
    if not rows:
        raise ValueError("CSV 中没有寄存器数据")
    return rows


@dataclass(frozen=True)
class ConfigStep:
    kind: str
    address: int | None = None
    data: int | None = None
    delay_ms: int = 0
    line: int = 0
    comment: str = ""


@dataclass(frozen=True)
class Configuration:
    filename: str
    format: str
    sha256: str
    steps: tuple[ConfigStep, ...]

    @property
    def write_count(self):
        return sum(step.kind == "write" for step in self.steps)

    @property
    def duplicate_count(self):
        return self.write_count - len({step.address for step in self.steps if step.kind == "write"})


def parse_adi_python(text):
    """Accept only literal dut.write(a, v) and bounded literal time.sleep(seconds).

    Every statement is checked. Unknown Python is rejected, never ignored or run.
    In particular there is no eval/exec/import of the selected configuration.
    """
    try:
        tree = ast.parse(text.lstrip("\ufeff"), mode="exec")
    except (SyntaxError, RecursionError) as error:
        raise ValueError(f"官方配置语法错误，第 {getattr(error, 'lineno', '?')} 行：{error}") from error
    lines, steps, previous_end = text.lstrip("\ufeff").splitlines(), [], 0
    total_delay = 0
    for statement in tree.body:
        line = statement.lineno
        prefix = f"配置第 {line} 行："
        if (isinstance(statement, ast.Import) and len(statement.names) == 1
                and statement.names[0].name == "time" and statement.names[0].asname is None):
            previous_end = statement.end_lineno
            continue  # Syntax only; importing or executing the file is never necessary.
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            previous_end = statement.end_lineno
            continue
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            raise ValueError(prefix + "只支持 dut.write(地址, 数据) 和 time.sleep(秒)；未执行任何内容")
        call = statement.value
        if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)) or call.keywords:
            raise ValueError(prefix + "不支持此调用形式")
        target = (call.func.value.id, call.func.attr)
        comment = "\n".join(s.strip()[1:].strip() for s in lines[previous_end:line - 1] if s.lstrip().startswith("#"))
        if target == ("dut", "write"):
            if len(call.args) != 2 or any(not isinstance(a, ast.Constant) or type(a.value) is not int for a in call.args):
                raise ValueError(prefix + "dut.write 的地址与数据必须是整数字面量，不支持表达式")
            address, data = (a.value for a in call.args)
            if not 0 <= address <= 0x1FFF or not 0 <= data <= 0xFF:
                raise ValueError(prefix + "地址须为 0x0000～0x1FFF，数据须为 0x00～0xFF")
            steps.append(ConfigStep("write", address, data, line=line, comment=comment))
        elif target == ("time", "sleep"):
            if len(call.args) != 1 or not isinstance(call.args[0], ast.Constant) or type(call.args[0].value) not in (int, float):
                raise ValueError(prefix + "time.sleep 只接受数值字面量")
            seconds = call.args[0].value
            if not 0 <= seconds <= 60 or not math.isfinite(seconds):
                raise ValueError(prefix + "单次延时须在 0～60 秒以内")
            delay = math.ceil(seconds * 1000)
            total_delay += delay
            if total_delay > 300000:
                raise ValueError(prefix + "单个文件的总延时不能超过 300 秒")
            steps.append(ConfigStep("delay", delay_ms=delay, line=line, comment=comment))
        else:
            raise ValueError(prefix + "不支持的调用；只允许 dut.write 和 time.sleep")
        if len(steps) > MAX_STEPS:
            raise ValueError("单个文件最多 4096 个操作")
        previous_end = statement.end_lineno
    if not any(step.kind == "write" for step in steps):
        raise ValueError("配置文件中没有 dut.write 寄存器记录")
    return tuple(steps)


def load_configuration(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("配置文件不能超过 1 MiB")
    raw = path.read_bytes()
    if path.suffix.lower() == ".py":
        try:
            text = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8-sig")
        except UnicodeError as error:
            raise ValueError("官方 PY 配置请保存为 UTF-8 或带 BOM 的 UTF-16 文本") from error
        steps = parse_adi_python(text)
        format_name = "ADI HMC704X Save Config (.py)"
    elif path.suffix.lower() == ".csv":
        steps = tuple(ConfigStep("write", a, v, line=i) for i, (a, v) in enumerate(load_csv(path), 2))
        format_name = "address,data CSV"
    else:
        raise ValueError("请选择官方 Save Config 的 .py 文件，或 address,data 格式的 .csv")
    return Configuration(path.name, format_name, hashlib.sha256(raw).hexdigest(), steps)
