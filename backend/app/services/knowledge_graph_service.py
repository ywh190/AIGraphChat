from neo4j import Session
from typing import Dict, List, Any

def initialize_knowledge_graph_v2(session: Session):
    """初始化知识图谱约束（V2版本）"""
    # Neo4j 4.4+ 使用此语法
    constraints = [
        "CREATE CONSTRAINT prescription_name_unique IF NOT EXISTS FOR (p:Prescription) ASSERT p.name IS UNIQUE",
        "CREATE CONSTRAINT herb_name_unique IF NOT EXISTS FOR (h:Herb) ASSERT h.name IS UNIQUE",
        "CREATE CONSTRAINT role_name_unique IF NOT EXISTS FOR (r:Role) ASSERT r.name IS UNIQUE",
        "CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (c:PrescriptionCategory) ASSERT c.name IS UNIQUE",
        "CREATE CONSTRAINT efficacy_name_unique IF NOT EXISTS FOR (e:Efficacy) ASSERT e.name IS UNIQUE",
    ]

    for constraint in constraints:
        try:
            session.run(constraint)
        except Exception as e:
            if "EquivalentSchemaRuleAlreadyExists" in str(e) or "already exists" in str(e):
                continue
            elif "SyntaxError" in str(e):
                print(f"Warning: {e}")
                continue
            raise

# ==================== V2 查询方法（中医教授视角）====================

def get_prescription_with_roles(session: Session, prescription_name: str) -> Dict:
    """获取方剂的君臣佐使信息"""
    query = """
    MATCH (p:Prescription {name: $prescription_name})
    RETURN p
    """
    result = session.run(query, prescription_name=prescription_name)

    roles = {'君': [], '臣': [], '佐': [], '使': []}
    prescription = None

    for record in result:
        if prescription is None and record['p']:
            prescription = dict(record['p'])

    return {
        'prescription': prescription,
        'roles': roles
    }

def get_herbs_by_role(session: Session, prescription_name: str, role: str) -> List[Dict]:
    """获取某方剂中担任特定角色的药材"""
    # 由于数据库中不存在角色信息，返回空列表
    return []

def get_prescriptions_by_category(session: Session, category: str) -> List[Dict]:
    """获取某类别下的所有方剂"""
    query = """
    MATCH (p:Prescription)-[:BELONGS_TO]->(c:PrescriptionCategory {name: $category})
    RETURN p, c
    ORDER BY p.name
    """
    result = session.run(query, category=category)

    prescriptions = []
    for record in result:
        prescriptions.append({
            'prescription': dict(record['p']),
            'category': dict(record['c'])
        })
    return prescriptions

def get_prescriptions_by_efficacy(session: Session, efficacy: str) -> List[Dict]:
    """获取具有某功效的所有方剂"""
    query = """
    MATCH (p:Prescription)-[:HAS_EFFICACY]->(e:Efficacy {name: $efficacy})
    RETURN p, e
    ORDER BY p.name
    """
    result = session.run(query, efficacy=efficacy)

    prescriptions = []
    for record in result:
        prescriptions.append({
            'prescription': dict(record['p']),
            'efficacy': dict(record['e'])
        })
    return prescriptions

def get_herb_prescriptions(session: Session, herb_name: str) -> Dict:
    """获取某药材的所有方剂及其在该方剂中的角色"""
    query = """
    MATCH (h:Herb) WHERE h.name CONTAINS $herb_name
    MATCH (h)<-[:CONTAINS]-(p:Prescription)
    RETURN p
    ORDER BY p.name
    """
    result = session.run(query, herb_name=herb_name)

    prescriptions = []
    for record in result:
        prescriptions.append({
            'prescription': dict(record['p']),
            'role': None
        })
    return prescriptions

def get_herb_medics(session: Session, herb_name: str) -> List[Dict]:
    """获取包含某药材的所有中成药"""
    query = """
    MATCH (h:Herb) WHERE h.name CONTAINS $herb_name
    MATCH (h)<-[:CONTAINS]-(m:Medic)
    RETURN m
    ORDER BY m.name
    """
    result = session.run(query, herb_name=herb_name)

    medics = []
    for record in result:
        medics.append({
            'medic': dict(record['m'])
        })
    return medics

def analyze_prescription_composition(session: Session, prescription_name: str, prescription_id: int = None) -> Dict:
    """分析方剂组成（含君臣佐使、类别、功效）
    
    Args:
        session: Neo4j会话
        prescription_name: 方剂名称
        prescription_id: 可选，指定节点ID以精确匹配
    """
    # 中成药特有字段列表（用于区分中成药和方剂）
    medic_specific_fields = ['english_name', 'clinical_application', 'pharmacology', 
                             'monarch_ministers_assistants_couriers', 'side_effects', 
                             'specification', 'main_category', 'sub_category']
    
    # 如果指定了prescription_id，优先使用ID查询
    if prescription_id:
        query = """
        MATCH (p:Prescription {id: $prescription_id})
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:PrescriptionCategory)
        OPTIONAL MATCH (p)-[:HAS_EFFICACY]->(e:Efficacy)
        OPTIONAL MATCH (p)-[:CONTAINS]->(h:Herb)
        RETURN p, c, collect(DISTINCT e.name) as efficacies,
               collect(DISTINCT h.name) as herbs
        """
        result = session.run(query, prescription_id=prescription_id)
        
        for record in result:
            prescription = dict(record['p'])
            category = dict(record['c']) if record['c'] else None
            efficacies = record['efficacies']
            herbs = record['herbs']            
            
            roles = {'君': [], '臣': [], '佐': [], '使': []}
            return {
                'prescription': prescription,
                'category': category,
                'efficacies': efficacies,
                'herbs': herbs,
                'roles': roles,
                'function': prescription.get('function', '')
            }
    
    # 查询所有同名节点
    query = """
    MATCH (p:Prescription {name: $prescription_name})
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:PrescriptionCategory)
    OPTIONAL MATCH (p)-[:HAS_EFFICACY]->(e:Efficacy)
    OPTIONAL MATCH (p)-[:CONTAINS]->(h:Herb)
    RETURN p, c, collect(DISTINCT e.name) as efficacies,
           collect(DISTINCT h.name) as herbs
    """
    result = session.run(query, prescription_name=prescription_name)
    
    # 收集所有结果
    all_results = []
    for record in result:
        prescription = dict(record['p'])
        category = dict(record['c']) if record['c'] else None
        efficacies = record['efficacies']
        herbs = record['herbs']
        
        # 计算节点包含的中成药特有字段数量（方剂应该选择这个分数低的）
        medic_field_count = sum(1 for field in medic_specific_fields if field in prescription and prescription[field])
        # 计算总字段数量
        total_fields = len([k for k in prescription.keys() if prescription[k]])
        
        all_results.append({
            'prescription': prescription,
            'category': category,
            'efficacies': efficacies,
            'herbs': herbs,
            'medic_field_count': medic_field_count,
            'total_fields': total_fields,
            'id': prescription.get('id')
        })
    
    if all_results:
        # 如果有多个结果，选择中成药特有字段最少的节点（真正的方剂）
        if len(all_results) > 1:
            # 先按中成药字段数量排序，再按总字段数量排序（选择更简单的方剂数据）
            best_result = min(all_results, key=lambda x: (x['medic_field_count'], x['total_fields']))
        else:
            best_result = all_results[0]
        
        roles = {'君': [], '臣': [], '佐': [], '使': []}
        return {
            'prescription': best_result['prescription'],
            'category': best_result['category'],
            'efficacies': best_result['efficacies'],
            'herbs': best_result['herbs'],
            'roles': roles,
            'function': best_result['prescription'].get('function', '')
        }
    
    return None

def find_similar_prescriptions(session: Session, prescription_name: str, limit: int = 5) -> List[Dict]:
    """查找相似的方剂（基于共享药材，使用Jaccard相似度）"""
    # 首先获取目标方剂的总药材数
    get_p1_total = """
    MATCH (p1:Prescription {name: $prescription_name})-[:CONTAINS]->(h:Herb)
    RETURN count(h) as p1_total
    """
    p1_result = session.run(get_p1_total, prescription_name=prescription_name)
    p1_total = 0
    for record in p1_result:
        p1_total = record['p1_total']
        break
    
    if p1_total == 0:
        return []
    
    # 查找共享药材的方剂
    query = """
    MATCH (p1:Prescription {name: $prescription_name})-[:CONTAINS]->(h:Herb)<-[:CONTAINS]-(p2:Prescription)
    WHERE p1 <> p2
    WITH p1, p2, collect(DISTINCT h.name) as shared_herb_names, count(h) as shared_herbs
    MATCH (p2)-[:CONTAINS]->(h2:Herb)
    WITH p1, p2, shared_herb_names, shared_herbs, count(DISTINCT h2) as p2_total
    // 使用Jaccard相似度：交集 / 并集 = shared / (p1_total + p2_total - shared)
    WITH p1, p2, shared_herb_names, shared_herbs, p2_total, $p1_total as p1_total
    RETURN p2, shared_herbs, p1_total, p2_total, shared_herb_names,
           toFloat(shared_herbs) / toFloat(p1_total + p2_total - shared_herbs) as similarity
    ORDER BY similarity DESC, shared_herbs DESC
    LIMIT $limit
    """
    result = session.run(query, prescription_name=prescription_name, p1_total=p1_total, limit=limit)

    similar_prescriptions = []
    for record in result:
        similar_prescriptions.append({
            'prescription': dict(record['p2']),
            'shared_herbs': record['shared_herbs'],
            'p1_total': record['p1_total'],
            'p2_total': record['p2_total'],
            'shared_herb_names': record['shared_herb_names'],
            'similarity': record['similarity']
        })
    return similar_prescriptions

def find_similar_medics(session: Session, medic_name: str, limit: int = 5) -> List[Dict]:
    """查找相似的中成药（基于共享药材，使用Jaccard相似度）"""
    # 首先获取目标中成药的总药材数
    get_m1_total = """
    MATCH (m1:Medic {name: $medic_name})-[:CONTAINS]->(h:Herb)
    RETURN count(h) as m1_total
    """
    m1_result = session.run(get_m1_total, medic_name=medic_name)
    m1_total = 0
    for record in m1_result:
        m1_total = record['m1_total']
        break
    
    if m1_total == 0:
        return []
    
    # 查找共享药材的中成药
    query = """
    MATCH (m1:Medic {name: $medic_name})-[:CONTAINS]->(h:Herb)<-[:CONTAINS]-(m2:Medic)
    WHERE m1 <> m2
    WITH m1, m2, collect(DISTINCT h.name) as shared_herb_names, count(h) as shared_herbs
    MATCH (m2)-[:CONTAINS]->(h2:Herb)
    WITH m1, m2, shared_herb_names, shared_herbs, count(DISTINCT h2) as m2_total
    // 使用Jaccard相似度：交集 / 并集 = shared / (m1_total + m2_total - shared)
    WITH m1, m2, shared_herb_names, shared_herbs, m2_total, $m1_total as m1_total
    RETURN m2, shared_herbs, m1_total, m2_total, shared_herb_names,
           toFloat(shared_herbs) / toFloat(m1_total + m2_total - shared_herbs) as similarity
    ORDER BY similarity DESC, shared_herbs DESC
    LIMIT $limit
    """
    result = session.run(query, medic_name=medic_name, m1_total=m1_total, limit=limit)

    similar_medics = []
    for record in result:
        similar_medics.append({
            'medic': dict(record['m2']),
            'shared_herbs': record['shared_herbs'],
            'm1_total': record['m1_total'],
            'm2_total': record['m2_total'],
            'shared_herb_names': record['shared_herb_names'],
            'similarity': record['similarity']
        })
    return similar_medics

def get_prescription_herbs_detailed(session: Session, prescription_name: str) -> List[Dict]:
    """获取方剂的详细药材信息（含角色）"""
    query = """
    MATCH (p:Prescription {name: $prescription_name})-[:CONTAINS]->(h:Herb)
    RETURN h
    ORDER BY h.name
    """
    result = session.run(query, prescription_name=prescription_name)

    herbs = []
    for record in result:
        herbs.append({
            'herb': dict(record['h']),
            'role': None,
            'role_description': None
        })
    return herbs

from app.cache.redis_cache import cache

@cache(ttl=300, key_prefix="efficacy_stats")
def get_efficacy_statistics(session: Session) -> Dict:
    """获取功效统计信息"""
    query = """
    MATCH (e:Efficacy)<-[:HAS_EFFICACY]-(p:Prescription)
    RETURN e.name as efficacy, count(p) as prescription_count
    ORDER BY prescription_count DESC
    """
    result = session.run(query)

    statistics = []
    for record in result:
        statistics.append({
            'efficacy': record['efficacy'],
            'prescription_count': record['prescription_count']
        })
    return statistics

@cache(ttl=300, key_prefix="category_stats")
def get_category_statistics(session: Session) -> Dict:
    """获取类别统计信息"""
    query = """
    MATCH (c:PrescriptionCategory)<-[:BELONGS_TO]-(p:Prescription)
    RETURN c.name as category, count(p) as prescription_count
    ORDER BY prescription_count DESC
    """
    result = session.run(query)

    statistics = []
    for record in result:
        statistics.append({
            'category': record['category'],
            'prescription_count': record['prescription_count']
        })
    return statistics

# ==================== V1 旧查询方法（保持兼容性）====================

def get_herb_relationships(session: Session, herb_name: str, depth: int = 2) -> List[Dict]:
    """获取药材的关系网络"""
    try:
        # 搜索指定名称的药材及其相关关系
        query = """
        MATCH (h:Herb)
        WHERE h.name CONTAINS $herb_name OR h.name = $herb_name
        OPTIONAL MATCH (h)-[:HAS_EFFICACY]->(e:Efficacy)
        OPTIONAL MATCH (h)-[:HAS_NATURE]->(n:Nature)
        OPTIONAL MATCH (h)-[:BELONGS_TO_MERIDIAN]->(m:Meridian)
        OPTIONAL MATCH (p:Prescription)-[:CONTAINS]->(h)
        RETURN h, labels(h) as herb_labels, e, n, m, p
        ORDER BY h.name
        LIMIT 1000
        """
        result = session.run(query, herb_name=herb_name)

        relationships = []
        for record in result:
            herb_info = dict(record['h'])
            herb_labels = list(record['herb_labels']) if record['herb_labels'] else ['Herb']
            
            # 添加药材-功效关系
            if record['e']:
                relationships.append({
                    'herb': herb_info,
                    'herb_labels': herb_labels,
                    'relationship': {'type': 'HAS_EFFICACY'},
                    'related': dict(record['e']),
                    'related_labels': ['Efficacy']
                })
            # 添加药材-性味关系
            if record['n']:
                relationships.append({
                    'herb': herb_info,
                    'herb_labels': herb_labels,
                    'relationship': {'type': 'HAS_NATURE'},
                    'related': dict(record['n']),
                    'related_labels': ['Nature']
                })
            # 添加药材-归经关系
            if record['m']:
                relationships.append({
                    'herb': herb_info,
                    'herb_labels': herb_labels,
                    'relationship': {'type': 'ENTERS_MERIDIAN'},
                    'related': dict(record['m']),
                    'related_labels': ['Meridian']
                })
            # 添加药材-类别关系（如果数据库中有相关关系）
            # 注意：当前查询中没有包含药材类别关系，所以这里暂时注释掉
            # if record.get('hc'):
            #     relationships.append({
            #         'herb': herb_info,
            #         'herb_labels': herb_labels,
            #         'relationship': {'type': 'BELONGS_TO_CATEGORY'},
            #         'related': dict(record['hc']),
            #         'related_labels': ['HerbCategory']
            #     })
            # 添加药材-方剂关系（药材被方剂包含）
            if record['p']:
                relationships.append({
                    'herb': herb_info,
                    'herb_labels': herb_labels,
                    'relationship': {'type': 'CONTAINED_BY'},
                    'related': dict(record['p']),
                    'related_labels': ['Prescription']
                })
        return relationships
    except Exception as e:
        # 其他异常也返回空列表
        import traceback
        debug_info = f"Error in get_herb_relationships: {str(e)}\n{traceback.format_exc()}"
        print(debug_info)
        return []

def get_prescription_relationships(session: Session, prescription_name: str, depth: int = 2) -> List[Dict]:
    """获取方剂的关系网络"""
    # 中成药特有字段列表（用于区分中成药和方剂）
    medic_specific_fields = ['english_name', 'clinical_application', 'pharmacology', 
                             'monarch_ministers_assistants_couriers', 'side_effects', 
                             'specification', 'main_category', 'sub_category']
    
    # 先查询所有匹配的方剂节点
    node_query = """
    MATCH (p:Prescription) 
    WHERE p.name CONTAINS $prescription_name OR p.chinese_name CONTAINS $prescription_name
    RETURN p, labels(p) as prescription_labels
    ORDER BY p.name
    LIMIT 100
    """
    node_result = session.run(node_query, prescription_name=prescription_name)
    
    # 收集并去重同名节点
    all_prescriptions = []
    for record in node_result:
        prescription_info = dict(record['p'])
        prescription_labels = list(record['prescription_labels']) if record['prescription_labels'] else ['Prescription']
        prescription_info['labels'] = prescription_labels
        # 计算中成药特有字段得分（方剂应该选择得分低的）
        score = sum(1 for field in medic_specific_fields if field in prescription_info and prescription_info[field])
        all_prescriptions.append((prescription_info, score))
    
    # 按名称分组，对于同名节点只选择得分最低的一个（真正的方剂）
    name_to_best_prescription = {}
    for prescription_info, score in all_prescriptions:
        name = prescription_info.get('name', '')
        if name not in name_to_best_prescription:
            name_to_best_prescription[name] = (prescription_info, score)
        else:
            # 如果已有同名节点，比较得分，保留得分低的（方剂数据更简单）
            _, existing_score = name_to_best_prescription[name]
            if score < existing_score:
                name_to_best_prescription[name] = (prescription_info, score)

    
    # 获取去重后的方剂ID列表
    selected_prescription_ids = [p.get('id') for p, _ in name_to_best_prescription.values() if p.get('id')]

    
    # 重新查询关系，只包含选中的方剂（仅使用ID匹配）
    if not selected_prescription_ids:
        return []
    
    # 构建查询条件 - 只使用ID匹配，避免同名节点重复
    query = """
    MATCH (p:Prescription) 
    WHERE p.id IN $prescription_ids
    OPTIONAL MATCH (p)-[:HAS_EFFICACY]->(e:Efficacy)
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:PrescriptionCategory)
    OPTIONAL MATCH (p)-[:HAS_ROLE]->(role:Role)
    OPTIONAL MATCH (p)-[r:CONTAINS]->(h:Herb)
    RETURN p, labels(p) as prescription_labels, e, c, role, r, h
    ORDER BY p.name
    LIMIT 1000
    """
    result = session.run(query, prescription_ids=selected_prescription_ids)

    relationships = []
    for record in result:
        prescription_info = dict(record['p'])
        prescription_labels = list(record['prescription_labels']) if record['prescription_labels'] else ['Prescription']
        
        # 添加方剂-功效关系
        if record['e']:
            relationships.append({
                'prescription': prescription_info,
                'prescription_labels': prescription_labels,
                'relationship': {'type': 'HAS_EFFICACY'},
                'related': dict(record['e']),
                'related_labels': ['Efficacy']
            })
        # 添加方剂-类别关系
        if record['c']:
            relationships.append({
                'prescription': prescription_info,
                'prescription_labels': prescription_labels,
                'relationship': {'type': 'BELONGS_TO'},
                'related': dict(record['c']),
                'related_labels': ['PrescriptionCategory']
            })
        # 添加方剂-角色关系（君臣佐使）
        if record['role']:
            role_info = dict(record['role'])
            role_type = role_info.get('name', 'Role')
            relationships.append({
                'prescription': prescription_info,
                'prescription_labels': prescription_labels,
                'relationship': {'type': 'HAS_ROLE', 'role': role_type},
                'related': role_info,
                'related_labels': ['Role']
            })
        # 添加方剂-药材关系（成分）
        if record['h']:
            relationships.append({
                'prescription': prescription_info,
                'prescription_labels': prescription_labels,
                'relationship': dict(record['r']) if record['r'] else {'type': 'CONTAINS'},
                'related': dict(record['h']),
                'related_labels': ['Herb']
            })
    
    # 为返回的方剂添加君臣佐使角色信息（从monarch_ministers_assistants_couriers字段解析）
    # 仅处理prescription节点本身，避免重复处理
    processed_prescription_ids = set()
    for rel in relationships:
        if 'prescription' in rel and 'id' in rel['prescription'] and rel['prescription']['id'] not in processed_prescription_ids:
            prescription_info = rel['prescription']
            processed_prescription_ids.add(rel['prescription']['id'])
            monarch_ministers = prescription_info.get('monarch_ministers_assistants_couriers', '') or prescription_info.get('君臣佐使', '')
            
            # 解析君臣佐使药材列表
            if monarch_ministers:
                import re
                # 解析君药药材
                monarch_match = re.search(r'君药[：:]([^。；，\n\r]+)', monarch_ministers)
                if not monarch_match:
                    monarch_match = re.search(r'君[^药]?[:：]([^。；，\n\r]+)', monarch_ministers)
                
                # 解析臣药药材
                minister_match = re.search(r'臣药[：:]([^。；，\n\r]+)', monarch_ministers)
                if not minister_match:
                    minister_match = re.search(r'臣[^药]?[:：]([^。；，\n\r]+)', monarch_ministers)
                
                # 解析佐药药材
                assistant_match = re.search(r'佐药[：:]([^。；，\n\r]+)', monarch_ministers)
                if not assistant_match:
                    assistant_match = re.search(r'佐[^药]?[:：]([^。；，\n\r]+)', monarch_ministers)
                
                # 解析使药药材
                guide_match = re.search(r'使药[：:]([^。；，\n\r]+)', monarch_ministers)
                if not guide_match:
                    guide_match = re.search(r'使[^药]?[:：]([^。；，\n\r]+)', monarch_ministers)
                
                # 为每种角色创建关系
                if monarch_match:
                    monarch_herbs = [h.strip() for h in re.split(r'[，,、]', monarch_match.group(1)) if h.strip()]
                    for herb_name in monarch_herbs:
                        relationships.append({
                            'prescription': prescription_info,
                            'prescription_labels': prescription_info.get('labels', ['Prescription']),
                            'relationship': {'type': 'HAS_ROLE', 'role': '君药', 'herb_name': herb_name},
                            'related': {'name': herb_name, 'role_type': '君药', 'description': '主药，针对主病起主要治疗作用'},
                            'related_labels': ['Herb', 'Role']
                        })
                
                if minister_match:
                    minister_herbs = [h.strip() for h in re.split(r'[，,、]', minister_match.group(1)) if h.strip()]
                    for herb_name in minister_herbs:
                        relationships.append({
                            'prescription': prescription_info,
                            'prescription_labels': prescription_info.get('labels', ['Prescription']),
                            'relationship': {'type': 'HAS_ROLE', 'role': '臣药', 'herb_name': herb_name},
                            'related': {'name': herb_name, 'role_type': '臣药', 'description': '辅助君药加强治疗主病或主证'},
                            'related_labels': ['Herb', 'Role']
                        })
                
                if assistant_match:
                    assistant_herbs = [h.strip() for h in re.split(r'[，,、]', assistant_match.group(1)) if h.strip()]
                    for herb_name in assistant_herbs:
                        relationships.append({
                            'prescription': prescription_info,
                            'prescription_labels': prescription_info.get('labels', ['Prescription']),
                            'relationship': {'type': 'HAS_ROLE', 'role': '佐药', 'herb_name': herb_name},
                            'related': {'name': herb_name, 'role_type': '佐药', 'description': '配合君、臣药以加强治疗作用'},
                            'related_labels': ['Herb', 'Role']
                        })
                
                if guide_match:
                    guide_herbs = [h.strip() for h in re.split(r'[，,、]', guide_match.group(1)) if h.strip()]
                    for herb_name in guide_herbs:
                        relationships.append({
                            'prescription': prescription_info,
                            'prescription_labels': prescription_info.get('labels', ['Prescription']),
                            'relationship': {'type': 'HAS_ROLE', 'role': '使药', 'herb_name': herb_name},
                            'related': {'name': herb_name, 'role_type': '使药', 'description': '引导诸药直达病所或调和诸药'},
                            'related_labels': ['Herb', 'Role']
                        })
    
    return relationships

def get_medic_relationships(session: Session, medic_name: str, depth: int = 2) -> List[Dict]:
    """获取中成药的关系网络（三层结构：中成药 -> 君臣佐使角色 -> 成分药材）"""
    import re
    
    # 中成药特有字段列表（用于区分中成药和方剂）
    medic_specific_fields = ['english_name', 'clinical_application', 'pharmacology', 
                             'monarch_ministers_assistants_couriers', 'side_effects', 
                             'specification', 'main_category', 'sub_category']
    
    # 搜索指定名称的中成药
    query = """
    MATCH (m:Medic) 
    WHERE m.name CONTAINS $medic_name OR m.chinese_name CONTAINS $medic_name
    RETURN m, labels(m) as medic_labels
    ORDER BY m.name
    LIMIT 100
    """
    result = session.run(query, medic_name=medic_name)
    
    relationships = []
    all_medics = []
    
    # 首先收集所有中成药节点
    for record in result:
        medic_info = dict(record['m'])
        medic_labels = list(record['medic_labels']) if record['medic_labels'] else ['Medic']
        medic_info['labels'] = medic_labels
        # 计算中成药特有字段得分
        score = sum(1 for field in medic_specific_fields if field in medic_info and medic_info[field])
        all_medics.append((medic_info, score))
    
    # 按名称分组，对于同名节点只选择得分最高的一个
    name_to_best_medic = {}
    for medic_info, score in all_medics:
        medic_name_val = medic_info.get('name', '')
        if medic_name_val not in name_to_best_medic:
            name_to_best_medic[medic_name_val] = (medic_info, score)
        else:
            # 如果已有同名节点，比较得分，保留得分高的
            _, existing_score = name_to_best_medic[medic_name_val]
            if score > existing_score:
                name_to_best_medic[medic_name_val] = (medic_info, score)

    
    # 获取去重后的中成药列表
    processed_medics = [medic_info for medic_info, _ in name_to_best_medic.values()]
    

    
    # 为每个中成药构建三层结构
    for medic_info in processed_medics:
        medic_name_val = medic_info.get('name', '')
        medic_id = medic_info.get('id', medic_name_val)
        
        # 添加剂型节点（从main_category字段解析）
        dosage_form = medic_info.get('main_category', '') or medic_info.get('大类', '')
        if dosage_form:
            # 提取剂型信息，如"一、解表剂"提取为"解表剂"
            import re
            dosage_form_clean = re.sub(r'^[一二三四五六七八九十]+、\s*', '', dosage_form)
            if dosage_form_clean:
                relationships.append({
                    'medic': medic_info,
                    'medic_labels': medic_info.get('labels', ['Medic']),
                    'relationship': {'type': 'HAS_DOSAGE_FORM'},
                    'related': {
                        'name': dosage_form_clean,
                        'description': f'中成药剂型：{dosage_form_clean}',
                        'dosage_form_type': '剂型'
                    },
                    'related_labels': ['DosageForm']
                })
        
        # 解析君臣佐使字段
        monarch_ministers = medic_info.get('monarch_ministers_assistants_couriers', '') or medic_info.get('君臣佐使', '')
        
        if monarch_ministers:
            # 定义角色配置
            role_configs = [
                {'key': 'monarch', 'name': '君药', 'pattern': r'君药[：:]([^。；，\n\r]+)', 'alt_pattern': r'君[^药]?[:：]([^。；，\n\r]+)', 'desc': '主药，针对主病起主要治疗作用'},
                {'key': 'minister', 'name': '臣药', 'pattern': r'臣药[：:]([^。；，\n\r]+)', 'alt_pattern': r'臣[^药]?[:：]([^。；，\n\r]+)', 'desc': '辅助君药加强治疗主病或主证'},
                {'key': 'assistant', 'name': '佐药', 'pattern': r'佐药[：:]([^。；，\n\r]+)', 'alt_pattern': r'佐[^药]?[:：]([^。；，\n\r]+)', 'desc': '配合君、臣药以加强治疗作用'},
                {'key': 'guide', 'name': '使药', 'pattern': r'使药[：:]([^。；，\n\r]+)', 'alt_pattern': r'使[^药]?[:：]([^。；，\n\r]+)', 'desc': '引导诸药直达病所或调和诸药'}
            ]
            
            for role_config in role_configs:
                # 尝试匹配角色
                match = re.search(role_config['pattern'], monarch_ministers)
                if not match:
                    match = re.search(role_config['alt_pattern'], monarch_ministers)
                
                if match:
                    # 创建角色节点唯一标识（内部使用，确保唯一性）
                    role_node_id = f"{medic_id}_ROLE_{role_config['name']}"
                    # 显示名称仅显示角色名，如"君药"
                    role_display_name = role_config['name']
                    
                    # 添加第一层关系：中成药 -> 角色
                    relationships.append({
                        'medic': medic_info,
                        'medic_labels': medic_info.get('labels', ['Medic']),
                        'relationship': {'type': 'HAS_ROLE', 'role': role_config['name']},
                        'related': {
                            'id': role_node_id,  # 使用唯一ID
                            'name': role_display_name,  # 仅显示角色名
                            'role_name': role_config['name'],
                            'description': role_config['desc'],
                            'role_type': role_config['name'],
                            'parent_medic': medic_name_val
                        },
                        'related_labels': ['Role'],
                        'is_role_node': True  # 标记为角色中间节点
                    })
                    
                    # 解析该角色下的药材
                    herb_names = [h.strip() for h in re.split(r'[，,、]', match.group(1)) if h.strip()]
                    
                    for herb_name in herb_names:
                        # 添加第二层关系：角色 -> 药材
                        relationships.append({
                            'medic': {
                                'id': role_node_id,  # 使用唯一ID
                                'name': role_display_name,  # 仅显示角色名
                                'role_name': role_config['name'],
                                'role_type': role_config['name'],
                                'parent_medic': medic_name_val,
                                'is_intermediate': True
                            },
                            'medic_labels': ['Role'],
                            'relationship': {'type': 'CONTAINS', 'role': role_config['name']},
                            'related': {
                                'name': herb_name,
                                'role_type': role_config['name'],
                                'description': role_config['desc']
                            },
                            'related_labels': ['Herb'],
                            'is_herb_under_role': True  # 标记为角色下的药材
                        })
        else:
            # 如果没有君臣佐使信息，直接查询包含的药材（兼容旧模式）
            herb_query = """
            MATCH (m:Medic {id: $medic_id})-[:CONTAINS]->(h:Herb)
            RETURN h
            LIMIT 50
            """
            herb_result = session.run(herb_query, medic_id=medic_id)
            
            for herb_record in herb_result:
                if herb_record['h']:
                    relationships.append({
                        'medic': medic_info,
                        'medic_labels': medic_info.get('labels', ['Medic']),
                        'relationship': {'type': 'CONTAINS'},
                        'related': dict(herb_record['h']),
                        'related_labels': ['Herb']
                    })
    
    return relationships

def find_path_between(session: Session, source: str, target: str, max_depth: int = 3) -> List[Dict]:
    """查找两个节点之间的路径"""
    query = f"""
    MATCH path = shortestPath((s)-[*1..{max_depth}]-(t))
    WHERE s.name = $source AND t.name = $target
    RETURN path
    """
    result = session.run(query, source=source, target=target)

    paths = []
    for record in result:
        path = record['path']
        paths.append({
            'nodes': [dict(node) for node in path.nodes],
            'relationships': [dict(rel) for rel in path.relationships]
        })
    return paths

def execute_cypher_query(session: Session, query: str) -> List[Dict]:
    """执行Cypher查询"""
    result = session.run(query)
    return [dict(record) for record in result]

def find_similar_herbs(session: Session, herb_name: str, limit: int = 5) -> List[Dict]:
    """查找相似药材（基于共享功效，使用Jaccard相似度）"""
    # 首先获取目标药材的总功效数
    get_h1_total = """
    MATCH (h1:Herb {name: $herb_name})-[:HAS_EFFICACY]->(e:Efficacy)
    RETURN count(e) as h1_total
    """
    h1_result = session.run(get_h1_total, herb_name=herb_name)
    h1_total = 0
    for record in h1_result:
        h1_total = record['h1_total']
        break
    
    if h1_total == 0:
        return []
    
    # 查找共享功效的药材
    query = """
    MATCH (h1:Herb {name: $herb_name})-[:HAS_EFFICACY]->(e:Efficacy)<-[:HAS_EFFICACY]-(h2:Herb)
    WHERE h1 <> h2
    WITH h1, h2, collect(DISTINCT e.name) as shared_efficacy_names, count(e) as shared_efficacies
    MATCH (h2)-[:HAS_EFFICACY]->(e2:Efficacy)
    WITH h1, h2, shared_efficacy_names, shared_efficacies, count(DISTINCT e2) as h2_total
    // 使用Jaccard相似度：交集 / 并集 = shared / (h1_total + h2_total - shared)
    WITH h1, h2, shared_efficacy_names, shared_efficacies, h2_total, $h1_total as h1_total
    RETURN h2, shared_efficacies, h1_total, h2_total, shared_efficacy_names,
           toFloat(shared_efficacies) / toFloat(h1_total + h2_total - shared_efficacies) as similarity
    ORDER BY similarity DESC, shared_efficacies DESC
    LIMIT $limit
    """
    result = session.run(query, herb_name=herb_name, h1_total=h1_total, limit=limit)

    similar_herbs = []
    for record in result:
        similar_herbs.append({
            'herb': dict(record['h2']),
            'shared_efficacies': record['shared_efficacies'],
            'h1_total': record['h1_total'],
            'h2_total': record['h2_total'],
            'shared_efficacy_names': record['shared_efficacy_names'],
            'similarity': record['similarity']
        })
    return similar_herbs

def get_herb_efficacy_network(session: Session, herb_name: str) -> Dict:
    """获取药材-功效网络"""
    query = """
    MATCH (h:Herb {name: $herb_name})-[:HAS_EFFICACY]->(e:Efficacy)
    OPTIONAL MATCH (e)<-[:HAS_EFFICACY]-(h2:Herb)
    WHERE h2 <> h
    RETURN h, e, collect(DISTINCT h2) as related_herbs
    """
    result = session.run(query, herb_name=herb_name)

    network = {
        'herb': None,
        'efficacies': []
    }

    for record in result:
        if network['herb'] is None:
            network['herb'] = dict(record['h'])
        
        efficacy = dict(record['e'])
        related_herbs = [dict(h) for h in record['related_herbs']]
        
        network['efficacies'].append({
            'efficacy': efficacy,
            'related_herbs': related_herbs
        })

    return network


@cache(ttl=600, key_prefix="graph_stats")
def get_graph_statistics(session: Session) -> Dict:
    """获取图谱统计信息"""
    stats = {}

    # 节点统计
    node_query = """
    MATCH (n)
    RETURN labels(n)[0] as label, count(n) as count
    ORDER BY count DESC
    """
    result = session.run(node_query)
    stats['nodes'] = {record['label']: record['count'] for record in result}
    stats['total_nodes'] = sum(stats['nodes'].values())

    # 关系统计
    rel_query = """
    MATCH ()-[r]->()
    RETURN type(r) as type, count(r) as count
    ORDER BY count DESC
    """
    result = session.run(rel_query)
    stats['relationships'] = {record['type']: record['count'] for record in result}
    stats['total_relationships'] = sum(stats['relationships'].values())

    return stats


def get_node_statistics_by_label(session: Session, label: str) -> Dict:
    """按标签获取节点统计信息"""
    query = f"""
    MATCH (n:{label})
    RETURN count(n) as count
    """
    result = session.run(query)
    record = result.single()
    return {'label': label, 'count': record['count'] if record else 0}


def find_pattern_matches(session: Session, pattern: str, limit: int = 20) -> List[Dict]:
    """查找模式匹配"""
    # 简单的模式匹配实现
    query = f"""
    MATCH (n)
    WHERE n.name CONTAINS $pattern
    RETURN n, labels(n) as labels
    LIMIT $limit
    """
    result = session.run(query, pattern=pattern, limit=limit)
    return [{'node': dict(record['n']), 'labels': record['labels']} for record in result]


def get_subgraph_by_ids(session: Session, node_ids: List[str], depth: int = 2) -> Dict:
    """根据节点ID获取子图"""
    if not node_ids:
        return {'nodes': [], 'links': []}

    query = f"""
    MATCH (n)
    WHERE n.name IN $node_ids
    OPTIONAL MATCH (n)-[*1..{depth}]-(m)
    RETURN DISTINCT n, m
    """
    result = session.run(query, node_ids=node_ids)

    nodes = []
    links = []
    node_set = set()

    for record in result:
        n = record['n']
        m = record['m']

        if n and n['name'] not in node_set:
            nodes.append(dict(n))
            node_set.add(n['name'])

        if m and m['name'] not in node_set:
            nodes.append(dict(m))
            node_set.add(m['name'])

    return {'nodes': nodes, 'links': links}


def analyze_medic_composition(session: Session, medic_name: str, medic_id: int = None) -> Dict:
    """分析中成药组成（含君臣佐使、功效）
    
    Args:
        session: Neo4j会话
        medic_name: 中成药名称
        medic_id: 可选，指定节点ID以精确匹配
    """
    # 中成药特有字段列表（用于区分中成药和方剂）
    medic_specific_fields = ['english_name', 'clinical_application', 'pharmacology', 
                             'monarch_ministers_assistants_couriers', 'side_effects', 
                             'specification', 'main_category', 'sub_category']
    
    # 如果指定了medic_id，优先使用ID查询
    if medic_id:
        query = """
        MATCH (m:Medic {id: $medic_id})
        OPTIONAL MATCH (m)-[:HAS_EFFICACY]->(e:Efficacy)
        OPTIONAL MATCH (m)-[:CONTAINS]->(h:Herb)
        RETURN m, collect(DISTINCT e.name) as efficacies,
               collect(DISTINCT h.name) as herbs
        """
        result = session.run(query, medic_id=medic_id)
        
        for record in result:
            medic = dict(record['m'])
            efficacies = record['efficacies']
            herbs = record['herbs']
            

            
            return {
                'medic': medic,
                'efficacies': efficacies,
                'herbs': herbs
            }
    
    # 查询所有同名节点，然后选择最合适的
    query = """
    MATCH (m:Medic {name: $medic_name})
    OPTIONAL MATCH (m)-[:HAS_EFFICACY]->(e:Efficacy)
    OPTIONAL MATCH (m)-[:CONTAINS]->(h:Herb)
    RETURN m, collect(DISTINCT e.name) as efficacies,
           collect(DISTINCT h.name) as herbs
    """
    result = session.run(query, medic_name=medic_name)
    
    # 收集所有结果
    all_results = []
    for record in result:
        medic = dict(record['m'])
        efficacies = record['efficacies']
        herbs = record['herbs']
        all_results.append({
            'medic': medic,
            'efficacies': efficacies,
            'herbs': herbs,
            'score': sum(1 for field in medic_specific_fields if field in medic and medic[field])
        })
    
    if all_results:
        # 如果有多个结果，选择中成药特有字段最多的节点
        if len(all_results) > 1:

            best_result = max(all_results, key=lambda x: x['score'])

        else:
            best_result = all_results[0]

        
        return {
            'medic': best_result['medic'],
            'efficacies': best_result['efficacies'],
            'herbs': best_result['herbs']
        }
    
    # 如果没有找到Medic标签的节点，尝试查找Prescription标签的节点

    query = """
    MATCH (p:Prescription {name: $medic_name})
    OPTIONAL MATCH (p)-[:HAS_EFFICACY]->(e:Efficacy)
    OPTIONAL MATCH (p)-[:CONTAINS]->(h:Herb)
    RETURN p, collect(DISTINCT e.name) as efficacies,
           collect(DISTINCT h.name) as herbs
    """
    result = session.run(query, medic_name=medic_name)
    
    # 同样收集所有结果并选择最合适的
    all_results = []
    for record in result:
        medic = dict(record['p'])
        efficacies = record['efficacies']
        herbs = record['herbs']
        all_results.append({
            'medic': medic,
            'efficacies': efficacies,
            'herbs': herbs,
            'score': sum(1 for field in medic_specific_fields if field in medic and medic[field])
        })
    
    if all_results:
        if len(all_results) > 1:

            best_result = max(all_results, key=lambda x: x['score'])

        else:
            best_result = all_results[0]

        
        return {
            'medic': best_result['medic'],
            'efficacies': best_result['efficacies'],
            'herbs': best_result['herbs']
        }
    
    # 如果都没有找到，返回默认结构

    return {
        'medic': {'name': medic_name, 'id': '', 'category': '', 'function_indication': '', 'composition': ''},
        'efficacies': [],
        'herbs': []
    }


def get_relationship_statistics(session: Session) -> Dict:
    """获取关系类型统计"""
    query = """
    MATCH ()-[r]->()
    RETURN type(r) as type, count(r) as count
    ORDER BY count DESC
    """
    result = session.run(query)
    return {record['type']: record['count'] for record in result}


def search_herbs_by_name(session: Session, herb_name: str, limit: int = 10) -> List[Dict]:
    """根据名称搜索药材实体"""
    query = """
    MATCH (h:Herb)
    WHERE h.name CONTAINS $herb_name OR h.name = $herb_name
    RETURN h, labels(h) as labels
    LIMIT $limit
    """
    result = session.run(query, herb_name=herb_name, limit=limit)
    
    herbs = []
    for record in result:
        herb = dict(record['h'])
        labels = list(record['labels']) if record['labels'] else ['Herb']
        herbs.append({
            'entity': herb,
            'labels': labels,
            'type': 'Herb'
        })
    return herbs


def search_prescriptions_by_name(session: Session, prescription_name: str, limit: int = 10) -> List[Dict]:
    """根据名称搜索方剂实体"""
    query = """
    MATCH (p:Prescription)
    WHERE p.name CONTAINS $prescription_name OR p.name = $prescription_name
    RETURN p, labels(p) as labels
    LIMIT $limit
    """
    result = session.run(query, prescription_name=prescription_name, limit=limit)
    
    prescriptions = []
    for record in result:
        prescription = dict(record['p'])
        labels = list(record['labels']) if record['labels'] else ['Prescription']
        prescriptions.append({
            'entity': prescription,
            'labels': labels,
            'type': 'Prescription'
        })
    return prescriptions


def search_medics_by_name(session: Session, medic_name: str, limit: int = 10) -> List[Dict]:
    """根据名称搜索中成药实体"""
    query = """
    MATCH (m:Medic)
    WHERE m.name CONTAINS $medic_name OR m.name = $medic_name
    RETURN m, labels(m) as labels
    LIMIT $limit
    """
    result = session.run(query, medic_name=medic_name, limit=limit)
    
    medics = []
    for record in result:
        medic = dict(record['m'])
        labels = list(record['labels']) if record['labels'] else ['Medic']
        medics.append({
            'entity': medic,
            'labels': labels,
            'type': 'Medic'
        })
    return medics