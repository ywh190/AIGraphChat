"""
Redis缓存服务
提供统一的缓存接口和装饰器
"""
import json
import hashlib
import pickle
from functools import wraps
from typing import Optional, Any, Callable
from app.core.config import settings

# 尝试导入redis，如果没有安装则使用内存缓存作为 fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[WARN] redis模块未安装，将使用内存缓存作为替代")


class MemoryCache:
    """内存缓存实现（Redis不可用时使用）"""
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)
    
    def set(self, key: str, value: Any, ex: int = None):
        # 忽略过期时间，内存缓存不做自动清理
        self._cache[key] = value
    
    def delete(self, key: str):
        self._cache.pop(key, None)
    
    def keys(self, pattern: str):
        # 简单实现，不支持通配符
        return [k for k in self._cache.keys() if pattern.replace("*", "") in k]
    
    def ping(self):
        return True


class RedisCache:
    """Redis缓存封装类"""
    
    def __init__(self):
        self._client = None
        self._enabled = settings.REDIS_ENABLED
        self._initialize()
    
    def _initialize(self):
        """初始化Redis连接"""
        if not self._enabled:
            print("[INFO] Redis缓存已禁用")
            self._client = MemoryCache()
            return
        
        if not REDIS_AVAILABLE:
            print("[WARN] Redis模块未安装，使用内存缓存")
            self._client = MemoryCache()
            return
        
        try:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=False,  # 使用二进制序列化
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            # 测试连接
            self._client.ping()
            print(f"[OK] Redis缓存连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            print(f"[WARN] Redis连接失败: {e}，将使用内存缓存")
            self._client = MemoryCache()
    
    def _make_key(self, key: str) -> str:
        """生成带前缀的缓存键"""
        return f"{settings.CACHE_KEY_PREFIX}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """序列化数据"""
        return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """反序列化数据"""
        if data is None:
            return None
        return pickle.loads(data)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            full_key = self._make_key(key)
            data = self._client.get(full_key)
            return self._deserialize(data)
        except Exception as e:
            print(f"[ERROR] 缓存获取失败: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值，0表示永不过期
        """
        try:
            full_key = self._make_key(key)
            data = self._serialize(value)
            # ttl=0 表示永不过期，None 使用默认值
            if ttl is None:
                expire = settings.CACHE_DEFAULT_TTL
            elif ttl == 0:
                expire = None  # Redis 的 ex=None 表示永不过期
            else:
                expire = ttl
            self._client.set(full_key, data, ex=expire)
        except Exception as e:
            print(f"[ERROR] 缓存设置失败: {e}")
    
    def delete(self, key: str):
        """删除缓存"""
        try:
            full_key = self._make_key(key)
            self._client.delete(full_key)
        except Exception as e:
            print(f"[ERROR] 缓存删除失败: {e}")
    
    def clear_pattern(self, pattern: str):
        """按模式清除缓存"""
        try:
            full_pattern = self._make_key(pattern)
            keys = self._client.keys(full_pattern)
            if keys:
                self._client.delete(*keys)
                print(f"[INFO] 清除缓存: {len(keys)} 个键匹配 {pattern}")
        except Exception as e:
            print(f"[ERROR] 缓存清除失败: {e}")
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            full_key = self._make_key(key)
            return self._client.exists(full_key) > 0
        except Exception:
            return False


# 全局缓存客户端实例
redis_client = RedisCache()


def _generate_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """生成缓存键"""
    # 使用函数名和参数生成唯一键
    key_parts = [
        func.__module__,
        func.__name__,
        str(args),
        str(sorted(kwargs.items()))
    ]
    key_string = "|".join(key_parts)
    # 使用MD5哈希生成短键
    return hashlib.md5(key_string.encode()).hexdigest()


def cache(ttl: int = None, key_prefix: str = None):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存过期时间（秒），默认使用配置中的值
        key_prefix: 缓存键前缀，用于手动清理缓存
    
    Example:
        @cache(ttl=3600, key_prefix="prescription")
        def get_prescription(name: str):
            return db.query(...)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = _generate_cache_key(func, args, kwargs)
            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"
            
            # 尝试从缓存获取
            cached_value = redis_client.get(cache_key)
            if cached_value is not None:
                print(f"[CACHE HIT] {func.__name__}")
                return cached_value
            
            # 执行函数
            print(f"[CACHE MISS] {func.__name__}")
            result = func(*args, **kwargs)
            
            # 存入缓存
            redis_client.set(cache_key, result, ttl)
            return result
        
        # 附加清除缓存的方法
        wrapper.cache_clear = lambda: redis_client.clear_pattern(f"{key_prefix}:*" if key_prefix else "")
        wrapper.cache_key_prefix = key_prefix
        
        return wrapper
    return decorator


def cache_get(key: str) -> Optional[Any]:
    """直接获取缓存"""
    return redis_client.get(key)


def cache_set(key: str, value: Any, ttl: int = None):
    """直接设置缓存"""
    redis_client.set(key, value, ttl)


def cache_clear(pattern: str = "*"):
    """清除匹配模式的缓存"""
    redis_client.clear_pattern(pattern)


def cache_delete(key: str):
    """删除指定缓存"""
    redis_client.delete(key)
