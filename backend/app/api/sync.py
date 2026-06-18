"""
数据同步API
提供MySQL和Neo4j之间数据同步的接口
支持实时进度追踪
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from threading import Lock

from app.services.sync_service import sync_service, SyncDirection

router = APIRouter()

# 全局进度存储
_sync_progress = {}
_progress_lock = Lock()


class SyncRequest(BaseModel):
    """同步请求模型"""
    direction: str = "mysql_to_neo4j"  # mysql_to_neo4j, neo4j_to_mysql, bidirectional
    sync_prescriptions: bool = True
    sync_herbs: bool = True
    sync_medics: bool = True
    sync_relationships: bool = True
    sync_attributes: bool = True
    incremental: bool = False  # True为增量同步，False为全量同步
    limit: Optional[int] = None  # 限制同步数量（用于测试）
    batch_size: int = 1000  # 批量操作大小


class SyncResponse(BaseModel):
    """同步响应模型"""
    success: bool
    message: str
    data: Optional[dict] = None


def progress_callback(progress_data: dict):
    """进度回调函数,存储进度数据供API查询"""
    try:
        from app.cache import redis_client
        # 将进度数据存储到Redis，设置较短的过期时间(1小时)
        redis_client.set('sync_progress', progress_data, ttl=3600)

        # 同时更新内存变量作为备份
        with _progress_lock:
            _sync_progress.update(progress_data)
    except Exception as e:
        print(f"[ERROR] 存储进度数据失败: {e}")
        # 即使Redis失败，也更新内存变量
        with _progress_lock:
            _sync_progress.update(progress_data)


@router.post("", response_model=SyncResponse)
async def trigger_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    触发数据同步(同步执行,返回完整结果)
    
    Example:
        POST /api/sync
        {
            "direction": "mysql_to_neo4j",
            "sync_prescriptions": true,
            "sync_herbs": true,
            "sync_relationships": true,
            "sync_attributes": true,
            "incremental": false
        }
    """
    try:
        # 设置进度回调
        sync_service.set_progress_callback(progress_callback)
        
        if request.incremental:
            # 增量同步
            result = sync_service.incremental_sync(
                sync_prescriptions=request.sync_prescriptions,
                sync_herbs=request.sync_herbs,
                sync_medics=request.sync_medics
            )
        else:
            # 全量同步
            result = sync_service.full_sync_mysql_to_neo4j(
                sync_prescriptions=request.sync_prescriptions,
                sync_herbs=request.sync_herbs,
                sync_medics=request.sync_medics,
                sync_relationships=request.sync_relationships,
                sync_attributes=request.sync_attributes,
                batch_size=request.batch_size
            )
        
        return SyncResponse(
            success=True,
            message="数据同步完成",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/background")
async def trigger_sync_background(
    request: SyncRequest,
    background_tasks: BackgroundTasks
):
    """
    后台触发数据同步（异步执行）
    
    适用于大量数据同步，不会阻塞API响应
    可通过 /api/sync/progress 查询实时进度
    """
    def do_sync():
        sync_service.set_progress_callback(progress_callback)
        sync_service.full_sync_mysql_to_neo4j(
            sync_prescriptions=request.sync_prescriptions,
            sync_herbs=request.sync_herbs,
            sync_medics=request.sync_medics,
            sync_relationships=request.sync_relationships,
            sync_attributes=request.sync_attributes,
            batch_size=request.batch_size
        )
    
    background_tasks.add_task(do_sync)
    
    return {
        "success": True,
        "message": "同步任务已提交到后台执行",
        "status": "running",
        "use_progress_endpoint": "/api/sync/progress"
    }


@router.get("/status")
async def get_sync_status():
    """获取同步状态"""
    status = sync_service.get_sync_status()
    return {
        "success": True,
        "data": status
    }


@router.get("/progress")
async def get_sync_progress():
    """
    获取同步进度
    
    返回当前同步任务的实时进度信息,包括:
    - progress: 进度百分比 (0-100)
    - current_step: 当前步骤名称
    - message: 当前消息
    - status: 同步状态
    - in_progress: 是否正在同步
    """
    try:
        from app.cache import redis_client
        # 优先从Redis读取进度数据
        progress_data = redis_client.get('sync_progress')

        if progress_data:
            # Redis中有数据，直接返回
            return {
                "success": True,
                "data": progress_data
            }
        else:
            # Redis中没有数据，尝试从内存变量读取
            with _progress_lock:
                progress_data = _sync_progress.copy()

            return {
                "success": True,
                "data": progress_data or {
                    "progress": 0,
                    "current_step": "idle",
                    "message": "没有正在进行的同步任务",
                    "status": "idle",
                    "in_progress": False
                }
            }
    except Exception as e:
        print(f"[ERROR] 获取进度数据失败: {e}")
        # 出错时返回默认值
        return {
            "success": True,
            "data": {
                "progress": 0,
                "current_step": "idle",
                "message": "获取进度数据失败",
                "status": "error",
                "in_progress": False
            }
        }
    
@router.get("/validate")
async def validate_consistency():
    """
    验证MySQL和Neo4j数据一致性
    
    比较两个数据库中的数据量，返回差异报告
    """
    from app.db.session import get_db, get_neo4j_driver
    
    try:
        from app.core.config import settings
        mysql_db = next(get_db())
        driver = get_neo4j_driver()
        
        with driver.session(database=settings.NEO4J_DATABASE) as neo4j_session:
            result = sync_service.validate_data_consistency(
                mysql_db, neo4j_session
            )
        
        driver.close()
        
        return {
            "success": True,
            "data": result,
            "message": "数据一致性验证完成" if result['consistent'] else "发现数据不一致"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")


@router.post("/incremental")
async def incremental_sync(
    since: Optional[datetime] = None,
    sync_prescriptions: bool = True,
    sync_herbs: bool = True,
    sync_medics: bool = True
):
    """
    执行增量同步（同步执行）
    
    Args:
        since: 同步该时间之后更新的数据
    """
    try:
        # 设置进度回调
        sync_service.set_progress_callback(progress_callback)
        
        result = sync_service.incremental_sync(
            since=since,
            sync_prescriptions=sync_prescriptions,
            sync_herbs=sync_herbs,
            sync_medics=sync_medics
        )
        
        return {
            "success": True,
            "message": "增量同步完成",
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"增量同步失败: {str(e)}")


class IncrementalSyncRequest(BaseModel):
    """增量同步请求模型"""
    since: Optional[datetime] = None
    sync_prescriptions: bool = True
    sync_herbs: bool = True
    sync_medics: bool = True


@router.post("/incremental/background")
async def incremental_sync_background(
    background_tasks: BackgroundTasks,
    request: IncrementalSyncRequest
):
    """
    后台执行增量同步（异步执行）
    
    适用于大量数据同步，不会阻塞API响应
    可通过 /api/sync/progress 查询实时进度
    """
    def do_incremental_sync():
        sync_service.set_progress_callback(progress_callback)
        sync_service.incremental_sync(
            since=request.since,
            sync_prescriptions=request.sync_prescriptions,
            sync_herbs=request.sync_herbs,
            sync_medics=request.sync_medics
        )
    
    background_tasks.add_task(do_incremental_sync)
    
    return {
        "success": True,
        "message": "增量同步任务已提交到后台执行",
        "status": "running",
        "use_progress_endpoint": "/api/sync/progress"
    }


@router.post("/clear-cache")
async def clear_sync_cache():
    """清除同步相关缓存"""
    from app.cache import cache_clear
    
    try:
        cache_clear("prescription:")
        cache_clear("herb:")
        cache_clear("sync:")
        
        return {
            "success": True,
            "message": "同步缓存已清除"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


class SetSyncTimeRequest(BaseModel):
    """设置同步时间请求"""
    sync_time: Optional[datetime] = None  # 不传则使用当前时间


@router.post("/set-sync-time")
async def set_last_sync_time(request: SetSyncTimeRequest = None):
    """
    手动设置上次同步时间（用于修复同步时间丢失的问题）
    
    如果不传 sync_time，则使用当前时间
    """
    try:
        from datetime import datetime as dt
        sync_time = request.sync_time if request and request.sync_time else dt.now()
        
        result = sync_service.force_set_last_sync_time(sync_time)
        
        return {
            "success": True,
            "message": f"已设置上次同步时间: {sync_time.isoformat()}",
            "data": {
                "last_sync_time": result.isoformat() if result else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置同步时间失败: {str(e)}")


@router.get("/statistics")
async def get_sync_statistics():
    """获取同步统计信息"""
    from app.db.session import get_db, get_neo4j_driver
    
    try:
        mysql_db = next(get_db())
        driver = get_neo4j_driver()

        # 正确的查询方式
        from app.models.models import Prescription, Herb, Efficacy, Medic
        mysql_stats = {
            'prescriptions': mysql_db.query(Prescription).count(),
            'herbs': mysql_db.query(Herb).count(),
            'efficacies': mysql_db.query(Efficacy).count(),
            'medics': mysql_db.query(Medic).count()
        }
        
        # Neo4j统计
        from app.core.config import settings
        with driver.session(database=settings.NEO4J_DATABASE) as neo4j_session:
            neo4j_stats = {}
            
            result = neo4j_session.run("MATCH (p:Prescription) RETURN count(p) as count")
            neo4j_stats['prescriptions'] = result.single()['count']
            
            result = neo4j_session.run("MATCH (h:Herb) RETURN count(h) as count")
            neo4j_stats['herbs'] = result.single()['count']
            
            result = neo4j_session.run("MATCH (e:Efficacy) RETURN count(e) as count")
            neo4j_stats['efficacies'] = result.single()['count']
            
            result = neo4j_session.run("MATCH (m:Medic) RETURN count(m) as count")
            neo4j_stats['medics'] = result.single()['count']
            
            result = neo4j_session.run("MATCH ()-[r]->() RETURN count(r) as count")
            neo4j_stats['relationships'] = result.single()['count']
        
        driver.close()
        
        return {
            "success": True,
            "data": {
                "mysql": mysql_stats,
                "neo4j": neo4j_stats,
                "sync_status": sync_service.get_sync_status()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
