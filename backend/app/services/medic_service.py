from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.models import models, schemas


def get_medics(db: Session, skip: int = 0, limit: int = 100):
    """获取中成药列表"""
    query = db.query(models.Medic)
    return query.offset(skip).limit(limit).all()


def get_medic(db: Session, medic_id: int):
    """根据ID获取中成药"""
    return db.query(models.Medic).filter(models.Medic.id == medic_id).first()


def create_medic(db: Session, medic: schemas.MedicCreate):
    """创建新中成药"""
    db_medic = models.Medic(**medic.dict())
    db.add(db_medic)
    db.commit()
    db.refresh(db_medic)
    return db_medic


def update_medic(db: Session, medic_id: int, medic: schemas.MedicUpdate):
    """更新中成药"""
    db_medic = db.query(models.Medic).filter(models.Medic.id == medic_id).first()
    if db_medic:
        for key, value in medic.dict(exclude_unset=True).items():
            setattr(db_medic, key, value)
        db.commit()
        db.refresh(db_medic)
    return db_medic


def delete_medic(db: Session, medic_id: int):
    """删除中成药"""
    db_medic = db.query(models.Medic).filter(models.Medic.id == medic_id).first()
    if db_medic:
        db.delete(db_medic)
        db.commit()


def search_medics(db: Session, query: str, limit: int = 10):
    """搜索中成药"""
    return db.query(models.Medic).filter(
        models.Medic.name.ilike(f"%{query}%") |
        models.Medic.english_name.ilike(f"%{query}%") |
        models.Medic.function_indication.ilike(f"%{query}%") |
        models.Medic.composition.ilike(f"%{query}%") |
        models.Medic.category.ilike(f"%{query}%") |
        models.Medic.main_category.ilike(f"%{query}%") |
        models.Medic.sub_category.ilike(f"%{query}%")
    ).limit(limit).all()


def get_medic_by_name(db: Session, name: str):
    """根据名称获取中成药"""
    return db.query(models.Medic).filter(models.Medic.name == name).first()


def get_medics_by_category(db: Session, category: str, skip: int = 0, limit: int = 100):
    """按科室类别获取中成药"""
    return db.query(models.Medic).filter(models.Medic.category == category).offset(skip).limit(limit).all()


def get_medics_by_main_category(db: Session, main_category: str, skip: int = 0, limit: int = 100):
    """按大类获取中成药"""
    return db.query(models.Medic).filter(models.Medic.main_category == main_category).offset(skip).limit(limit).all()


def get_medics_by_sub_category(db: Session, sub_category: str, skip: int = 0, limit: int = 100):
    """按小类获取中成药"""
    return db.query(models.Medic).filter(models.Medic.sub_category == sub_category).offset(skip).limit(limit).all()


def get_medic_count_by_category(db: Session):
    """按科室类别统计中成药数量"""
    return db.query(
        models.Medic.category,
        func.count(models.Medic.id).label('count')
    ).group_by(models.Medic.category).all()


def get_medic_count_by_main_category(db: Session):
    """按大类统计中成药数量"""
    return db.query(
        models.Medic.main_category,
        func.count(models.Medic.id).label('count')
    ).group_by(models.Medic.main_category).all()
