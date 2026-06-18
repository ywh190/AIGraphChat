"""
数据维护管理API
提供批量操作和管理功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import List
import csv
import io
from app.db.session import get_db
from app.models import models
from app.schemas.common import (
    ResponseModel, BulkDeleteRequest, BulkUpdateRequest,
    PaginatedResponse
)
from app.schemas.prescription import PrescriptionResponse
from app.schemas.herb import HerbResponse
from app.core.dependencies import get_current_admin_user
from app.models.user import User

router = APIRouter()


# ========== 处方管理 ==========

@router.post("/prescriptions/bulk-delete", response_model=ResponseModel)
def bulk_delete_prescriptions(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量删除处方（管理员权限）"""
    try:
        deleted_count = db.query(models.Prescription).filter(
            models.Prescription.id.in_(request.ids)
        ).delete(synchronize_session=False)
        db.commit()

        return ResponseModel(
            success=True,
            message=f"成功删除 {deleted_count} 条处方",
            data={"deleted_count": deleted_count}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")


@router.post("/prescriptions/bulk-update", response_model=ResponseModel)
def bulk_update_prescriptions(
    request: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量更新处方（管理员权限）"""
    try:
        updated_count = db.query(models.Prescription).filter(
            models.Prescription.id.in_(request.ids)
        ).update(request.updates, synchronize_session=False)
        db.commit()

        return ResponseModel(
            success=True,
            message=f"成功更新 {updated_count} 条处方",
            data={"updated_count": updated_count}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")


@router.post("/prescriptions/bulk-import", response_model=ResponseModel)
def bulk_import_prescriptions(
    items: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量导入处方（管理员权限）"""
    try:
        created_count = 0
        failed_items = []

        for item in items:
            try:
                # 检查必需字段
                if not item.get('name'):
                    failed_items.append({'item': item, 'error': '缺少name字段'})
                    continue

                # 检查是否已存在相同name的记录
                existing_prescription = db.query(models.Prescription).filter(
                    models.Prescription.name == item.get('name')
                ).first()

                if existing_prescription:
                    failed_items.append({'item': item, 'error': f'Duplicate entry: name "{item.get("name")}" already exists'})
                    continue

                # 创建处方
                prescription = models.Prescription(**item)
                db.add(prescription)
                created_count += 1
            except Exception as e:
                failed_items.append({'item': item, 'error': str(e)})
                continue

        db.commit()

        result_data = {
            "created_count": created_count,
            "failed_count": len(failed_items),
            "failed_items": failed_items[:10]  # 只返回前10个失败项
        }

        message = f"导入完成：成功 {created_count} 条"
        if failed_items:
            message += f"，失败 {len(failed_items)} 条"

        return ResponseModel(
            success=True,
            message=message,
            data=result_data
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")


@router.get("/prescriptions/all", response_model=List[PrescriptionResponse])
def get_all_prescriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取所有处方（管理员专用）"""
    prescriptions = db.query(models.Prescription).offset(skip).limit(limit).all()
    return prescriptions


# ========== 药材管理 ==========

@router.post("/herbs/bulk-delete", response_model=ResponseModel)
def bulk_delete_herbs(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量删除药材（管理员权限）"""
    try:
        deleted_count = db.query(models.Herb).filter(
            models.Herb.id.in_(request.ids)
        ).delete(synchronize_session=False)
        db.commit()

        return ResponseModel(
            success=True,
            message=f"成功删除 {deleted_count} 条药材",
            data={"deleted_count": deleted_count}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")


@router.post("/herbs/bulk-update", response_model=ResponseModel)
def bulk_update_herbs(
    request: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量更新药材（管理员权限）"""
    try:
        updated_count = db.query(models.Herb).filter(
            models.Herb.id.in_(request.ids)
        ).update(request.updates, synchronize_session=False)
        db.commit()

        return ResponseModel(
            success=True,
            message=f"成功更新 {updated_count} 条药材",
            data={"updated_count": updated_count}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")


@router.post("/herbs/bulk-import", response_model=ResponseModel)
def bulk_import_herbs(
    items: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量导入药材（管理员权限）"""
    try:
        created_count = 0
        failed_items = []

        for item in items:
            try:
                # 检查必需字段
                if not item.get('name'):
                    failed_items.append({'item': item, 'error': '缺少name字段'})
                    continue

                # 检查是否已存在相同name的记录
                existing_herb = db.query(models.Herb).filter(
                    models.Herb.name == item.get('name')
                ).first()

                if existing_herb:
                    failed_items.append({'item': item, 'error': f'Duplicate entry: name "{item.get("name")}" already exists'})
                    continue

                # 创建药材
                herb = models.Herb(**item)
                db.add(herb)
                created_count += 1
            except Exception as e:
                failed_items.append({'item': item, 'error': str(e)})
                continue

        db.commit()

        result_data = {
            "created_count": created_count,
            "failed_count": len(failed_items),
            "failed_items": failed_items[:10]  # 只返回前10个失败项
        }

        message = f"导入完成：成功 {created_count} 条"
        if failed_items:
            message += f"，失败 {len(failed_items)} 条"

        return ResponseModel(
            success=True,
            message=message,
            data=result_data
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")


@router.get("/herbs/all", response_model=List[HerbResponse])
def get_all_herbs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取所有药材（管理员专用）"""
    herbs = db.query(models.Herb).offset(skip).limit(limit).all()
    return herbs


# ========== 中成药管理 ==========

@router.post("/medics/bulk-delete", response_model=ResponseModel)
def bulk_delete_medics(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量删除中成药（管理员权限）"""
    try:
        deleted_count = db.query(models.Medic).filter(
            models.Medic.id.in_(request.ids)
        ).delete(synchronize_session=False)
        db.commit()

        return ResponseModel(
            success=True,
            message=f"成功删除 {deleted_count} 条中成药",
            data={"deleted_count": deleted_count}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")


@router.post("/medics/bulk-update", response_model=ResponseModel)
def bulk_update_medics(
    request: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量更新中成药（管理员权限）"""
    try:
        updated_count = db.query(models.Medic).filter(
            models.Medic.id.in_(request.ids)
        ).update(request.updates, synchronize_session=False)
        db.commit()

        return ResponseModel(
            success=True,
            message=f"成功更新 {updated_count} 条中成药",
            data={"updated_count": updated_count}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")


@router.post("/medics/bulk-import", response_model=ResponseModel)
def bulk_import_medics(
    items: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """批量导入中成药（管理员权限）"""
    try:
        created_count = 0
        failed_items = []

        for item in items:
            try:
                # 检查必需字段
                if not item.get('name'):
                    failed_items.append({'item': item, 'error': '缺少name字段'})
                    continue

                # 检查是否已存在相同name的记录
                existing_medic = db.query(models.Medic).filter(
                    models.Medic.name == item.get('name')
                ).first()

                if existing_medic:
                    failed_items.append({'item': item, 'error': f'Duplicate entry: name "{item.get("name")}" already exists'})
                    continue

                # 创建中成药
                medic = models.Medic(**item)
                db.add(medic)
                created_count += 1
            except Exception as e:
                failed_items.append({'item': item, 'error': str(e)})
                continue

        db.commit()

        result_data = {
            "created_count": created_count,
            "failed_count": len(failed_items),
            "failed_items": failed_items[:10]  # 只返回前10个失败项
        }

        message = f"导入完成：成功 {created_count} 条"
        if failed_items:
            message += f"，失败 {len(failed_items)} 条"

        return ResponseModel(
            success=True,
            message=message,
            data=result_data
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")


@router.get("/medics/all", response_model=List)
def get_all_medics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取所有中成药（管理员专用）"""
    medics = db.query(models.Medic).offset(skip).limit(limit).all()
    return medics


# ========== 数据统计 ==========

@router.get("/statistics/overview")
def get_statistics_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取数据统计概览（管理员权限）"""
    stats = {
        "prescriptions": db.query(models.Prescription).count(),
        "herbs": db.query(models.Herb).count(),
        "efficacies": db.query(models.Efficacy).count(),
        "medics": db.query(models.Medic).count(),
    }

    return ResponseModel(
        success=True,
        message="统计信息获取成功",
        data=stats
    )


@router.get("/statistics/prescriptions-by-category")
def get_prescriptions_by_category_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取各分类处方统计（管理员权限）"""
    # 注意：新的Prescription模型中已移除category字段
    # 此端点仅用于兼容旧API，返回空数据
    return ResponseModel(
        success=True,
        message="分类统计获取成功（新模型中已移除category字段）",
        data={}
    )


@router.get("/statistics/herbs-by-category")
def get_herbs_by_category_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取各分类药材统计（管理员权限）"""
    # 注意：新的Herb模型中已移除category字段
    # 此端点仅用于兼容旧API，返回空数据
    return ResponseModel(
        success=True,
        message="分类统计获取成功（新模型中已移除category字段）",
        data={}
    )


# ========== 数据导出 ==========

@router.get("/export/prescriptions")
def export_prescriptions(
    format: str = Query("json", description="导出格式: json, csv"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """导出所有处方数据（管理员权限）"""
    prescriptions = db.query(models.Prescription).all()

    if format == "json":
        # 过滤掉SQLAlchemy内部字段
        data = []
        for p in prescriptions:
            item = {k: v for k, v in p.__dict__.items() if not k.startswith('_')}
            data.append(item)
        return ResponseModel(
            success=True,
            message="导出成功",
            data=data
        )
    elif format == "csv":
        # 定义CSV字段
        fieldnames = ['id', 'name', 'composition', 'function_indication', 'usage_dosage', 'source']
        
        # 创建内存中的CSV文件
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for p in prescriptions:
            row = {
                'id': p.id,
                'name': p.name,
                'composition': p.composition,
                'function_indication': p.function_indication,
                'usage_dosage': p.usage_dosage,
                'source': p.source
            }
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        # 返回CSV文件响应
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=prescriptions_export.csv"}
        )
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")





@router.get("/export/herbs")
def export_herbs(
    format: str = Query("json", description="导出格式: json, csv"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """导出所有药材数据（管理员权限）"""
    herbs = db.query(models.Herb).all()

    if format == "json":
        # 过滤掉SQLAlchemy内部字段
        data = []
        for h in herbs:
            item = {k: v for k, v in h.__dict__.items() if not k.startswith('_')}
            data.append(item)
        return ResponseModel(
            success=True,
            message="导出成功",
            data=data
        )
    elif format == "csv":
        # 定义CSV字段（所有主要字段）
        fieldnames = [
            'id', 'name', 'pinyin', 'aliases', 'english_name', 'source', 'source_text',
            'habitat', 'original_morphology', 'properties', 'chemical_composition',
            'meridians', 'nature', 'function', 'usage', 'discussions', 'excerpt',
            'harvest_storage', 'processing', 'clinical_application', 'storage',
            'identification', 'pharmacological_effects', 'link'
        ]
        
        # 创建内存中的CSV文件
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for h in herbs:
            row = {field: getattr(h, field, '') for field in fieldnames}
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        # 返回CSV文件响应
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=herbs_export.csv"}
        )
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")



