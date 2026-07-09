from croniter import croniter
from datetime import datetime


def get_next_run(cron_expr: str, after: datetime) -> datetime:
    """计算 after 之后的下一个 cron 匹配时间。"""
    return croniter(cron_expr, after).get_next(datetime)
