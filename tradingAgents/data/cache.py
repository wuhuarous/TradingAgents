"""简单的 TTL 内存缓存 + 重试装饰器"""
import functools
import hashlib
import json
import logging
import time
from threading import RLock

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, object]] = {}
_lock = RLock()
_DEfAULT_TTL = 60  # 默认缓存 60 秒


def cache_key(*args, **kwargs) -> str:
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def ttl_cache(ttl: int = _DEfAULT_TTL, skip_first_arg: bool = False):
    """TTL 内存缓存装饰器

    Args:
        ttl: 缓存有效期（秒）
        skip_first_arg: 为 True 时跳过第一个位置参数（用于实例方法跳过 self）
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key_args = args[1:] if (skip_first_arg and args) else args
            key = f"{func.__name__}:{cache_key(*key_args, **kwargs)}"
            now = time.time()
            with _lock:
                if key in _cache:
                    expires, val = _cache[key]
                    if now < expires:
                        return val
            result = func(*args, **kwargs)
            with _lock:
                _cache[key] = (now + ttl, result)
            return result
        return wrapper
    return decorator


def retry_on_error(max_retries: int = 3, base_delay: float = 1.0):
    """重试装饰器，指数退避"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    msg = str(e)[:100]
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.debug("Retry %d/%d for %s after %.1fs: %s",
                                     attempt + 2, max_retries, func.__name__, delay, msg)
                        time.sleep(delay)
            raise last_error  # type: ignore
        return wrapper
    return decorator


def clear_expired():
    """清理过期缓存条目"""
    now = time.time()
    with _lock:
        expired = [k for k, (exp, _) in _cache.items() if now >= exp]
        for k in expired:
            del _cache[k]
