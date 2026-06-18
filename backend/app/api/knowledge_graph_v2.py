from fastapi import APIRouter, Depends
from neo4j import GraphDatabase
from typing import List, Dict, Optional
from app.core.config import settings
from app.db.session import get_neo4j_driver, get_neo4j_session
from app.services.knowledge_graph_service import (
    get_prescription_with_roles,
    get_herbs_by_role,
    get_prescriptions_by_category,
    get_prescriptions_by_efficacy,
    get_herb_prescriptions,
    analyze_prescription_composition,
    find_similar_prescriptions,
    get_prescription_herbs_detailed,
    get_efficacy_statistics,
    get_category_statistics
)

router = APIRouter()

@router.get("/prescription/{name}/roles")
async def get_prescription_roles(
    name: str,
    session = Depends(get_neo4j_session)
):
    """
    获取方剂的君臣佐使信息
    """
    result = get_prescription_with_roles(session, name)
    return result

@router.get("/prescription/{name}/herbs")
async def get_prescription_herbs(
    name: str,
    session = Depends(get_neo4j_session)
):
    """
    获取方剂的详细药材信息（含角色）
    """
    herbs = get_prescription_herbs_detailed(session, name)
    return {"prescription": name, "herbs": herbs}

@router.get("/prescription/{name}/analysis")
async def analyze_prescription(
    name: str,
    session = Depends(get_neo4j_session)
):
    """
    分析方剂组成（含君臣佐使、类别、功效）
    """
    analysis = analyze_prescription_composition(session, name)
    if not analysis:
        return {"error": "方剂不存在"}
    return analysis

@router.get("/prescription/{name}/similar")
async def get_similar_prescriptions(
    name: str,
    limit: int = 5,
    session = Depends(get_neo4j_session)
):
    """
    查找相似的方剂（基于共享药材）
    """
    similar = find_similar_prescriptions(session, name, limit)
    return {"prescription": name, "similar_prescriptions": similar}

@router.get("/herb/{name}/prescriptions")
async def get_herb_in_prescriptions(
    name: str,
    session = Depends(get_neo4j_session)
):
    """
    获取某药材的所有方剂及其在该方剂中的角色
    """
    prescriptions = get_herb_prescriptions(session, name)
    return {"herb": name, "prescriptions": prescriptions}

@router.get("/category/{name}/prescriptions")
async def get_prescriptions_by_category_endpoint(
    name: str,
    session = Depends(get_neo4j_session)
):
    """
    获取某类别下的所有方剂
    """
    prescriptions = get_prescriptions_by_category(session, name)
    return {"category": name, "prescriptions": prescriptions}

@router.get("/efficacy/{name}/prescriptions")
async def get_prescriptions_by_efficacy_endpoint(
    name: str,
    session = Depends(get_neo4j_session)
):
    """
    获取具有某功效的所有方剂
    """
    prescriptions = get_prescriptions_by_efficacy(session, name)
    return {"efficacy": name, "prescriptions": prescriptions}

@router.get("/prescription/{name}/role/{role}/herbs")
async def get_herbs_by_role_endpoint(
    name: str,
    role: str,
    session = Depends(get_neo4j_session)
):
    """
    获取某方剂中担任特定角色的药材
    role: 君、臣、佐、使
    """
    herbs = get_herbs_by_role(session, name, role)
    return {"prescription": name, "role": role, "herbs": herbs}

@router.get("/statistics/efficacy")
async def get_efficacy_stats(
    session = Depends(get_neo4j_session)
):
    """
    获取功效统计信息
    """
    stats = get_efficacy_statistics(session)
    return {"statistics": stats}

@router.get("/statistics/category")
async def get_category_stats(
    session = Depends(get_neo4j_session)
):
    """
    获取类别统计信息
    """
    stats = get_category_statistics(session)
    return {"statistics": stats}

@router.post("/query")
async def execute_custom_query(
    query: Dict[str, str],
    session = Depends(get_neo4j_session)
):
    """
    执行自定义Cypher查询
    """
    from app.services.knowledge_graph_service import execute_cypher_query

    cypher_query = query.get("query")
    if not cypher_query:
        return {"error": "缺少查询语句"}

    try:
        results = execute_cypher_query(session, cypher_query)
        return {"results": results}
    except Exception as e:
        return {"error": str(e)}

@router.get("/overview")
async def get_graph_overview(
    session = Depends(get_neo4j_session)
):
    """
    获取知识图谱概览统计
    """
    queries = [
        "MATCH (p:Prescription) RETURN count(p) as prescription_count",
        "MATCH (h:Herb) RETURN count(h) as herb_count",
        "MATCH (r:Role) RETURN count(r) as role_count",
        "MATCH (p:Prescription) WHERE p.category IS NOT NULL RETURN count(DISTINCT p.category) as category_count",
        "MATCH (e:Efficacy) RETURN count(e) as efficacy_count",
        "MATCH ()-[r]->() RETURN count(r) as relationship_count"
    ]

    overview = {}
    for query in queries:
        result = session.run(query)
        record = result.single()
        if record:
            key = list(record.keys())[0]
            overview[key] = record[key]

    return overview
