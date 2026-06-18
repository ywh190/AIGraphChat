from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models import models
from app.models.schemas import (
    MedicCreate, MedicUpdate, Medic,
    MedicListResponse, MedicSearchRequest
)
from app.services import medic_service
from app.core.dependencies import get_current_active_user, get_current_admin_user
from app.models.user import User

router = APIRouter()


@router.get("/statistics")
def get_medic_statistics(db: Session = Depends(get_db)):
    """获取中成药统计分析数据 - 修正版"""
    from sqlalchemy import func, text
    import re
    
    # 获取总数
    total = db.execute(text("SELECT COUNT(*) FROM medics")).scalar() or 0
    
    # 科室分布 - 原生SQL
    category_results = db.execute(text("""
        SELECT category, COUNT(*) as cnt 
        FROM medics 
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category 
        ORDER BY cnt DESC 
        LIMIT 10
    """)).fetchall()
    
    category_data = [
        {"name": r[0], "value": r[1], "percentage": round(r[1] / total * 100, 2) if total > 0 else 0}
        for r in category_results if r[0]
    ]
    
    # 高频功效TOP10 - 使用中医药标准功效关键词进行准确统计
    efficacy_keywords = [
        '清热', '解毒', '消肿', '止痛', '活血', '化瘀', '祛风', '除湿', 
        '止咳', '化痰', '健脾', '益气', '养血', '滋阴', '补肾', '利尿',
        '通便', '止血', '散结', '理气', '疏肝', '和胃', '安神', '明目',
        '解表', '发汗', '疏散', '泻火', '凉血', '补气', '温阳', '固涩',
        '消食', '导滞', '平喘', '润肺', '通络', '破血', '软坚', '开窍',
        '抗菌', '抗炎', '消炎', '镇痛', '镇静', '调节免疫'
    ]
    
    efficacy_counts = {}
    for keyword in efficacy_keywords:
        result = db.execute(text(f"SELECT COUNT(*) FROM medics WHERE function_indication LIKE :pattern"), {"pattern": f"%{keyword}%"}).scalar()
        if result and result > 0:
            efficacy_counts[keyword] = result
    
    # 按频次排序，取TOP10
    sorted_efficacies = sorted(efficacy_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    top_efficacies = [
        {
            "name": keyword, 
            "value": count, 
            "percentage": round(count / total * 100, 2) if total > 0 else 0
        }
        for keyword, count in sorted_efficacies
    ]
    
    # 组方复杂度分布 - 基于组成字段长度（保持原有逻辑，因为中成药组成相对规范）
    simple_count = db.execute(text("SELECT COUNT(*) FROM medics WHERE LENGTH(composition) <= 30")).scalar() or 0
    medium_count = db.execute(text("SELECT COUNT(*) FROM medics WHERE LENGTH(composition) BETWEEN 31 AND 80")).scalar() or 0
    complex_count = db.execute(text("SELECT COUNT(*) FROM medics WHERE LENGTH(composition) BETWEEN 81 AND 150")).scalar() or 0
    very_complex_count = db.execute(text("SELECT COUNT(*) FROM medics WHERE LENGTH(composition) > 150")).scalar() or 0
    
    herb_count_data = [
        {"name": "单方(1-2味)", "value": simple_count, "percentage": round(simple_count / total * 100, 2) if total > 0 else 0},
        {"name": "小方(3-5味)", "value": medium_count, "percentage": round(medium_count / total * 100, 2) if total > 0 else 0},
        {"name": "中方(6-10味)", "value": complex_count, "percentage": round(complex_count / total * 100, 2) if total > 0 else 0},
        {"name": "复方(>10味)", "value": very_complex_count, "percentage": round(very_complex_count / total * 100, 2) if total > 0 else 0}
    ]
    
    return {
        "total": total,
        "categoryData": category_data,
        "topEfficacies": top_efficacies,
        "herbCountDistribution": herb_count_data
    }


@router.get("/", response_model=MedicListResponse)
def get_medics(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="限制数量"),
    db: Session = Depends(get_db)
):
    """获取中成药列表"""
    medics = medic_service.get_medics(db, skip=skip, limit=limit)
    total = db.query(models.Medic).count()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": medics
    }


# 更具体的路由必须先定义，以避免与 /{medic_id} 冲突
@router.get("/name/{name}", response_model=Medic)
def get_medic_by_name(name: str, db: Session = Depends(get_db)):
    """根据名称获取中成药"""
    medic = medic_service.get_medic_by_name(db, name)
    if medic is None:
        raise HTTPException(status_code=404, detail="中成药不存在")
    return medic


@router.get("/category/{category}", response_model=List[Medic])
def get_medics_by_category(
    category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """按科室类别获取中成药"""
    return medic_service.get_medics_by_category(db, category, skip, limit)


@router.get("/main-category/{main_category}", response_model=List[Medic])
def get_medics_by_main_category(
    main_category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """按大类获取中成药"""
    return medic_service.get_medics_by_main_category(db, main_category, skip, limit)


@router.get("/sub-category/{sub_category}", response_model=List[Medic])
def get_medics_by_sub_category(
    sub_category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """按小类获取中成药"""
    return medic_service.get_medics_by_sub_category(db, sub_category, skip, limit)


@router.post("/", response_model=Medic, status_code=201)
def create_medic(
    medic: MedicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """创建新中成药（需要管理员权限）"""
    # 检查名称是否已存在
    existing = medic_service.get_medic_by_name(db, medic.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"中成药 '{medic.name}' 已存在")

    try:
        return medic_service.create_medic(db, medic)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建中成药失败: {str(e)}")


@router.put("/{medic_id}", response_model=Medic)
def update_medic(
    medic_id: int,
    medic: MedicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """更新中成药（需要管理员权限）"""
    db_medic = medic_service.get_medic(db, medic_id)
    if db_medic is None:
        raise HTTPException(status_code=404, detail="中成药不存在")

    try:
        return medic_service.update_medic(db, medic_id, medic)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新中成药失败: {str(e)}")


@router.delete("/{medic_id}")
def delete_medic(
    medic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """删除中成药（需要管理员权限）"""
    db_medic = medic_service.get_medic(db, medic_id)
    if db_medic is None:
        raise HTTPException(status_code=404, detail="中成药不存在")

    try:
        medic_service.delete_medic(db, medic_id)
        return {"message": "中成药删除成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除中成药失败: {str(e)}")


@router.post("/search", response_model=MedicListResponse)
def search_medics(request: MedicSearchRequest, db: Session = Depends(get_db)):
    """搜索中成药"""
    query = db.query(models.Medic)
    search_type = request.search_type or 'all'
    
    # 关键词搜索（去除前后空格）
    keyword = request.keyword.strip() if request.keyword else None
    if keyword:
        search_pattern = f"%{keyword}%"
        if search_type == 'name':
            # 只搜索名称
            query = query.filter(
                models.Medic.name.ilike(search_pattern) |
                models.Medic.english_name.ilike(search_pattern)
            )
        elif search_type == 'composition':
            # 只搜索组成
            query = query.filter(models.Medic.composition.ilike(search_pattern))
        elif search_type == 'function':
            # 只搜索功效
            query = query.filter(models.Medic.function_indication.ilike(search_pattern))
        else:
            # 全部搜索
            query = query.filter(
                models.Medic.name.ilike(search_pattern) |
                models.Medic.english_name.ilike(search_pattern) |
                models.Medic.function_indication.ilike(search_pattern) |
                models.Medic.composition.ilike(search_pattern)
            )

    # 按科室类别筛选
    if request.category:
        query = query.filter(models.Medic.category == request.category)

    # 按大类筛选
    if request.main_category:
        query = query.filter(models.Medic.main_category == request.main_category)

    # 按小类筛选
    if request.sub_category:
        query = query.filter(models.Medic.sub_category == request.sub_category)

    # 获取总数
    total = query.count()
    
    # 获取分页数据
    medics = query.offset(request.skip).limit(request.limit).all()
    
    return {
        "total": total,
        "skip": request.skip,
        "limit": request.limit,
        "items": medics
    }
