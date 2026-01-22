# 简单内存缓存（生产建议用 Redis）
_cache = {}

def get_cache(key):
    return _cache.get(key)

def set_cache(key, value):
    _cache[key] = value
