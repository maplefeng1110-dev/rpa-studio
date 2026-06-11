"""
极简 cron 解析器（零依赖）
支持标准 5 字段：分 时 日 月 周
每个字段支持： *  、 */n  、 a  、 a-b  、 a-b/n  、以及用逗号组合的列表。
周（dow）：0 或 7 表示周日，1-6 表示周一到周六。
日(dom)与周(dow)同时被限制时，按 cron 标准取「或」语义。
"""
from datetime import datetime, timedelta
from typing import Set

# 各字段取值范围
_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "dom": (1, 31),
    "month": (1, 12),
    "dow": (0, 6),
}
_ORDER = ["minute", "hour", "dom", "month", "dow"]


def _parse_field(field: str, lo: int, hi: int) -> Set[int]:
    """解析单个 cron 字段为允许的整数集合。"""
    result: Set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            rng, step_s = part.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValueError(f"无效的步长: {part}")
        else:
            rng = part

        if rng == "*":
            start, end = lo, hi
        elif "-" in rng:
            a, b = rng.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(rng)

        if start < lo or end > hi or start > end:
            raise ValueError(f"字段超出范围 [{lo},{hi}]: {part}")
        result.update(range(start, end + 1, step))
    if not result:
        raise ValueError(f"空字段: {field!r}")
    return result


def parse_cron(expr: str):
    """把 cron 表达式解析为 {字段名: 允许集合}。非法表达式抛 ValueError。"""
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"cron 必须是 5 个字段（分 时 日 月 周），收到: {expr!r}")
    parsed = {}
    for name, field in zip(_ORDER, fields):
        lo, hi = _RANGES[name]
        # dow 允许 7 表示周日，先归一化为 0
        if name == "dow":
            field = field.replace("7", "0")
        parsed[name] = _parse_field(field, lo, hi)
    return parsed


def cron_match(expr: str, dt: datetime) -> bool:
    """判断某个时间点（精确到分钟）是否匹配 cron 表达式。"""
    p = parse_cron(expr)
    dow = dt.isoweekday() % 7  # 周一=1..周日=7 -> 周日=0

    minute_ok = dt.minute in p["minute"]
    hour_ok = dt.hour in p["hour"]
    month_ok = dt.month in p["month"]

    dom_restricted = len(p["dom"]) != (_RANGES["dom"][1] - _RANGES["dom"][0] + 1)
    dow_restricted = len(p["dow"]) != (_RANGES["dow"][1] - _RANGES["dow"][0] + 1)
    dom_hit = dt.day in p["dom"]
    dow_hit = dow in p["dow"]

    if dom_restricted and dow_restricted:
        day_ok = dom_hit or dow_hit  # cron 标准：两者都限制时取或
    else:
        day_ok = dom_hit and dow_hit

    return minute_ok and hour_ok and month_ok and day_ok


def next_run(expr: str, after: datetime, max_minutes: int = 367 * 24 * 60) -> datetime:
    """
    返回 after 之后第一个匹配 cron 的时间点（精确到分钟，秒归零）。
    逐分钟向前扫描，最长扫 ~1 年，扫不到抛 ValueError（防止死循环）。
    """
    parse_cron(expr)  # 提前校验
    candidate = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    for _ in range(max_minutes):
        if cron_match(expr, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError(f"一年内找不到匹配的时间点: {expr!r}")
