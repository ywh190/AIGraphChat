from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import re
from app.models import models

def query_knowledge(db: Session, question: str, limit: int = 5) -> List[Dict]:
    """查询知识库 - 基于关键词匹配"""
    results = []
    
    # 搜索药材
    herbs = db.query(models.Herb).filter(
        models.Herb.name.contains(question) |
        models.Herb.function.contains(question) |
        models.Herb.nature.contains(question) |
        models.Herb.meridians.contains(question)
    ).limit(limit // 2).all()
    
    for herb in herbs:
        results.append({
            "content": f"药材名称: {herb.name}\n性味: {herb.nature or '未知'}\n归经: {herb.meridians or '未知'}\n功效: {herb.function or '未知'}",
            "source": f"药材数据库 - {herb.name}",
            "score": 0.9,
            "type": "herb"
        })
    
    # 搜索方剂
    prescriptions = db.query(models.Prescription).filter(
        models.Prescription.name.contains(question) |
        models.Prescription.function_indication.contains(question) |
        models.Prescription.composition.contains(question)
    ).limit(limit // 2).all()
    
    for prescription in prescriptions:
        results.append({
            "content": f"方剂名称: {prescription.name}\n组成: {prescription.composition or '未知'}\n功效主治: {prescription.function_indication or '未知'}\n来源: {prescription.source or '未知'}",
            "source": f"方剂数据库 - {prescription.name}",
            "score": 0.85,
            "type": "prescription"
        })
    
    # 搜索中成药
    medics = db.query(models.Medic).filter(
        models.Medic.name.contains(question) |
        models.Medic.function_indication.contains(question) |
        models.Medic.composition.contains(question)
    ).limit(limit // 2).all()
    
    for medic in medics:
        results.append({
            "content": f"中成药名称: {medic.name}\n组成: {medic.composition or '未知'}\n功能主治: {medic.function_indication or '未知'}\n科室: {medic.category or '未知'}",
            "source": f"中成药数据库 - {medic.name}",
            "score": 0.8,
            "type": "medic"
        })
    
    # 如果没有结果，尝试分词搜索
    if not results and len(question) > 2:
        keywords = extract_keywords(question)
        for keyword in keywords[:3]:
            if len(keyword) >= 2:
                herb_results = db.query(models.Herb).filter(
                    models.Herb.name.contains(keyword) |
                    models.Herb.function.contains(keyword)
                ).limit(1).all()
                
                for herb in herb_results:
                    results.append({
                        "content": f"药材名称: {herb.name}\n性味: {herb.nature or '未知'}\n功效: {herb.function or '未知'}",
                        "source": f"药材数据库 - {herb.name} (关键词: {keyword})",
                        "score": 0.7,
                        "type": "herb"
                    })
    
    return results[:limit]

def extract_keywords(text: str) -> List[str]:
    """简单关键词提取"""
    # 移除标点符号
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    # 返回长度>=2的词
    return [word for word in words if len(word) >= 2]

def retrieve_documents(db: Session, query: str, limit: int = 10) -> List[Dict]:
    """检索相关文档"""
    knowledge_results = query_knowledge(db, query, limit)
    documents = []
    
    for result in knowledge_results:
        documents.append({
            "text": result["content"],
            "metadata": {
                "source": result["source"],
                "type": result.get("type", "unknown"),
                "score": result.get("score", 0.0)
            }
        })
    
    return documents

def generate_response(db: Session, query: str, context: List[Dict]) -> str:
    """生成响应 - 这个功能由ai_service处理"""
    if not context:
        return "未找到相关信息。"
    
    # 简单汇总上下文
    context_text = "\n".join([item.get("content", "") for item in context[:3]])
    return f"基于以下信息：\n{context_text}\n\n针对问题 '{query}' 的回答需要调用AI模型进行生成。"