# 中医药知识图谱数据库设计方案

## 数据源分析

### 1. 药材数据.json（18,119条）
- 字段：名称、链接、来源信息
- 来源信息包含：拼音、别名、出处、性味、功能主治、用法用量

### 2. 中药方剂数据.json（24,685条）
- 字段：name、prescription、function、usage、source

### 3. 中成药数据_含君臣佐使.csv（1,832条，39列）
- 分类：科室类别、大类、小类
- 基本信息：中文名称、英文名称
- 核心信息：药物组成、功能与主治、方解、临床应用
- 用药信息：不良反应、禁忌、注意事项、用法与用量、规格
- 其他信息：药理毒理、参考文献、君臣佐使

---

## 一、MySQL表结构设计

### 1. 药材表 (herbs)

```sql
CREATE TABLE herbs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE COMMENT '药材名称',
    pinyin VARCHAR(200) COMMENT '拼音',
    latin_name VARCHAR(300) COMMENT '拉丁名',
    aliases TEXT COMMENT '别名（JSON格式）',
    source VARCHAR(500) COMMENT '来源',
    source_text TEXT COMMENT '来源详情',
    nature VARCHAR(100) COMMENT '性味',
    efficacy TEXT COMMENT '功效',
    meridian_tropism VARCHAR(200) COMMENT '归经',
    function TEXT COMMENT '功能主治',
    usage TEXT COMMENT '用法用量',
    precautions TEXT COMMENT '注意事项',
    link VARCHAR(500) COMMENT '数据来源链接',
    data_source ENUM('herb_data', 'prescription', 'medic') DEFAULT 'herb_data' COMMENT '数据来源',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_name (name),
    INDEX idx_pinyin (pinyin),
    INDEX idx_nature (nature)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='药材表';
```

### 2. 方剂表 (prescriptions)

```sql
CREATE TABLE prescriptions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    chinese_name VARCHAR(200) NOT NULL COMMENT '中文名称',
    english_name VARCHAR(200) COMMENT '英文名称',
    category VARCHAR(100) COMMENT '科室类别',
    main_category VARCHAR(100) COMMENT '大类',
    sub_category VARCHAR(100) COMMENT '小类',
    composition TEXT COMMENT '药物组成',
    function_indication TEXT COMMENT '功能与主治',
    analysis TEXT COMMENT '方解',
    clinical_application TEXT COMMENT '临床应用',
    side_effects TEXT COMMENT '不良反应',
    contraindications TEXT COMMENT '禁忌',
    precautions TEXT COMMENT '注意事项',
    usage_dosage TEXT COMMENT '用法与用量',
    specification TEXT COMMENT '规格',
    pharmacology TEXT COMMENT '药理毒理',
    references TEXT COMMENT '参考文献',
    monarch_ministers_assistants_couriers TEXT COMMENT '君臣佐使',
    source VARCHAR(500) COMMENT '来源',
    data_source ENUM('prescription', 'medic') DEFAULT 'prescription' COMMENT '数据来源',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_chinese_name (chinese_name),
    INDEX idx_category (category),
    INDEX idx_main_category (main_category),
    INDEX idx_data_source (data_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='方剂表（包含中药方剂和中成药）';
```

### 3. 君臣佐使角色表 (prescription_roles)

```sql
CREATE TABLE prescription_roles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE COMMENT '角色名称',
    description TEXT COMMENT '角色描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='君臣佐使角色表';

-- 初始化角色数据
INSERT INTO prescription_roles (name, description) VALUES
('君', '方剂中的主药，针对主病或主证起主要治疗作用'),
('臣', '辅助君药加强治疗作用'),
('佐', '配合君臣药治疗兼证或抑制君臣药的毒性、副作用'),
('使', '引经报使，调和诸药');
```

### 4. 方剂-药材关联表 (prescription_herbs)

```sql
CREATE TABLE prescription_herbs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    prescription_id INT NOT NULL COMMENT '方剂ID',
    herb_id INT NOT NULL COMMENT '药材ID',
    dosage VARCHAR(100) COMMENT '用量',
    role_id INT COMMENT '君臣佐使角色ID',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (herb_id) REFERENCES herbs(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES prescription_roles(id) ON DELETE SET NULL,

    INDEX idx_prescription (prescription_id),
    INDEX idx_herb (herb_id),
    INDEX idx_role (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='方剂-药材关联表';
```

### 5. 功效表 (efficacies)

```sql
CREATE TABLE efficacies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE COMMENT '功效名称',
    description TEXT COMMENT '功效描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='功效表';
```

### 6. 药材-功效关联表 (herb_efficacies)

```sql
CREATE TABLE herb_efficacies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    herb_id INT NOT NULL COMMENT '药材ID',
    efficacy_id INT NOT NULL COMMENT '功效ID',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (herb_id) REFERENCES herbs(id) ON DELETE CASCADE,
    FOREIGN KEY (efficacy_id) REFERENCES efficacies(id) ON DELETE CASCADE,

    UNIQUE KEY uk_herb_efficacy (herb_id, efficacy_id),
    INDEX idx_herb (herb_id),
    INDEX idx_efficacy (efficacy_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='药材-功效关联表';
```

### 7. 用户表 (users)

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    email VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱',
    hashed_password VARCHAR(255) NOT NULL COMMENT '加密密码',
    full_name VARCHAR(100) COMMENT '全名',
    role ENUM('admin', 'user') DEFAULT 'user' COMMENT '用户角色',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';
```

---

## 二、Neo4j图结构设计

### 节点类型

#### 1. Herb (药材节点)
```cypher
(:Herb {
    id: Integer,
    name: String,
    pinyin: String,
    latin_name: String,
    aliases: String,  // JSON
    source: String,
    nature: String,
    efficacy: String,
    meridian_tropism: String,
    usage: String,
    link: String,
    data_source: String
})
```

#### 2. Prescription (方剂节点)
```cypher
(:Prescription {
    id: Integer,
    chinese_name: String,
    english_name: String,
    category: String,
    main_category: String,
    sub_category: String,
    composition: String,
    function_indication: String,
    analysis: String,
    clinical_application: String,
    side_effects: String,
    contraindications: String,
    precautions: String,
    usage_dosage: String,
    specification: String,
    pharmacology: String,
    source: String,
    data_source: String
})
```

#### 3. Role (君臣佐使角色节点)
```cypher
(:Role {
    id: Integer,
    name: String,
    description: String
})
```

#### 4. Category (分类节点)
```cypher
(:Category {
    id: Integer,
    name: String,
    type: String  // 'department', 'main_category', 'sub_category'
})
```

#### 5. Efficacy (功效节点)
```cypher
(:Efficacy {
    id: Integer,
    name: String,
    description: String
})
```

### 关系类型

#### 1. CONTAINS - 方剂包含药材
```cypher
(:Prescription)-[:CONTAINS {
    dosage: String,
    created_at: String
}]->(:Herb)
```

#### 2. ACT_AS - 药材担任角色
```cypher
(:Herb)-[:ACT_AS]->(:Role)
```

#### 3. CONTAINS_ROLE - 方剂包含角色
```cypher
(:Prescription)-[:CONTAINS_ROLE]->(:Role)
```

#### 4. BELONGS_TO - 方剂属于分类
```cypher
(:Prescription)-[:BELONGS_TO {
    category_type: String  // 'department', 'main_category', 'sub_category'
}]->(:Category)
```

#### 5. HAS_EFFICACY - 药材具有功效
```cypher
(:Herb)-[:HAS_EFFICACY]->(:Efficacy)
```

#### 6. TREATS - 方剂治疗病症
```cypher
(:Prescription)-[:TREATS {
    description: String
}]->(:Symptom)
```

#### 7. COMPOSED_OF - 功效由成分组成
```cypher
(:Prescription)-[:COMPOSED_OF]->(:Herb)
```

---

## 三、数据同步策略

### 同步流程

```
┌─────────────┐
│   数据文件   │
│  (JSON/CSV) │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  导入脚本   │
│ (importer)  │
└──────┬──────┘
       │
       ├───► MySQL
       │    (结构化数据)
       │
       └───► Neo4j
            (知识图谱)
```

### 同步时机

1. **初始导入**：首次导入所有数据
2. **定时同步**：每小时检查数据更新
3. **手动同步**：管理员触发全量同步
4. **增量同步**：基于时间戳的增量更新

---

## 四、数据导入策略

### 导入优先级

1. **第一步**：导入药材数据 → 创建Herb节点
2. **第二步**：导入方剂数据 → 创建Prescription节点
3. **第三步**：导入中成药数据 → 创建Prescription节点和关系
4. **第四步**：建立关系 → CONTAINS, ACT_AS, BELONGS_TO

### 数据清洗

- 统一药材名称（去除多余空格、特殊字符）
- 标准化分类名称
- 验证剂量格式
- 去重处理
- 处理缺失值

---

## 五、索引优化

### MySQL索引

- `herbs.name` - 主键索引
- `prescriptions.chinese_name` - 主键索引
- `prescriptions.category` - 分类查询索引
- `prescription_herbs.prescription_id` - 外键索引
- `prescription_herbs.herb_id` - 外键索引

### Neo4j索引

```cypher
CREATE INDEX herb_name_index FOR (h:Herb) ON (h.name);
CREATE INDEX prescription_name_index FOR (p:Prescription) ON (p.chinese_name);
CREATE INDEX prescription_category_index FOR (p:Prescription) ON (p.category);
CREATE INDEX role_name_index FOR (r:Role) ON (r.name);
CREATE INDEX category_name_index FOR (c:Category) ON (c.name);
CREATE INDEX efficacy_name_index FOR (e:Efficacy) ON (e.name);
```

---

## 六、前端展示支持

### 知识图谱查询

1. **方剂详情查询**
```cypher
MATCH (p:Prescription {id: $id})-[:CONTAINS]->(h:Herb)-[:ACT_AS]->(r:Role)<-[:CONTAINS_ROLE]-(p)
RETURN p, h, r
```

2. **药材方剂查询**
```cypher
MATCH (h:Herb {id: $id})<-[:CONTAINS]-(p:Prescription)
RETURN p
```

3. **分类浏览**
```cypher
MATCH (p:Prescription)-[:BELONGS_TO]->(c:Category {type: $type})
RETURN c.name, count(p) as count
```

4. **功效关联分析**
```cypher
MATCH (e:Efficacy)<-[:HAS_EFFICACY]-(h:Herb)
WHERE e.name CONTAINS $keyword
RETURN h, e
```

### 数据管理API

- **CRUD操作**：药材、方剂的增删改查
- **批量操作**：批量导入、批量删除、批量更新
- **数据验证**：输入验证、数据完整性检查
- **数据统计**：数据量统计、分类统计、关系统计
- **数据导出**：支持JSON、CSV格式导出

---

## 七、安全考虑

1. **认证授权**
   - JWT令牌认证
   - 角色权限控制（管理员/普通用户）
   - API访问频率限制

2. **数据验证**
   - Pydantic模型验证
   - SQL注入防护
   - XSS防护

3. **审计日志**
   - 记录数据修改操作
   - 记录用户登录日志
   - 记录同步操作日志

---

## 八、扩展性设计

### 水平扩展

- MySQL：读写分离、主从复制
- Neo4j：集群部署、数据分片
- Redis：集群模式

### 垂直扩展

- 增加更多节点类型（如：Symptom、Disease）
- 增加更多关系类型
- 支持多语言（英文、拉丁名）
- 添加图片、音频等多媒体数据

---

## 九、数据量预估

| 数据类型 | MySQL记录数 | Neo4j节点数 | Neo4j关系数 |
|---------|-------------|--------------|--------------|
| 药材 | ~18,119 | 18,119 | ~40,000 |
| 方剂 | ~26,517 | 26,517 | ~100,000 |
| 分类 | ~100 | 100 | ~80,000 |
| 功效 | ~1,000 | 1,000 | ~20,000 |
| 合计 | ~45,736 | ~45,736 | ~240,000 |
