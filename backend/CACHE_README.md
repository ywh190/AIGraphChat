# Redis 缓存使用指南

## 📦 安装依赖

```bash
cd backend
pip install redis==5.0.1
```

或者使用 requirements.txt：
```bash
pip install -r requirements.txt
```

## ⚙️ 配置

编辑 `.env` 文件添加Redis配置：

```env
# Redis 缓存配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # 如果没有密码请留空
REDIS_ENABLED=true
CACHE_DEFAULT_TTL=3600
CACHE_KEY_PREFIX=tcm:
```

### 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| REDIS_HOST | Redis服务器地址 | localhost |
| REDIS_PORT | Redis端口 | 6379 |
| REDIS_DB | 数据库编号 | 0 |
| REDIS_PASSWORD | 密码（可选） | 空 |
| REDIS_ENABLED | 是否启用Redis | true |
| CACHE_DEFAULT_TTL | 默认缓存时间（秒） | 3600 |
| CACHE_KEY_PREFIX | 缓存键前缀 | tcm: |

## 🚀 启动 Redis

### Windows
```powershell
# 使用 Docker
docker run -d -p 6379:6379 --name redis redis:latest

# 或下载安装版后
redis-server
```

### Linux/Mac
```bash
# 使用 Docker
docker run -d -p 6379:6379 --name redis redis:latest

# 或系统服务
sudo systemctl start redis
```

## 📖 使用方式

### 1. 自动缓存（装饰器方式）

```python
from app.cache import cache

@cache(ttl=3600, key_prefix="my_data")
def get_expensive_data(param1, param2):
    # 耗时操作
    return result
```

### 2. 手动缓存操作

```python
from app.cache import cache_get, cache_set, cache_delete

# 设置缓存
cache_set("my_key", my_data, ttl=1800)

# 获取缓存
data = cache_get("my_key")

# 删除缓存
cache_delete("my_key")
```

### 3. 使用带缓存的知识图谱服务

```python
from app.services.knowledge_graph_cached import cached_kg_service

# 查询方剂（自动缓存）
result = cached_kg_service.get_prescription_with_roles("麻黄汤")

# 查询统计信息（自动缓存）
stats = cached_kg_service.get_graph_statistics()

# 清除特定方剂缓存
cached_kg_service.clear_prescription_cache("麻黄汤")

# 清除所有方剂缓存
cached_kg_service.clear_prescription_cache()
```

## 🔧 缓存管理工具

### 命令行工具

```bash
cd backend
python scripts/cache_manager.py
```

功能：
1. 查看缓存状态
2. 测试缓存性能
3. 清除缓存
4. 测试方剂查询缓存

### API 端点

```bash
# 获取统计信息（使用缓存）
GET /api/knowledge-graph/graph-statistics?use_cache=true

# 获取统计信息（不使用缓存）
GET /api/knowledge-graph/graph-statistics?use_cache=false

# 清除所有缓存
POST /api/knowledge-graph/cache/clear?cache_type=all

# 清除方剂缓存
POST /api/knowledge-graph/cache/clear?cache_type=prescription

# 清除药材缓存
POST /api/knowledge-graph/cache/clear?cache_type=herb

# 清除统计数据缓存
POST /api/knowledge-graph/cache/clear?cache_type=statistics
```

## 📊 缓存策略

### 缓存时间（TTL）设置

| 查询类型 | TTL | 说明 |
|----------|-----|------|
| 方剂信息 | 1小时 | 数据相对稳定 |
| 药材信息 | 30分钟 | 可能较频繁查询 |
| 统计信息 | 2小时 | 数据变化缓慢 |
| 搜索结果 | 30分钟 | 可能随数据变化 |

### 缓存键命名规范

```
{tcm:{prefix}:{hash}}

示例：
- tcm:prescription_roles:a1b2c3d4
- tcm:graph_statistics
- tcm:search_nodes:query_hash
```

## 🔍 故障排除

### Redis连接失败

```
[WARN] Redis连接失败: Error 61 connecting to localhost:6379. Connection refused.
```

**解决方案**：
1. 检查Redis是否运行：`redis-cli ping`
2. 检查配置是否正确
3. 系统会自动降级为内存缓存

### 内存缓存警告

```
[WARN] redis模块未安装，将使用内存缓存作为替代
```

**解决方案**：
```bash
pip install redis
```

## 📝 注意事项

1. **Redis不可用时**：自动降级为内存缓存（重启后数据丢失）
2. **缓存失效**：数据更新后需手动清除相关缓存
3. **内存使用**：监控Redis内存使用，避免缓存过多数据
4. **开发环境**：可以禁用Redis使用内存缓存简化配置
