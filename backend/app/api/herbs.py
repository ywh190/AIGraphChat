from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models import models, schemas
from app.schemas.herb import (
    HerbCreate, HerbUpdate, HerbResponse,
    HerbListResponse, HerbSearchRequest
)
from app.schemas.common import ResponseModel
from app.services import herb_service
from app.core.dependencies import get_current_active_user, get_current_admin_user
from app.models.user import User

router = APIRouter()


@router.get("/statistics")
def get_herb_statistics(db: Session = Depends(get_db)):
    """获取药材统计分析数据 - SQL聚合版"""
    from sqlalchemy import func, text
    
    # 获取总数
    total = db.query(func.count(models.Herb.id)).scalar()
    
    # 四气统计 - 使用原生SQL
    four_qi = ['寒', '热', '温', '凉', '平']
    nature_data = []
    for qi in four_qi:
        result = db.execute(text(f"SELECT COUNT(*) FROM herbs WHERE nature LIKE :pattern"), {"pattern": f"%{qi}%"}).scalar()
        if result > 0:
            nature_data.append({
                "name": qi, 
                "value": result, 
                "percentage": round(result / total * 100, 2) if total > 0 else 0
            })
    nature_data.sort(key=lambda x: x['value'], reverse=True)
    
    # 五味统计
    five_flavors = ['辛', '甘', '酸', '苦', '咸', '淡']
    flavor_data = []
    for flavor in five_flavors:
        result = db.execute(text(f"SELECT COUNT(*) FROM herbs WHERE nature LIKE :pattern"), {"pattern": f"%{flavor}%"}).scalar()
        if result > 0:
            flavor_data.append({
                "name": flavor, 
                "value": result, 
                "percentage": round(result / total * 100, 2) if total > 0 else 0
            })
    flavor_data.sort(key=lambda x: x['value'], reverse=True)
    
    # 归经统计
    meridians_list = ['肝', '心', '脾', '肺', '肾', '胃', '胆', '大肠', '小肠', '膀胱', '三焦', '心包']
    meridian_data = []
    for meridian in meridians_list:
        result = db.execute(text(f"SELECT COUNT(*) FROM herbs WHERE meridians LIKE :pattern"), {"pattern": f"%{meridian}%"}).scalar()
        if result > 0:
            meridian_data.append({
                "name": meridian + '经', 
                "value": result, 
                "percentage": round(result / total * 100, 2) if total > 0 else 0
            })
    meridian_data.sort(key=lambda x: x['value'], reverse=True)
    meridian_data = meridian_data[:12]
    
    # 功效统计
    common_functions = [
        '清热', '解毒', '消肿', '止痛', '活血', '化瘀', '祛风', '除湿', 
        '止咳', '化痰', '健脾', '益气', '养血', '滋阴', '补肾', '利尿',
        '通便', '止血', '散结', '理气', '疏肝', '和胃', '安神', '明目'
    ]
    function_data = []
    for func_keyword in common_functions:
        result = db.execute(text(f"SELECT COUNT(*) FROM herbs WHERE `function` LIKE :pattern"), {"pattern": f"%{func_keyword}%"}).scalar()
        if result > 0:
            function_data.append({
                "name": func_keyword, 
                "value": result, 
                "percentage": round(result / total * 100, 2) if total > 0 else 0
            })
    function_data.sort(key=lambda x: x['value'], reverse=True)
    function_data = function_data[:15]
    
    return {
        "total": total,
        "natureData": nature_data,
        "flavorData": flavor_data,
        "meridianData": meridian_data,
        "functionData": function_data
    }


@router.get("/", response_model=HerbListResponse)
def get_herbs(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="限制数量"),
    db: Session = Depends(get_db)
):
    """获取药材列表"""
    herbs = herb_service.get_herbs(db, skip=skip, limit=limit)
    total = db.query(models.Herb).count()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": herbs
    }


@router.get("/{herb_id}", response_model=HerbResponse)
def get_herb(herb_id: int, db: Session = Depends(get_db)):
    """根据ID获取药材详情"""
    herb = herb_service.get_herb(db, herb_id=herb_id)
    if herb is None:
        raise HTTPException(status_code=404, detail="药材不存在")
    return herb


@router.post("/", response_model=HerbResponse, status_code=201)
def create_herb(
    herb: HerbCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """创建新药材（需要管理员权限）"""
    return herb_service.create_herb(db, herb)


@router.put("/{herb_id}", response_model=HerbResponse)
def update_herb(
    herb_id: int,
    herb: HerbUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """更新药材信息（需要管理员权限）"""
    db_herb = herb_service.get_herb(db, herb_id=herb_id)
    if db_herb is None:
        raise HTTPException(status_code=404, detail="药材不存在")
    return herb_service.update_herb(db, herb_id, herb)


@router.delete("/{herb_id}", response_model=ResponseModel)
def delete_herb(
    herb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """删除药材（需要管理员权限）"""
    db_herb = herb_service.get_herb(db, herb_id=herb_id)
    if db_herb is None:
        raise HTTPException(status_code=404, detail="药材不存在")
    herb_service.delete_herb(db, herb_id)
    return ResponseModel(
        success=True,
        message="药材删除成功"
    )


@router.post("/search", response_model=HerbListResponse)
def search_herbs(
    search_request: HerbSearchRequest,
    db: Session = Depends(get_db)
):
    """搜索药材"""
    keyword = search_request.keyword.strip() if search_request.keyword else None
    search_type = search_request.search_type or 'all'
    nature = search_request.nature
    skip = search_request.skip
    limit = search_request.limit

    # 搜索逻辑
    query = db.query(models.Herb)

    if keyword:
        if search_type == 'name':
            # 只搜索名称
            query = query.filter(
                (models.Herb.name.contains(keyword)) |
                (models.Herb.pinyin.contains(keyword)) |
                (models.Herb.aliases.contains(keyword))
            )
        elif search_type == 'function':
            # 只搜索功效
            query = query.filter(models.Herb.function.contains(keyword))
        elif search_type == 'nature':
            # 只搜索性味
            query = query.filter(models.Herb.nature.contains(keyword))
        else:
            # 全部搜索
            query = query.filter(
                (models.Herb.name.contains(keyword)) |
                (models.Herb.pinyin.contains(keyword)) |
                (models.Herb.function.contains(keyword)) |
                (models.Herb.nature.contains(keyword))
            )

    if nature:
        query = query.filter(models.Herb.nature.contains(nature))

    total = query.count()
    herbs = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": herbs
    }


@router.get("/name/{name}", response_model=HerbResponse)
def get_herb_by_name(name: str, db: Session = Depends(get_db)):
    """根据名称获取药材"""
    herb = herb_service.get_herb_by_name(db, name)
    if herb is None:
        raise HTTPException(status_code=404, detail="药材不存在")
    return herb


@router.get("/category/{category}", response_model=List[HerbResponse])
def get_herbs_by_category(
    category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """按性味（nature）获取药材（兼容旧API）"""
    return herb_service.get_herbs_by_category(db, category, skip, limit)