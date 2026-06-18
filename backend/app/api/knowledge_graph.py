from typing import List
from fastapi import APIRouter, Depends, HTTPException
from app.db.session import get_neo4j_session
from app.models import schemas
from app.services import knowledge_graph_service
import time
import signal

router = APIRouter()

@router.get("/debug/database-info")
async def debug_database_info(session = Depends(get_neo4j_session)):
    """调试接口：查看数据库中有哪些节点和关系"""
    try:
        # 查询所有节点类型及其数量
        node_count_query = """
        MATCH (n)
        RETURN labels(n) as labels, count(n) as count
        ORDER BY count DESC
        """
        node_counts = session.run(node_count_query)

        node_stats = []
        for record in node_counts:
            node_stats.append({
                'labels': record['labels'],
                'count': record['count']
            })

        # 查询所有关系类型及其数量
        rel_count_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        ORDER BY count DESC
        """
        rel_counts = session.run(rel_count_query)

        rel_stats = []
        for record in rel_counts:
            rel_stats.append({
                'type': record['type'],
                'count': record['count']
            })

        # 查询一些样本节点
        sample_query = """
        MATCH (n)
        RETURN n.name as name, labels(n) as labels
        LIMIT 5
        """
        samples = session.run(sample_query)

        sample_nodes = []
        for record in samples:
            sample_nodes.append({
                'name': record['name'],
                'labels': record['labels']
            })

        return {
            'node_stats': node_stats,
            'rel_stats': rel_stats,
            'sample_nodes': sample_nodes
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")

@router.get("/herb-relationships/{herb_name}")
async def get_herb_relationships(
    herb_name: str, 
    depth: int = 2,
    limit: int = 1000,
    skip: int = 0,
    relationship_types: str = None,
    session = Depends(get_neo4j_session)
):
    """获取药材的关系网络"""
    import logging
    logger = logging.getLogger(__name__)
    # 去除前后空格
    herb_name = herb_name.strip()
    logger.info(f"[HERB-RELATIONSHIPS] Called with herb_name={herb_name}, depth={depth}, limit={limit}")
    try:
        # 解析relationship_types参数
        rel_types_list = None
        if relationship_types:
            rel_types_list = relationship_types.split(',')
        
        relationships = knowledge_graph_service.get_herb_relationships(
            session, herb_name, depth
        )
        # 转换为前端期望的格式
        nodes = []
        links = []
        node_set = set()
        
        # 标签到类型映射
        label_to_type = {
            'Herb': 0,
            'Prescription': 1,
            'Medic': 2,
            'Efficacy': 3,
            'Disease': 4,
            'Department': 5,
            'PrescriptionCategory': 6,
            'Role': 7,
            'Nature': 8,
            'Flavor': 9,
            'Meridian': 10,
            'Direction': 11,
            'HerbCategory': 12,
            'TreatmentMethod': 13,
            'Syndrome': 14,
            'Symptom': 15,
            'Etiology': 16,
            'Pathogenesis': 17,
            'Principle': 18,
            'Theory': 19,
            'EfficacyCategory': 20
        }
        
        # 确保 limit 有效
        if limit <= 0:
            limit = 1000
        
        # 如果没有找到关系，至少返回查询的药材节点
        if not relationships:
            nodes.append({
                'id': herb_name,
                'name': herb_name,
                'type': 0,
                'label': 'Herb',
                'labels': ['Herb']
            })
        else:
            for rel in relationships:
                # 检查总节点数是否超过限制（limit <= 0 表示不限制）
                if limit > 0 and len(nodes) >= limit:
                    break
                
                herb = rel['herb']
                herb_labels = rel.get('herb_labels', [])
                related = rel['related']
                related_labels = rel.get('related_labels', [])
                r = rel['relationship']
                rel_type = r.get('type', 'RELATED')
                
                # 如果指定了relationship_types，只处理筛选的关系类型
                if rel_types_list and rel_type not in rel_types_list:
                    continue
                
                # 添加药材节点
                if herb['name'] not in node_set:
                    primary_label = herb_labels[0] if herb_labels else 'Herb'
                    node_type = label_to_type.get(primary_label, 0)
                    node_data = dict(herb)  # 复制所有属性
                    node_data['id'] = herb['name']
                    node_data['name'] = herb['name']
                    node_data['type'] = node_type
                    node_data['label'] = primary_label
                    node_data['labels'] = herb_labels
                    nodes.append(node_data)
                    node_set.add(herb['name'])
                
                # 添加相关节点（limit <= 0 表示不限制）
                if related['name'] not in node_set and (limit <= 0 or len(nodes) < limit):
                    primary_label = related_labels[0] if related_labels else 'Unknown'
                    node_type = label_to_type.get(primary_label, 1)
                    node_data = dict(related)  # 复制所有属性
                    node_data['id'] = related['name']
                    node_data['name'] = related['name']
                    node_data['type'] = node_type
                    node_data['label'] = primary_label
                    node_data['labels'] = related_labels
                    nodes.append(node_data)
                    node_set.add(related['name'])
                
                # 添加边
                links.append({
                    'source': herb['name'],
                    'target': related['name'],
                    'type': rel_type
                })
        
        return {"nodes": nodes, "links": links}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Knowledge graph error: {str(e)}")







@router.get("/prescription-relationships/{prescription_name}")
async def get_prescription_relationships(
    prescription_name: str, 
    depth: int = 2,
    limit: int = 1000,
    skip: int = 0,
    relationship_types: str = None,
    session = Depends(get_neo4j_session)
):
    """获取方剂的关系网络"""
    # 去除前后空格
    prescription_name = prescription_name.strip()
    try:
        # 解析relationship_types参数
        rel_types_list = None
        if relationship_types:
            rel_types_list = relationship_types.split(',')
        
        relationships = knowledge_graph_service.get_prescription_relationships(
            session, prescription_name, depth
        )
        # 转换为前端期望的格式
        nodes = []
        links = []
        node_set = set()
        
        # 标签到类型映射（与药材关系API保持一致）
        label_to_type = {
            'Herb': 0,
            'Prescription': 1,
            'Medic': 2,
            'Efficacy': 3,
            'Disease': 4,
            'Department': 5,
            'PrescriptionCategory': 6,
            'Role': 7,
            'Nature': 8,
            'Flavor': 9,
            'Meridian': 10,
            'Direction': 11,
            'HerbCategory': 12,
            'TreatmentMethod': 13,
            'Syndrome': 14,
            'Symptom': 15,
            'Etiology': 16,
            'Pathogenesis': 17,
            'Principle': 18,
            'Theory': 19,
            'EfficacyCategory': 20
        }
        
        # 如果没有找到关系，至少返回查询的方剂节点
        if not relationships:
            nodes.append({
                'id': prescription_name,
                'name': prescription_name,
                'type': 1,
                'label': 'Prescription',
                'labels': ['Prescription']
            })
        else:
            for rel in relationships:
                # 检查总节点数是否超过限制（limit <= 0 表示不限制）
                if limit > 0 and len(nodes) >= limit:
                    break
                
                prescription = rel['prescription']
                prescription_labels = rel.get('prescription_labels', [])
                related = rel['related']
                related_labels = rel.get('related_labels', [])
                r = rel['relationship']
                rel_type = r.get('type', 'RELATED')
                
                # 如果指定了relationship_types，只处理筛选的关系类型
                if rel_types_list and rel_type not in rel_types_list:
                    continue
                
                # 添加方剂节点
                if prescription['name'] not in node_set:
                    primary_label = prescription_labels[0] if prescription_labels else 'Prescription'
                    node_type = label_to_type.get(primary_label, 1)
                    node_data = dict(prescription)  # 复制所有属性
                    node_data['id'] = prescription['name']
                    node_data['name'] = prescription['name']
                    node_data['type'] = node_type
                    node_data['label'] = primary_label
                    node_data['labels'] = prescription_labels
                    nodes.append(node_data)
                    node_set.add(prescription['name'])
                
                # 添加相关节点（limit <= 0 表示不限制）
                if related['name'] not in node_set and (limit <= 0 or len(nodes) < limit):
                    primary_label = related_labels[0] if related_labels else 'Unknown'
                    node_type = label_to_type.get(primary_label, 0)
                    node_data = dict(related)  # 复制所有属性
                    node_data['id'] = related['name']
                    node_data['name'] = related['name']
                    node_data['type'] = node_type
                    node_data['label'] = primary_label
                    node_data['labels'] = related_labels
                    nodes.append(node_data)
                    node_set.add(related['name'])
                
                # 添加边
                links.append({
                    'source': prescription['name'],
                    'target': related['name'],
                    'type': rel_type
                })
        
        return {"nodes": nodes, "links": links}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Knowledge graph error: {str(e)}")

@router.get("/medic-relationships/{medic_name}")
async def get_medic_relationships(
    medic_name: str, 
    depth: int = 2,
    limit: int = 1000,
    skip: int = 0,
    relationship_types: str = None,
    session = Depends(get_neo4j_session)
):
    """获取中成药的关系网络"""
    # 去除前后空格
    medic_name = medic_name.strip()
    try:
        # 解析relationship_types参数
        rel_types_list = None
        if relationship_types:
            rel_types_list = relationship_types.split(',')
        
        relationships = knowledge_graph_service.get_medic_relationships(
            session, medic_name, depth
        )
        # 转换为前端期望的格式
        nodes = []
        links = []
        node_set = set()
        
        # 标签到类型映射
        label_to_type = {
            'Herb': 0,
            'Prescription': 1,
            'Medic': 2,
            'Efficacy': 3,
            'Disease': 4,
            'Department': 5,
            'PrescriptionCategory': 6,
            'Role': 7,
            'Nature': 8,
            'Flavor': 9,
            'Meridian': 10,
            'Direction': 11,
            'HerbCategory': 12,
            'TreatmentMethod': 13,
            'Syndrome': 14,
            'Symptom': 15,
            'Etiology': 16,
            'Pathogenesis': 17,
            'Principle': 18,
            'Theory': 19,
            'EfficacyCategory': 20
        }
        
        # 使用服务函数返回的关系构建图
        # 如果服务函数返回空，则直接查询匹配的中成药节点
        if not relationships:
            # 直接查询匹配的中成药节点（模糊匹配）
            direct_query = """
            MATCH (m:Medic) 
            WHERE m.name CONTAINS $medic_name OR m.chinese_name CONTAINS $medic_name
            RETURN m, labels(m) as medic_labels
            ORDER BY m.name
            LIMIT 1000
            """
            direct_result = session.run(direct_query, medic_name=medic_name)
            for record in direct_result:
                medic = dict(record['m'])
                medic_labels = list(record['medic_labels'])
                if medic['name'] not in node_set:
                    node_data = dict(medic)
                    node_data['id'] = medic['name']
                    node_data['name'] = medic['name']
                    node_data['type'] = 2
                    node_data['label'] = 'Medic'
                    node_data['labels'] = ['Medic']
                    nodes.append(node_data)
                    node_set.add(medic['name'])
        else:
            # 首先添加中成药根节点
            for rel in relationships:
                medic = rel['medic']
                medic_labels = rel.get('medic_labels', [])
                
                # 只添加Medic类型的节点作为根
                # 使用id或name作为节点唯一标识
                root_id = medic.get('id') or medic['name']
                if 'Medic' in medic_labels and root_id not in node_set:
                    node_data = dict(medic)
                    node_data['id'] = root_id
                    node_data['name'] = medic['name']
                    node_data['type'] = 2
                    node_data['label'] = 'Medic'
                    node_data['labels'] = ['Medic']
                    nodes.append(node_data)
                    node_set.add(root_id)
                    break
            
            # 然后处理所有关系
            for rel in relationships:
                # 检查总节点数是否超过限制（limit <= 0 表示不限制）
                if limit > 0 and len(nodes) >= limit:
                    break
                
                medic = rel['medic']
                medic_labels = rel.get('medic_labels', [])
                related = rel['related']
                related_labels = rel.get('related_labels', [])
                r = rel['relationship']
                rel_type = r.get('type', 'RELATED')
                
                # 如果指定了relationship_types，只处理筛选的关系类型
                if rel_types_list and rel_type not in rel_types_list:
                    continue
                
                # 添加源节点（可能是Medic或Role）
                # 使用id或name作为节点唯一标识，优先使用id（角色节点有唯一id）
                source_id = medic.get('id') or medic['name']
                if source_id not in node_set:
                    primary_label = medic_labels[0] if medic_labels else 'Medic'
                    node_type = label_to_type.get(primary_label, 2)
                    node_data = dict(medic)
                    node_data['id'] = source_id
                    node_data['name'] = medic['name']
                    node_data['type'] = node_type
                    node_data['label'] = primary_label
                    node_data['labels'] = medic_labels
                    # 为角色节点添加描述
                    if primary_label == 'Role':
                        node_data['description'] = medic.get('description', '')
                        node_data['role_type'] = medic.get('role_type', '')
                    nodes.append(node_data)
                    node_set.add(source_id)
                
                # 添加目标节点（limit <= 0 表示不限制）
                # 使用id或name作为节点唯一标识，优先使用id（角色节点有唯一id）
                node_id = related.get('id') or related['name']
                if node_id not in node_set and (limit <= 0 or len(nodes) < limit):
                    primary_label = related_labels[0] if related_labels else 'Unknown'
                    node_type = label_to_type.get(primary_label, 0)
                    node_data = dict(related)
                    node_data['id'] = node_id
                    node_data['name'] = related['name']
                    node_data['type'] = node_type
                    node_data['label'] = primary_label
                    node_data['labels'] = related_labels
                    nodes.append(node_data)
                    node_set.add(node_id)
                
                # 添加边 - 使用正确的节点ID（优先使用id字段）
                source_id = medic.get('id') or medic['name']
                target_id = related.get('id') or related['name']
                links.append({
                    'source': source_id,
                    'target': target_id,
                    'type': rel_type
                })
        
        return {"nodes": nodes, "links": links}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Medic relationships error: {str(e)}")

@router.get("/similar-herbs/{herb_name}")
async def find_similar_herbs(
    herb_name: str, 
    limit: int = 5, 
    session = Depends(get_neo4j_session)
):
    """查找相似药材"""
    herb_name = herb_name.strip()
    try:
        similar_herbs = knowledge_graph_service.find_similar_herbs(session, herb_name, limit)
        return {"similar_herbs": similar_herbs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity search error: {str(e)}")

@router.get("/similar-prescriptions/{prescription_name}")
async def find_similar_prescriptions(
    prescription_name: str, 
    limit: int = 5, 
    session = Depends(get_neo4j_session)
):
    """查找相似方剂"""
    prescription_name = prescription_name.strip()
    try:
        similar_prescriptions = knowledge_graph_service.find_similar_prescriptions(session, prescription_name, limit)
        return {"similar_prescriptions": similar_prescriptions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity search error: {str(e)}")

@router.get("/similar-medics/{medic_name}")
async def find_similar_medics(
    medic_name: str, 
    limit: int = 5, 
    session = Depends(get_neo4j_session)
):
    """查找相似中成药"""
    medic_name = medic_name.strip()
    try:
        similar_medics = knowledge_graph_service.find_similar_medics(session, medic_name, limit)
        return {"similar_medics": similar_medics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity search error: {str(e)}")

@router.get("/herb-medics/{herb_name}")
async def get_herb_medics(
    herb_name: str,
    session = Depends(get_neo4j_session)
):
    """获取包含某药材的所有中成药"""
    herb_name = herb_name.strip()
    try:
        medics = knowledge_graph_service.get_herb_medics(session, herb_name)
        return {"medics": medics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Herb medics error: {str(e)}")

@router.get("/herb-prescriptions/{herb_name}")
async def get_herb_prescriptions(
    herb_name: str,
    session = Depends(get_neo4j_session)
):
    """获取包含某药材的所有方剂"""
    herb_name = herb_name.strip()
    try:
        prescriptions = knowledge_graph_service.get_herb_prescriptions(session, herb_name)
        return {"prescriptions": prescriptions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Herb prescriptions error: {str(e)}")

@router.get("/herb-efficacy-network/{herb_name}")
async def get_herb_efficacy_network(
    herb_name: str, 
    session = Depends(get_neo4j_session)
):
    """获取药材-功效网络"""
    herb_name = herb_name.strip()
    try:
        network = knowledge_graph_service.get_herb_efficacy_network(session, herb_name)
        return {"network": network}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Efficacy network error: {str(e)}")

@router.post("/query")
async def execute_cypher_query(
    query: str, 
    session = Depends(get_neo4j_session)
):
    """执行Cypher查询"""
    try:
        result = knowledge_graph_service.execute_cypher_query(session, query)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution error: {str(e)}")

@router.get("/graph-statistics")
async def get_graph_statistics(
    session = Depends(get_neo4j_session), 
    use_cache: bool = True
):
    """获取图谱统计信息"""
    try:
        stats = knowledge_graph_service.get_graph_statistics(session)
        return {"statistics": stats, "cached": use_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph statistics error: {str(e)}")

@router.post("/cache/clear")
async def clear_cache(cache_type: str = "all"):
    """清除缓存"""
    try:
        return {"message": f"Cache cleared: {cache_type}", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear error: {str(e)}")

@router.get("/node-statistics/{label}")
async def get_node_statistics(
    label: str, 
    session = Depends(get_neo4j_session)
):
    """按标签获取节点统计信息"""
    try:
        stats = knowledge_graph_service.get_node_statistics_by_label(session, label)
        return {"statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Node statistics error: {str(e)}")





@router.post("/pattern-matches")
async def find_pattern_matches(
    pattern: str, 
    limit: int = 20, 
    session = Depends(get_neo4j_session)
):
    """查找模式匹配"""
    try:
        matches = knowledge_graph_service.find_pattern_matches(session, pattern, limit)
        return {"matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pattern matching error: {str(e)}")

class SubgraphRequest:
    def __init__(self, node_ids: List[str], depth: int = 2):
        self.node_ids = node_ids
        self.depth = depth

@router.post("/subgraph")
async def get_subgraph(
    request: dict,
    session = Depends(get_neo4j_session)
):
    """根据节点ID获取子图"""
    try:
        node_ids = request.get('node_ids', [])
        depth = request.get('depth', 2)
        subgraph = knowledge_graph_service.get_subgraph_by_ids(session, node_ids, depth)
        return {"subgraph": subgraph}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subgraph extraction error: {str(e)}")

@router.get("/relationship-statistics")
async def get_relationship_statistics(session = Depends(get_neo4j_session)):
    """获取关系类型统计"""
    try:
        stats = knowledge_graph_service.get_relationship_statistics(session)
        return {"relationship_statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relationship statistics error: {str(e)}")

@router.get("/node-details/{node_name}/{node_type}")
async def get_node_details(
    node_name: str,
    node_type: str,
    session = Depends(get_neo4j_session)
):
    """获取节点详细信息"""
    # 去除前后空格
    node_name = node_name.strip()
    node_type = node_type.strip()
    try:
        # 获取所有同名节点的标签，以便正确选择
        check_query = """
        MATCH (n {name: $name})
        RETURN n.id as id, labels(n) as labels, n
        """
        check_result = session.run(check_query, name=node_name)
        
        # 收集所有节点信息
        all_nodes = []
        label_to_node_map = {}
        for record in check_result:
            node_id = record['id']
            labels = record['labels']
            node_data = dict(record['n'])
            
            all_nodes.append({
                'id': node_id,
                'labels': labels,
                'data': node_data
            })
            
            # 映射标签到节点
            for label in labels:
                if label not in label_to_node_map:
                    label_to_node_map[label] = []
                label_to_node_map[label].append({
                    'id': node_id,
                    'data': node_data
                })
        
        print(f"节点 '{node_name}' 的所有节点信息: {all_nodes}")
        print(f"标签映射: {label_to_node_map}")
        
        # 根据请求类型选择节点
        # 优先选择与请求类型匹配的标签，并选择最合适的节点
        selected_node_type = node_type
        selected_node_data = None
        selected_node_id = None  # 新增：保存选择的节点ID
        
        # 中成药特有字段列表（用于区分中成药和方剂）
        medic_specific_fields = ['english_name', 'clinical_application', 'pharmacology', 
                                 'monarch_ministers_assistants_couriers', 'side_effects', 
                                 'specification', 'main_category', 'sub_category']
        
        if node_type in label_to_node_map:
            # 有匹配的标签，需要从多个节点中选择最合适的一个
            matching_nodes = label_to_node_map[node_type]
            
            if len(matching_nodes) == 1:
                # 只有一个匹配节点，直接使用
                selected_node_data = matching_nodes[0]['data']
                selected_node_id = matching_nodes[0]['id']
                print(f"找到唯一的 {node_type} 标签节点，ID={selected_node_id}")
            else:
                # 有多个匹配节点，需要根据请求类型选择最合适的
                print(f"找到 {len(matching_nodes)} 个 {node_type} 标签节点，进行智能选择")
                
                if node_type == 'Medic':
                    # 中成药：优先选择包含中成药特有字段的节点
                    best_node = None
                    best_score = -1
                    
                    for node_info in matching_nodes:
                        node_data = node_info['data']
                        # 计算节点包含的中成药特有字段数量
                        score = sum(1 for field in medic_specific_fields if field in node_data and node_data[field])
                        print(f"  节点 ID={node_info['id']}, 中成药字段得分={score}")
                        
                        if score > best_score:
                            best_score = score
                            best_node = node_info
                    
                    if best_node:
                        selected_node_data = best_node['data']
                        selected_node_id = best_node['id']
                        print(f"选择节点 ID={selected_node_id} 作为最佳中成药节点（得分={best_score}）")
                    else:
                        selected_node_data = matching_nodes[0]['data']
                        selected_node_id = matching_nodes[0]['id']
                        
                elif node_type == 'Prescription':
                    # 方剂：优先选择字段较少的节点（方剂数据通常字段较少）
                    best_node = None
                    best_score = float('inf')
                    
                    for node_info in matching_nodes:
                        node_data = node_info['data']
                        # 计算节点包含的字段数量
                        score = len([k for k in node_data.keys() if node_data[k]])
                        print(f"  节点 ID={node_info['id']}, 字段数量={score}")
                        
                        if score < best_score:
                            best_score = score
                            best_node = node_info
                    
                    if best_node:
                        selected_node_data = best_node['data']
                        selected_node_id = best_node['id']
                        print(f"选择节点 ID={selected_node_id} 作为最佳方剂节点（字段数={best_score}）")
                    else:
                        selected_node_data = matching_nodes[0]['data']
                        selected_node_id = matching_nodes[0]['id']
                else:
                    # 其他类型：使用第一个节点
                    selected_node_data = matching_nodes[0]['data']
                    selected_node_id = matching_nodes[0]['id']
        else:
            # 没有匹配的标签，按照优先级选择
            print(f"没有找到 {node_type} 标签，按照优先级选择")
            if 'Prescription' in label_to_node_map:
                selected_node_type = 'Prescription'
                selected_node_data = label_to_node_map['Prescription'][0]['data']
                selected_node_id = label_to_node_map['Prescription'][0]['id']
            elif 'Medic' in label_to_node_map:
                selected_node_type = 'Medic'
                selected_node_data = label_to_node_map['Medic'][0]['data']
                selected_node_id = label_to_node_map['Medic'][0]['id']
            elif 'Herb' in label_to_node_map:
                selected_node_type = 'Herb'
                selected_node_data = label_to_node_map['Herb'][0]['data']
                selected_node_id = label_to_node_map['Herb'][0]['id']
            else:
                # 没有任何已知标签
                selected_node_type = 'Unknown'
                selected_node_data = all_nodes[0]['data'] if all_nodes else {}
                selected_node_id = all_nodes[0]['id'] if all_nodes else None
        
        print(f"最终选择的节点类型: {selected_node_type}, ID: {selected_node_id}")
        
        # 收集所有节点的标签用于返回
        all_labels = []
        for node in all_nodes:
            all_labels.extend(node['labels'])
        all_labels = list(set(all_labels))
        
        if selected_node_type == 'Prescription':
            # 方剂：获取组成、君臣佐使、功效等，传递节点ID以精确匹配
            details = knowledge_graph_service.analyze_prescription_composition(session, node_name, selected_node_id)
            return {"details": details, "actual_labels": all_labels, "selected_id": selected_node_id}
        elif selected_node_type == 'Medic':
            # 中成药：获取组成、功效等，传递节点ID以精确匹配
            details = knowledge_graph_service.analyze_medic_composition(session, node_name, selected_node_id)
            return {"details": details, "actual_labels": all_labels, "selected_id": selected_node_id}
        elif selected_node_type == 'Herb':
            # 药材：获取性味归经、功效、所属方剂等，同时构建图谱结构用于可视化
            prescription_info = knowledge_graph_service.get_herb_prescriptions(session, node_name)
            
            # 获取药材的性味归经信息
            query = """
            MATCH (h:Herb {name: $name})
            OPTIONAL MATCH (h)-[:HAS_NATURE]->(n:Nature)
            OPTIONAL MATCH (h)-[:BELONGS_TO_MERIDIAN]->(m:Meridian)
            OPTIONAL MATCH (h)-[:HAS_EFFICACY]->(e:Efficacy)
            RETURN h, collect(DISTINCT n.name) as natures,
                   collect(DISTINCT m.name) as meridians,
                   collect(DISTINCT e.name) as efficacies
            """
            result = session.run(query, name=node_name)
            herb_info = None
            nodes = []
            links = []
            
            # 构建图谱节点和连线
            herb_node_id = f"herb_{node_name}"
            nodes.append({
                'id': herb_node_id,
                'name': node_name,
                'label': 'Herb',
                'type': 'Herb'
            })
            
            for record in result:
                herb_info = {
                    'herb': dict(record['h']),
                    'natures': record['natures'],
                    'meridians': record['meridians'],
                    'efficacies': record['efficacies'],
                    'prescriptions': prescription_info
                }
                
                # 添加性味节点和连线
                for nature in record['natures']:
                    nature_node_id = f"nature_{nature}"
                    nodes.append({
                        'id': nature_node_id,
                        'name': nature,
                        'label': 'Nature',
                        'type': 'Nature'
                    })
                    links.append({
                        'source': herb_node_id,
                        'target': nature_node_id,
                        'relationship': 'HAS_NATURE'
                    })
                
                # 添加归经节点和连线
                for meridian in record['meridians']:
                    meridian_node_id = f"meridian_{meridian}"
                    nodes.append({
                        'id': meridian_node_id,
                        'name': meridian,
                        'label': 'Meridian',
                        'type': 'Meridian'
                    })
                    links.append({
                        'source': herb_node_id,
                        'target': meridian_node_id,
                        'relationship': 'BELONGS_TO_MERIDIAN'
                    })
                
                # 添加功效节点和连线
                for efficacy in record['efficacies']:
                    efficacy_node_id = f"efficacy_{efficacy}"
                    nodes.append({
                        'id': efficacy_node_id,
                        'name': efficacy,
                        'label': 'Efficacy',
                        'type': 'Efficacy'
                    })
                    links.append({
                        'source': herb_node_id,
                        'target': efficacy_node_id,
                        'relationship': 'HAS_EFFICACY'
                    })
                
                break
            
            # 返回两种格式：details用于详情面板，nodes/links用于图谱可视化
            return {
                "details": herb_info, 
                "nodes": nodes, 
                "links": links,
                "actual_labels": all_labels
            }
        else:
            # 其他类型节点：返回基本信息
            return {"details": {"name": node_name, "type": node_type}, "actual_labels": all_labels}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Node details error: {str(e)}")


