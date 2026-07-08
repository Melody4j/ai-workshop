"""LLM 通用重试装饰器。

提供：
- LLMError: LLM 调用失败异常（重试耗尽后抛出）
- retry: 装饰器，失败重试 max_retries 次，间隔 delay 秒
"""

import functools
import logging
import time

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用重试耗尽后抛出的异常。"""

    pass


def retry(max_retries: int = 3, delay: float = 30):
    """重试装饰器。

    Args:
        max_retries: 最大重试次数（含首次调用，如 max_retries=3 表示最多调用 3 次）
        delay: 每次重试间隔（秒）

    Returns:
        装饰后的函数

    Raises:
        LLMError: 重试耗尽后抛出，包含最后一次异常信息
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(
                            f"[重试] {func.__name__} 第 {attempt} 次调用成功"
                        )
                    return result
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"[重试] {func.__name__} 第 {attempt}/{max_retries} 次失败: {e}，"
                            f"{delay}s 后重试..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[重试] {func.__name__} 第 {attempt}/{max_retries} 次失败，"
                            f"重试耗尽: {e}"
                        )
            raise LLMError(
                f"{func.__name__} 重试 {max_retries} 次后仍失败: {last_exception}"
            ) from last_exception

        return wrapper

    return decorator
