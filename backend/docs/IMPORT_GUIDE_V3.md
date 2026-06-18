# 数据导入与同步指南 V3

## 一、数据库设计概述

### MySQL表结构

#### 1. 核心表
- `users` - 用户表（支持认证授权）
- `herbs` - 药材表（18,119条）
- `prescriptions` - 方剂表（26,517条）
  - 包含中药方剂（24,685条）
  - 包含中成药（1,832条）
- `prescription_roles` - 君臣佐使角色表
- `efficacies` - 功效表

#### 2. 关联表
- `prescription_herbs` - 方剂-药材关联
- `herb_efficacies` - 药材-功效关联

### Neo4j图结构

#### 节点类型
- `Herb` - 药材节点
- `Prescription` - 方剂节点
- `Role` - 君臣佐使角色节点
- `Efficacy` - 功效节点

#### 关系类型
- `CONTAINS` - 方剂包含药材
- `ACT_AS` - 药材担任角色
- `HAS_EFFICACY` - 药材具有功效

---

## 二、分步导入方案

由于数据量较大（药材18,119条，方剂26,517条），建议分步导入：

### 第一步：清空旧数据

```bash
cd backend
python scripts/clean_database.py
```

### 第二步：导入药材数据

```bash
python scripts/import_herbs_v3.py
```

**预计时间**：5-10分钟

### 第三步：导入中药方剂数据

```bash
python scripts/import_prescriptions_v3.py
```

**预计时间**：10-15分钟

### 第四步：导入中成药数据

```bash
python scripts/import_medics_v3.py
```

**预计时间**：5-10分钟

### 第五步：建立Neo4j关系

```bash
python scripts/build_neo4j_relationships.py
```

**预计时间**：15-20分钟

### 第六步：验证数据

```bash
python scripts/validate_v3_data.py
```

---

## 三、数据清洗规则

### 1. 药材名称清洗
- 去除首尾空格
- 统一标点符号
- 处理同音异字
- 去重处理

### 2. 方剂名称清洗
- 去除编号和序号
- 标准化名称格式
- 合并重复记录

### 3. 剂量格式统一
- 转换为中文单位（两、钱、克）
- 统一分数格式
- 识别常见剂量模式

### 4. 分类名称标准化
- 统一科室类别名称
- 统一大类和小类名称
- 处理分类层级关系

---

## 四、Neo4j查询优化

### 1. 创建索引

```cypher
CREATE INDEX herb_name_index FOR (h:Herb) ON (h.name);
CREATE INDEX prescription_name_index FOR (p:Prescription) ON (p.chinese_name);
CREATE INDEX role_name_index FOR (r:Role) ON (r.name);
```

### 2. 常用查询

#### 查询方剂详情
```cypher
MATCH (p:Prescription {id: $id})
OPTIONAL MATCH (p)-[:CONTAINS]->(h:Herb)
OPTIONAL MATCH (h)-[:ACT_AS]->(r:Role)
RETURN p, collect({herb: h, role: r.name}) as ingredients
```

#### 查询药材所有方剂
```cypher
MATCH (h:Herb {id: $id})<-[:CONTAINS]-(p:Prescription)
RETURN p
```

#### 按分类查询方剂
```cypher
MATCH (p:Prescription)
WHERE p.category = $category
RETURN p LIMIT 100
```

#### 查询药材关联功效
```cypher
MATCH (h:Herb {id: $id})-[:HAS_EFFICACY]->(e:Efficacy)
RETURN e
```

---

## 五、前端知识图谱展示

### 1. 数据加载策略

```javascript
// 分页加载
async function loadPrescriptions(page = 1, pageSize = 100) {
  const skip = (page - 1) * pageSize;
  const response = await fetch(`/api/prescriptions?skip=${skip}&limit=${pageSize}`);
  return response.json();
}

// 增量加载
async function loadPrescriptionDetails(id) {
  const response = await fetch(`/api/prescriptions/${id}`);
  return response.json();
}
```

### 2. 图谱渲染优化

```javascript
// 使用Vis.js配置
const options = {
  nodes: {
    shape: 'box',
    font: { size: 16, face: 'Arial' },
    borderWidth: 2,
    shadow: true
  },
  edges: {
    width: 2,
    color: { inherit: 'from' },
    smooth: { type: 'cubicBezier' },
    arrows: { to: { enabled: true, scaleFactor: 1 } }
  },
  physics: {
    enabled: true,
    stabilization: {
      iterations: 100,
      updateInterval: 25
    }
  },
  interaction: {
    hover: true,
    tooltipDelay: 200,
    zoomView: true
  }
};
```

### 3. 节点分组和过滤

```javascript
// 按分类分组
function groupByCategory(nodes) {
  return nodes.reduce((groups, node) => {
    const category = node.category || '未分类';
    groups[category] = groups[category] || [];
    groups[category].push(node);
    return groups;
  }, {});
}

// 节点过滤
function filterNodes(nodes, searchTerm) {
  if (!searchTerm) return nodes;
  const term = searchTerm.toLowerCase();
  return nodes.filter(node =>
    node.name.toLowerCase().includes(term) ||
    (node.aliases || '').toLowerCase().includes(term)
  );
}
```

---

## 六、数据同步机制

### 1. 同步触发方式

#### 定时同步
```bash
# 添加到crontab
0 * * * * cd /path/to/backend && python scripts/sync_v3.py
```

#### API触发
```bash
# 通过API触发同步
curl -X POST http://localhost:8000/api/sync \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"direction": "mysql_to_neo4j"}'
```

### 2. 同步日志

记录所有同步操作，包括：
- 同步时间
- 同步类型（全量/增量）
- 同步结果（成功/失败）
- 错误信息
- 数据量变化

---

## 七、数据备份与恢复

### 1. MySQL备份

```bash
# 备份
mysqldump -u root -p medicine_db > backup_$(date +%Y%m%d).sql

# 恢复
mysql -u root -p medicine_db < backup_20240101.sql
```

### 2. Neo4j备份

```bash
# 备份
neo4j-admin dump --from=/path/to/neo4j/data --to=/path/to/backup/$(date +%Y%m%d)

# 恢复
neo4j-admin load --from=/path/to/backup/20240101 --to=/path/to/neo4j/data
```

---

## 八、性能优化建议

### 1. 数据库优化

- 定期分析表：`ANALYZE TABLE`
- 优化查询：使用EXPLAIN分析慢查询
- 分区大表：按时间或类别分区

### 2. 缓存策略

- Redis缓存热点数据
- 客户端缓存图谱配置
- CDN加速静态资源

### 3. 前端优化

- 虚拟滚动（加载大数据集）
- 图谱懒加载
- 节点分组折叠

---

## 九、安全注意事项

1. **数据导入**
   - 验证数据源可信度
   - 检查数据完整性
   - 记录导入日志

2. **API访问**
   - 实施速率限制
   - 验证用户权限
   - 敏感数据脱敏

3. **数据同步**
   - 使用加密传输
   - 验证数据签名
   - 回滚机制

---

## 十、故障排除

### 问题1：导入失败

**症状**：导入脚本报错退出

**解决**：
```bash
# 检查文件编码
file -i 药材数据.json

# 检查文件格式
head -20 药材数据.json
```

### 问题2：Neo4j连接失败

**症状**：无法连接到Neo4j

**解决**：
```bash
# 检查Neo4j服务状态
neo4j status

# 查看日志
tail -f logs/neo4j.log
```

### 问题3：内存不足

**症状**：导入过程中内存溢出

**解决**：
- 减少batch_size
- 使用增量导入
- 增加系统内存

---

## 十一、数据统计预估

导入完成后，预期数据量：

| 数据类型 | MySQL | Neo4j节点 | Neo4j关系 |
|---------|--------|------------|------------|
| 药材 | 18,119 | 18,119 | ~36,000 |
| 方剂 | 26,517 | 26,517 | ~100,000 |
| 角色 | 4 | 4 | ~8,000 |
| 功效 | ~1,000 | ~1,000 | ~20,000 |
| **合计** | **45,640** | **45,640** | **~164,000** |

---

## 十二、后续扩展方向

1. **数据扩展**
   - 添加病症节点
   - 添加病证关联
   - 添加药对信息

2. **功能扩展**
   - 智能推荐方剂
   - 药材配伍分析
   - 方剂对比功能

3. **可视化增强**
   - 3D图谱展示
   - 时间轴展示
   - 交互式路径分析
