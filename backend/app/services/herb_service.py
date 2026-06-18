from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.models import models, schemas

def get_herbs(db: Session, skip: int = 0, limit: int = 100):
    """获取药材列表"""
    query = db.query(models.Herb)
    return query.offset(skip).limit(limit).all()

def get_herb(db: Session, herb_id: int):
    """根据ID获取药材"""
    return db.query(models.Herb).filter(models.Herb.id == herb_id).first()

def create_herb(db: Session, herb: schemas.HerbCreate):
    """创建新药材"""
    # 只包含基本字段，排除关系字段
    herb_data = herb.dict(exclude={'efficacies', 'natures', 'meridians', 'prescriptions'})
    db_herb = models.Herb(**herb_data)
    db.add(db_herb)
    db.commit()
    db.refresh(db_herb)
    return db_herb

def update_herb(db: Session, herb_id: int, herb: schemas.HerbCreate):
    """更新药材"""
    db_herb = db.query(models.Herb).filter(models.Herb.id == herb_id).first()
    if db_herb:
        update_data = herb.dict(exclude_unset=True)  # 只包含已设置的字段
        for key, value in update_data.items():
            # 跳过None值和关系字段
            if value is not None and key not in ['efficacies', 'natures', 'meridians', 'prescriptions']:
                setattr(db_herb, key, value)
        db.commit()
        db.refresh(db_herb)
    return db_herb

def delete_herb(db: Session, herb_id: int):
    """删除药材"""
    db_herb = db.query(models.Herb).filter(models.Herb.id == herb_id).first()
    if db_herb:
        db.delete(db_herb)
        db.commit()

def search_herbs(db: Session, query: str, limit: int = 10):
    """搜索药材"""
    return db.query(models.Herb).filter(
        models.Herb.name.ilike(f"%{query}%") |
        models.Herb.pinyin.ilike(f"%{query}%") |
        models.Herb.function.ilike(f"%{query}%") |
        models.Herb.nature.ilike(f"%{query}%") |
        models.Herb.meridians.ilike(f"%{query}%")
    ).limit(limit).all()

def get_herb_by_name(db: Session, name: str):
    """根据名称获取药材"""
    return db.query(models.Herb).filter(models.Herb.name == name).first()

def get_herbs_by_category(db: Session, category: str, skip: int = 0, limit: int = 100):
    """按分类获取药材（兼容旧API，实际按nature筛选）"""
    return db.query(models.Herb).filter(models.Herb.nature == category).offset(skip).limit(limit).all()

def get_herb_count_by_category(db: Session):
    """按分类统计药材数量（实际按nature分组）"""
    return db.query(
        models.Herb.nature,
        func.count(models.Herb.id).label('count')
    ).group_by(models.Herb.nature).all()

def get_herbs_in_prescription(db: Session, prescription_id: int):
    """获取方剂中的药材"""
    prescription = db.query(models.Prescription).filter(models.Prescription.id == prescription_id).first()
    if prescription:
        return prescription.herbs
    return []

def get_prescriptions_with_herb(db: Session, herb_id: int):
    """获取包含某药材的方剂"""
    herb = db.query(models.Herb).filter(models.Herb.id == herb_id).first()
    if herb:
        return herb.prescriptions
    return []