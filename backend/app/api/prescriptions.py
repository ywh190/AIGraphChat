from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models import models, schemas
from app.schemas.prescription import (
    PrescriptionCreate, PrescriptionUpdate, PrescriptionResponse,
    PrescriptionListResponse, PrescriptionSearchRequest
)
from app.schemas.common import ResponseModel
from app.services import prescription_service
from app.core.dependencies import get_current_active_user, get_current_admin_user
from app.models.user import User

router = APIRouter()


@router.get("/statistics")
def get_prescription_statistics(db: Session = Depends(get_db)):
    """获取方剂统计分析数据 - SQL聚合版"""
    from sqlalchemy import func, text
    
    # 获取总数
    total = db.execute(text("SELECT COUNT(*) FROM prescriptions")).scalar() or 0
    
    # 高频功效TOP10 - 使用中医药标准功效关键词进行准确统计
    efficacy_keywords = [
        '清热', '解毒', '消肿', '止痛', '活血', '化瘀', '祛风', '除湿', 
        '止咳', '化痰', '健脾', '益气', '养血', '滋阴', '补肾', '利尿',
        '通便', '止血', '散结', '理气', '疏肝', '和胃', '安神', '明目',
        '解表', '发汗', '疏散', '泻火', '凉血', '补气', '温阳', '固涩',
        '消食', '导滞', '平喘', '润肺', '通络', '破血', '软坚', '开窍'
    ]
    
    efficacy_counts = {}
    for keyword in efficacy_keywords:
        result = db.execute(text(f"SELECT COUNT(*) FROM prescriptions WHERE function_indication LIKE :pattern"), {"pattern": f"%{keyword}%"}).scalar()
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
    
    # 组成复杂度分布 - 基于字符串长度
    short_count = db.execute(text("SELECT COUNT(*) FROM prescriptions WHERE LENGTH(composition) <= 50")).scalar() or 0
    medium_count = db.execute(text("SELECT COUNT(*) FROM prescriptions WHERE LENGTH(composition) BETWEEN 51 AND 100")).scalar() or 0
    long_count = db.execute(text("SELECT COUNT(*) FROM prescriptions WHERE LENGTH(composition) BETWEEN 101 AND 200")).scalar() or 0
    extra_long_count = db.execute(text("SELECT COUNT(*) FROM prescriptions WHERE LENGTH(composition) > 200")).scalar() or 0
    
    composition_data = [
        {"name": "短方(≤5味)", "value": short_count, "percentage": round(short_count / total * 100, 2) if total > 0 else 0},
        {"name": "中方(6-8味)", "value": medium_count, "percentage": round(medium_count / total * 100, 2) if total > 0 else 0},
        {"name": "长方(9-12味)", "value": long_count, "percentage": round(long_count / total * 100, 2) if total > 0 else 0},
        {"name": "超长方(>12味)", "value": extra_long_count, "percentage": round(extra_long_count / total * 100, 2) if total > 0 else 0}
    ]
    
    # 经典药对TOP12 - 修正版：准确提取药材并改进配伍算法
    top_herb_pairs = []
    try:
        from collections import Counter
        import re
        
        # 获取所有有效方剂的组成（限制在1000条以内以保证性能）
        all_compositions = db.execute(text("""
            SELECT composition FROM prescriptions 
            WHERE composition IS NOT NULL AND composition != '' 
            LIMIT 1000
        """)).fetchall()
        
        herb_pair_count = Counter()
        valid_prescription_count = 0  # 实际包含有效药材对的方剂数量
        
        # 定义需要排除的制法描述和无效关键词
        invalid_keywords = [
            '制法', '上为', '细末', '研末', '共研', '捣碎', '煎服', '水煎',
            '服法', '用法', '用量', '主治', '功效', '注意', '禁忌', '贮藏',
            '制备', '加工', '炮制', '处方', '方解', '方义', '配伍', '特点',
            '加减', '变化', '化裁', '现代', '应用', '研究', '临床', '实验'
        ]
        
        for (composition,) in all_compositions:
            if not composition:
                continue
                
            # 准确提取药材名称，排除剂量信息和制法描述
            # 支持多种分隔符和剂量格式
            herbs_raw = re.split(r'[、,，;；\s\n]+', composition.strip())
            herbs_clean = []
            
            for herb in herbs_raw:
                herb = herb.strip()
                if not herb:
                    continue
                    
                # 跳过包含制法关键词的条目
                skip_herb = False
                for invalid_kw in invalid_keywords:
                    if invalid_kw in herb:
                        skip_herb = True
                        break
                if skip_herb:
                    continue
                
                # 移除剂量信息（数字+单位，或中文数字+单位）
                # 匹配模式：10g, 3克, 三钱, 二两, 5mg 等
                herb_no_dose = re.sub(r'[\d一二三四五六七八九十百千]+[g克钱分两mg毫微]*$', '', herb)
                herb_no_dose = herb_no_dose.strip()
                
                # 过滤无效内容
                if herb_no_dose and len(herb_no_dose) >= 2:  # 药材名至少2个字符
                    # 额外验证：排除纯数字、纯符号等无效内容
                    if not re.match(r'^[\d\s\-_\.]+$', herb_no_dose):
                        herbs_clean.append(herb_no_dose)
            
            # 只处理包含至少2味有效药材的方剂
            if len(herbs_clean) >= 2:
                valid_prescription_count += 1
                # 生成所有可能的药材对（保持原始顺序，避免重复）
                for i in range(len(herbs_clean)):
                    for j in range(i + 1, len(herbs_clean)):
                        # 创建规范化的药对（按字母顺序排列，避免(A,B)和(B,A)重复）
                        herb1, herb2 = sorted([herbs_clean[i], herbs_clean[j]])
                        herb_pair_count[(herb1, herb2)] += 1
        
        # 计算TOP12药对
        if valid_prescription_count > 0:
            top_herb_pairs = [
                {
                    "herb1": pair[0], 
                    "herb2": pair[1], 
                    "count": count,
                    "percentage": round(count / valid_prescription_count * 100, 2)
                }
                for pair, count in herb_pair_count.most_common(12)
            ]
    except Exception as e:
        print(f"药对统计错误: {e}")
        pass
    
    return {
        "total": total,
        "compositionData": composition_data,
        "topEfficacies": top_efficacies,
        "topHerbPairs": top_herb_pairs
    }


@router.get("/", response_model=PrescriptionListResponse)
def get_prescriptions(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="限制数量"),
    db: Session = Depends(get_db)
):
    """获取方剂列表"""
    prescriptions = prescription_service.get_prescriptions(db, skip=skip, limit=limit)
    total = db.query(models.Prescription).count()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": prescriptions
    }


@router.get("/{prescription_id}", response_model=PrescriptionResponse)
def get_prescription(prescription_id: int, db: Session = Depends(get_db)):
    """根据ID获取方剂详情"""
    prescription = prescription_service.get_prescription(db, prescription_id=prescription_id)
    if prescription is None:
        raise HTTPException(status_code=404, detail="方剂不存在")
    return prescription


@router.post("/", response_model=PrescriptionResponse, status_code=201)
def create_prescription(
    prescription: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """创建新方剂（需要管理员权限）"""
    return prescription_service.create_prescription(db, prescription)


@router.put("/{prescription_id}", response_model=PrescriptionResponse)
def update_prescription(
    prescription_id: int,
    prescription: PrescriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """更新方剂信息（需要管理员权限）"""
    db_prescription = prescription_service.get_prescription(db, prescription_id=prescription_id)
    if db_prescription is None:
        raise HTTPException(status_code=404, detail="方剂不存在")
    return prescription_service.update_prescription(db, prescription_id, prescription)


@router.delete("/{prescription_id}", response_model=ResponseModel)
def delete_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """删除方剂（需要管理员权限）"""
    db_prescription = prescription_service.get_prescription(db, prescription_id=prescription_id)
    if db_prescription is None:
        raise HTTPException(status_code=404, detail="方剂不存在")
    prescription_service.delete_prescription(db, prescription_id)
    return ResponseModel(
        success=True,
        message="方剂删除成功"
    )


@router.post("/search", response_model=PrescriptionListResponse)
def search_prescriptions(
    search_request: PrescriptionSearchRequest,
    db: Session = Depends(get_db)
):
    """搜索方剂"""
    keyword = search_request.keyword.strip() if search_request.keyword else None
    search_type = search_request.search_type or 'all'
    skip = search_request.skip
    limit = search_request.limit

    # 搜索逻辑
    query = db.query(models.Prescription)

    if keyword:
        if search_type == 'name':
            # 只搜索名称
            query = query.filter(models.Prescription.name.contains(keyword))
        elif search_type == 'composition':
            # 只搜索组成
            query = query.filter(models.Prescription.composition.contains(keyword))
        elif search_type == 'function':
            # 只搜索功效
            query = query.filter(models.Prescription.function_indication.contains(keyword))
        else:
            # 全部搜索
            query = query.filter(
                (models.Prescription.name.contains(keyword)) |
                (models.Prescription.composition.contains(keyword)) |
                (models.Prescription.function_indication.contains(keyword))
            )

    total = query.count()
    prescriptions = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": prescriptions
    }


@router.get("/category/{category}/subcategory/{sub_category}", response_model=List[PrescriptionResponse])
def get_prescriptions_by_category(
    category: str,
    sub_category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """按分类获取方剂（兼容旧API，但新模型中已移除category字段）"""
    # 注意：新的Prescription模型中已移除category、main_category、sub_category字段
    # 此端点仅用于兼容旧API，返回空列表或根据需要调整逻辑
    return []