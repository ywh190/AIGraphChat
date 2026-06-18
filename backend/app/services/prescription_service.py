from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.models import models, schemas

def get_prescriptions(db: Session, skip: int = 0, limit: int = 100):
    """获取方剂列表"""
    query = db.query(models.Prescription)
    return query.offset(skip).limit(limit).all()

def get_prescription(db: Session, prescription_id: int):
    """根据ID获取方剂"""
    return db.query(models.Prescription).filter(models.Prescription.id == prescription_id).first()

def create_prescription(db: Session, prescription: schemas.PrescriptionCreate):
    """创建新方剂"""
    db_prescription = models.Prescription(**prescription.dict())
    db.add(db_prescription)
    db.commit()
    db.refresh(db_prescription)
    return db_prescription

def update_prescription(db: Session, prescription_id: int, prescription: schemas.PrescriptionCreate):
    """更新方剂"""
    db_prescription = db.query(models.Prescription).filter(models.Prescription.id == prescription_id).first()
    if db_prescription:
        for key, value in prescription.dict().items():
            setattr(db_prescription, key, value)
        db.commit()
        db.refresh(db_prescription)
    return db_prescription

def delete_prescription(db: Session, prescription_id: int):
    """删除方剂"""
    db_prescription = db.query(models.Prescription).filter(models.Prescription.id == prescription_id).first()
    if db_prescription:
        db.delete(db_prescription)
        db.commit()

def search_prescriptions(db: Session, query: str, limit: int = 10):
    """搜索方剂"""
    return db.query(models.Prescription).filter(
        models.Prescription.name.ilike(f"%{query}%") |
        models.Prescription.composition.ilike(f"%{query}%") |
        models.Prescription.function_indication.ilike(f"%{query}%")
    ).limit(limit).all()

def get_prescriptions_by_category(db: Session, category: str, sub_category: str, skip: int = 0, limit: int = 100):
    """按分类获取方剂（新模型中已移除category字段，此方法用于兼容旧API）"""
    # 注意：新的Prescription模型中已移除category、main_category、sub_category字段
    # 返回空列表以兼容旧API调用
    return []

def get_prescription_by_name(db: Session, name: str):
    """根据名称获取方剂"""
    return db.query(models.Prescription).filter(models.Prescription.name == name).first()

def get_prescription_count_by_category(db: Session):
    """按分类统计方剂数量（新模型中已移除category字段，此方法用于兼容旧API）"""
    # 注意：新的Prescription模型中已移除category、main_category、sub_category字段
    # 返回空列表以兼容旧API调用
    return []