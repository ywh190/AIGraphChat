# 数据同步机制说明文档

## 概述

本系统实现了 **MySQL** 和 **Neo4j** 之间的双向数据同步机制，确保关系型数据和图数据的一致性。

## 架构设计

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   MySQL     │◄───►│  Sync Service│◄───►│   Neo4j     │
│  (关系数据)  │     │  (同步服务)   │     │  (图数据)   │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                                        ▲
       │                                        │
       └────────────┬───────────────────────────┘
                    │
              ┌─────┴─────┐
              │   Cache   │
              │  (Redis)  │
              └───────────┘
```

## 同步策略

### 1. 全量同步
- 将所有MySQL数据同步到Neo4j
- 适用于首次同步或数据重建
- 会清除相关缓存

### 2. 增量同步
- 只同步自上次同步以来变更的数据
- 基于 `updated_at` 时间戳
- 效率更高，适合日常同步

### 3. 双向同步（预留）
- 支持 Neo4j -> MySQL 的反向同步
- 可用于图数据修改后回写关系数据库

## 使用方式

### 1. 命令行工具

```bash
cd backend
python scripts/sync_manager.py
```

菜单选项：
- 1. 全量同步
- 2. 增量同步
- 3. 仅同步方剂
- 4. 仅同步药材
- 5. 查看同步状态
- 6. 验证数据一致性
- 7. 查看同步统计
- 8. 清除同步缓存

### 2. API 端点

#### 触发全量同步
```bash
POST /api/sync
{
    "direction": "mysql_to_neo4j",
    "sync_prescriptions": true,
    "sync_herbs": true,
    "incremental": false
}
```

#### 触发增量同步
```bash
POST /api/sync/incremental
```

#### 后台异步同步
```bash
POST /api/sync/background
{
    "sync_prescriptions": true,
    "sync_herbs": true
}
```

#### 查看同步状态
```bash
GET /api/sync/status
```

#### 验证数据一致性
```bash
GET /api/sync/validate
```

#### 查看同步统计
```bash
GET /api/sync/statistics
```

#### 清除同步缓存
```bash
POST /api/sync/clear-cache
```

## 数据映射

### 方剂 (Prescription)
| MySQL 字段 | Neo4j 属性 | 说明 |
|-----------|-----------|------|
| id | id | 主键 |
| chinese_name | name | 中文名称 |
| category | category | 科室类别 |
| main_category | main_category | 大类 |
| sub_category | sub_category | 小类 |
| composition | composition | 药物组成 |
| function_indication | function_indication | 功能与主治 |
| updated_at | updated_at | 更新时间 |

### 药材 (Herb)
| MySQL 字段 | Neo4j 属性 | 说明 |
|-----------|-----------|------|
| id | id | 主键 |
| name | name | 药材名称 |
| pinyin_name | pinyin_name | 拼音 |
| latin_name | latin_name | 拉丁名 |
| category | category | 类别 |
| efficacy | efficacy | 功效 |
| updated_at | updated_at | 更新时间 |

### 关系映射
| MySQL 关系 | Neo4j 关系 | 说明 |
|-----------|-----------|------|
| 方剂-药材关联 | CONTAINS | 方剂包含药材 |
| 方剂-类别 | BELONGS_TO | 方剂属于类别 |
| 方剂-科室 | BELONGS_TO_DEPARTMENT | 方剂属于科室 |

## 一致性保证

### 冲突解决策略
1. **时间戳优先**：以 `updated_at` 最新的数据为准
2. **MySQL 优先**：默认以关系数据库为权威源
3. **手动干预**：提供API供人工解决冲突

### 数据验证
- 同步后自动验证数据一致性
- 对比节点数量和关键属性
- 生成差异报告

## 性能优化

### 1. 批量处理
- 使用批量插入代替单条操作
- 减少数据库往返次数

### 2. 缓存策略
- 同步完成后自动清除相关缓存
- 避免脏数据

### 3. 异步执行
- 大量数据同步使用后台任务
- 不阻塞API响应

## 监控与告警

### 同步状态监控
- 记录同步开始/结束时间
- 统计成功/失败数量
- 保存错误日志

### 数据一致性检查
```bash
# 定期执行一致性检查
python scripts/sync_manager.py
# 选择 6. 验证数据一致性
```

## 故障排除

### 问题1：同步失败
**症状**：同步过程中报错
**解决**：
1. 检查数据库连接
2. 查看错误日志
3. 重新执行同步

### 问题2：数据不一致
**症状**：MySQL和Neo4j数据量不匹配
**解决**：
1. 执行全量同步
2. 验证数据一致性
3. 手动处理差异

### 问题3：性能缓慢
**症状**：同步耗时过长
**解决**：
1. 使用增量同步代替全量同步
2. 增加批量处理大小
3. 检查网络延迟

## 最佳实践

### 1. 首次部署
```bash
# 1. 确保MySQL数据已导入
python scripts/import_to_mysql.py

# 2. 执行全量同步到Neo4j
python scripts/sync_manager.py
# 选择 1. 全量同步

# 3. 验证数据一致性
python scripts/sync_manager.py
# 选择 6. 验证数据一致性
```

### 2. 日常维护
```bash
# 定期执行增量同步（如每小时）
python scripts/sync_manager.py
# 选择 2. 增量同步

# 每日检查一致性
python scripts/sync_manager.py
# 选择 6. 验证数据一致性
```

### 3. 开发测试
```bash
# 仅同步少量数据用于测试
POST /api/sync
{
    "sync_prescriptions": true,
    "sync_herbs": false,
    "limit": 100
}
```

## 注意事项

1. **备份数据**：执行全量同步前建议备份数据
2. **避免并发**：不要同时执行多个同步任务
3. **监控性能**：大量数据同步可能影响系统性能
4. **及时清理**：定期清理同步日志和错误记录

## API 响应示例

### 同步成功响应
```json
{
    "success": true,
    "message": "数据同步完成",
    "data": {
        "prescriptions": {
            "synced": 1832,
            "failed": 0,
            "errors": []
        },
        "herbs": {
            "synced": 2066,
            "failed": 0,
            "errors": []
        },
        "start_time": "2024-01-15T10:30:00",
        "end_time": "2024-01-15T10:35:00"
    }
}
```

### 一致性验证响应
```json
{
    "success": true,
    "data": {
        "consistent": false,
        "differences": [
            {
                "entity": "prescriptions",
                "mysql_count": 1832,
                "neo4j_count": 1800,
                "difference": 32
            }
        ],
        "mysql_counts": {
            "prescriptions": 1832,
            "herbs": 2066
        },
        "neo4j_counts": {
            "prescriptions": 1800,
            "herbs": 2066
        }
    },
    "message": "发现数据不一致"
}
```
