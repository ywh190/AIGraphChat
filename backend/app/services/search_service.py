from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
from app.models import models
from app.services import prescription_service, herb_service

def search_prescriptions(db: Session, query: str, limit: int = 10):
    """搜索方剂"""
    search = f"%{query}%"
    results = db.query(models.Prescription).filter(
        or_(
            models.Prescription.name.like(search),
            models.Prescription.function_indication.like(search),
            models.Prescription.composition.like(search)
        )
    ).limit(limit).all()
    return results

def search_herbs(db: Session, query: str, limit: int = 10):
    """搜索药材"""
    search = f"%{query}%"
    results = db.query(models.Herb).filter(
        or_(
            models.Herb.name.like(search),
            models.Herb.pinyin.like(search),
            models.Herb.function.like(search),
            models.Herb.nature.like(search),
            models.Herb.meridians.like(search)
        )
    ).limit(limit).all()
    return results

def semantic_search(db: Session, query: str, limit: int = 10):
    """语义搜索（简化版本）"""
    # TODO: 实现真正的语义搜索
    # 这里先使用关键词搜索作为占位符
    return search_prescriptions(db, query, limit)

def advanced_search(db: Session, query: str):
    """高级搜索（结合关键词和语义）"""
    # TODO: 实现高级搜索
    prescriptions = search_prescriptions(db, query, 20)
    herbs = search_herbs(db, query, 20)
    return {
        "prescriptions": prescriptions,
        "herbs": herbs
    }
