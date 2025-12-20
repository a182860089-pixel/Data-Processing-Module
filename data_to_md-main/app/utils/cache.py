"""
转换结果缓存
使用 Redis 缓存转换结果，避免重复处理
借鉴 VERT 项目的 WASM 模块缓存机制
"""
import hashlib
import json
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    content: str
    metadata: Dict[str, Any]
    created_at: float
    hit_count: int = 0


class ConversionCache:
    """
    转换结果缓存
    
    特点：
    - 基于文件内容哈希的缓存键
    - 支持 Redis 和内存两种后端
    - 自动过期清理
    - 缓存命中统计
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        expire_seconds: int = 86400,  # 默认 24 小时
        max_memory_entries: int = 100,
        hash_chunk_size: int = 1024 * 1024  # 计算哈希时读取的字节数
    ):
        """
        初始化缓存
        
        Args:
            redis_url: Redis 连接 URL（可选）
            expire_seconds: 缓存过期时间（秒）
            max_memory_entries: 内存缓存最大条目数
            hash_chunk_size: 计算哈希时读取的文件大小
        """
        self.expire_seconds = expire_seconds
        self.max_memory_entries = max_memory_entries
        self.hash_chunk_size = hash_chunk_size
        
        # Redis 客户端（可选）
        self._redis = None
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url)
                self._redis.ping()
                logger.info(f"Redis cache connected: {redis_url}")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")
                self._redis = None
        
        # 内存缓存（备用）
        self._memory_cache: Dict[str, CacheEntry] = {}
        
        # 统计信息
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0
        }
    
    def _generate_cache_key(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        生成缓存键
        
        基于文件内容（前 N 字节）+ 转换选项生成唯一键
        
        Args:
            file_path: 文件路径
            options: 转换选项
            
        Returns:
            str: 缓存键
        """
        try:
            options = options or {}

            # 读取文件前 N 字节计算哈希
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(
                    f.read(self.hash_chunk_size)
                ).hexdigest()[:16]
            
            # 对转换选项计算哈希
            options_str = json.dumps(
                {k: v for k, v in sorted(options.items()) if v is not None},
                sort_keys=True
            )
            options_hash = hashlib.sha256(
                options_str.encode()
            ).hexdigest()[:8]
            
            return f"conv:{file_hash}:{options_hash}"
            
        except Exception as e:
            logger.warning(f"Failed to generate cache key: {e}")
            return None
    
    async def get(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取缓存的转换结果
        
        Args:
            file_path: 文件路径
            options: 转换选项
            
        Returns:
            Optional[Dict]: 缓存的结果，不存在时返回 None
        """
        cache_key = self._generate_cache_key(file_path, options)
        if not cache_key:
            return None
        
        result = None
        
        # 先尝试 Redis
        if self._redis:
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    result = json.loads(cached.decode())
                    self._redis.expire(cache_key, self.expire_seconds)  # 刷新过期时间
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # 备用：内存缓存
        if result is None and cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            # 检查是否过期
            if time.time() - entry.created_at < self.expire_seconds:
                entry.hit_count += 1
                result = {
                    "content": entry.content,
                    "metadata": entry.metadata
                }
            else:
                # 过期，删除
                del self._memory_cache[cache_key]
        
        if result:
            self._stats["hits"] += 1
            logger.debug(f"Cache hit: {cache_key}")
        else:
            self._stats["misses"] += 1
            logger.debug(f"Cache miss: {cache_key}")
        
        return result
    
    async def set(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        缓存转换结果
        
        Args:
            file_path: 文件路径
            options: 转换选项
            content: 转换后的内容（Markdown）
            metadata: 元数据
            
        Returns:
            bool: 是否成功缓存
        """
        cache_key = self._generate_cache_key(file_path, options)
        if not cache_key:
            return False
        
        cache_data = {
            "content": content,
            "metadata": metadata or {},
            "cached_at": time.time()
        }
        
        success = False
        
        # 尝试写入 Redis
        if self._redis:
            try:
                self._redis.setex(
                    cache_key,
                    self.expire_seconds,
                    json.dumps(cache_data)
                )
                success = True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        # 同时写入内存缓存
        self._memory_cache[cache_key] = CacheEntry(
            content=content,
            metadata=metadata or {},
            created_at=time.time()
        )
        
        # 清理过多的内存缓存条目
        if len(self._memory_cache) > self.max_memory_entries:
            self._cleanup_memory_cache()
        
        self._stats["sets"] += 1
        logger.debug(f"Cache set: {cache_key}")
        
        return success or cache_key in self._memory_cache
    
    async def check_cached(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        检查是否有缓存（不获取内容）
        
        Args:
            file_path: 文件路径
            options: 转换选项
            
        Returns:
            bool: 是否有缓存
        """
        cache_key = self._generate_cache_key(file_path, options)
        if not cache_key:
            return False
        
        # 检查 Redis
        if self._redis:
            try:
                if self._redis.exists(cache_key):
                    return True
            except Exception:
                pass
        
        # 检查内存缓存
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if time.time() - entry.created_at < self.expire_seconds:
                return True
        
        return False
    
    async def invalidate(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        使缓存失效
        
        Args:
            file_path: 文件路径
            options: 转换选项
            
        Returns:
            bool: 是否成功删除
        """
        cache_key = self._generate_cache_key(file_path, options)
        if not cache_key:
            return False
        
        deleted = False
        
        # 从 Redis 删除
        if self._redis:
            try:
                self._redis.delete(cache_key)
                deleted = True
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        
        # 从内存缓存删除
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            deleted = True
        
        logger.debug(f"Cache invalidated: {cache_key}")
        return deleted
    
    def _cleanup_memory_cache(self):
        """清理过期和最少使用的内存缓存条目"""
        current_time = time.time()
        
        # 首先删除过期条目
        expired_keys = [
            key for key, entry in self._memory_cache.items()
            if current_time - entry.created_at >= self.expire_seconds
        ]
        for key in expired_keys:
            del self._memory_cache[key]
        
        # 如果仍然超过限制，删除最少使用的条目
        if len(self._memory_cache) > self.max_memory_entries:
            # 按命中次数排序，删除命中最少的
            sorted_entries = sorted(
                self._memory_cache.items(),
                key=lambda x: x[1].hit_count
            )
            to_remove = len(self._memory_cache) - self.max_memory_entries
            for key, _ in sorted_entries[:to_remove]:
                del self._memory_cache[key]
        
        logger.debug(
            f"Memory cache cleanup: removed {len(expired_keys)} expired entries"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total * 100 if total > 0 else 0
        )
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "hit_rate": round(hit_rate, 2),
            "memory_entries": len(self._memory_cache),
            "redis_connected": self._redis is not None
        }
    
    async def clear(self):
        """清空所有缓存"""
        # 清空内存缓存
        self._memory_cache.clear()
        
        # 清空 Redis 缓存（只清除 conv: 前缀的键）
        if self._redis:
            try:
                keys = self._redis.keys("conv:*")
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")
        
        self._stats = {"hits": 0, "misses": 0, "sets": 0}
        logger.info("Cache cleared")


# 全局缓存实例（延迟初始化）
_conversion_cache: Optional[ConversionCache] = None


def get_conversion_cache() -> ConversionCache:
    """获取全局缓存实例"""
    global _conversion_cache
    
    if _conversion_cache is None:
        from app.config import get_settings
        settings = get_settings()
        
        _conversion_cache = ConversionCache(
            redis_url=settings.celery_broker_url,  # 复用 Redis 连接
            expire_seconds=settings.file_retention_days * 24 * 3600,
            max_memory_entries=100
        )
    
    return _conversion_cache
