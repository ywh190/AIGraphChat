"""
数据同步服务
实现MySQL和Neo4j之间的双向数据同步
支持批量同步、进度追踪、实时更新
"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import json
from sqlalchemy.orm import Session
from neo4j import Session as Neo4jSession
from sqlalchemy import text
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db.session import get_db, get_neo4j_driver
from app.models.models import (
    Prescription, Herb, Efficacy, Medic, PrescriptionRole,
    prescription_herb_association, medic_herb_association,
    Nature, Meridian
)
from app.cache import cache_clear
from app.core.config import settings


class SyncDirection(Enum):
    """同步方向"""
    MYSQL_TO_NEO4J = "mysql_to_neo4j"
    NEO4J_TO_MYSQL = "neo4j_to_mysql"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(Enum):
    """同步状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DataSyncService:
    """数据同步服务"""
    
    def __init__(self):
        self.sync_stats = {
            'total_synced': 0,
            'failed_count': 0,
            'status': SyncStatus.PENDING.value,
            'in_progress': False,
            'progress': 0,
            'current_step': '',
            'start_time': None,
            'end_time': None,
            'error_message': None
        }
        self.progress_callback = None
    
    def _get_last_sync_time(self) -> Optional[datetime]:
        """从Redis获取上次同步时间"""
        try:
            from app.cache import redis_client
            last_sync = redis_client.get('last_sync_time')
            if last_sync:
                # 处理不同类型的数据
                if isinstance(last_sync, bytes):
                    last_sync = last_sync.decode('utf-8')
                elif isinstance(last_sync, str):
                    pass  # 已经是字符串
                else:
                    # 尝试直接转换为字符串
                    last_sync = str(last_sync)

                # 尝试解析为datetime对象
                try:
                    return datetime.fromisoformat(last_sync)
                except ValueError as e:
                    print(f"[SYNC] 解析同步时间失败: {e}, 时间字符串: {last_sync}")
                    return None
        except Exception as e:
            print(f"[SYNC] 获取上次同步时间失败: {e}")
        return None
    
    def _get_neo4j_max_updated_time(self, neo4j_session) -> Optional[datetime]:
        """从Neo4j获取最大更新时间作为增量同步的参考点"""
        try:
            # 查询各类型节点的最大更新时间
            result = neo4j_session.run("""
                MATCH (n)
                WHERE n.updated_at IS NOT NULL
                RETURN max(n.updated_at) as max_time
            """)
            record = result.single()
            if record and record['max_time']:
                # Neo4j 返回的是字符串，需要解析
                max_time_str = record['max_time']
                if isinstance(max_time_str, str):
                    return datetime.fromisoformat(max_time_str.replace('Z', '+00:00'))
                return max_time_str
        except Exception as e:
            print(f"[SYNC] 获取Neo4j最大更新时间失败: {e}")
        return None
    
    def _set_last_sync_time(self, sync_time: datetime = None):
        """保存同步时间到Redis（永不过期）"""
        try:
            from app.cache import redis_client
            if sync_time is None:
                sync_time = datetime.now()

            # 确保sync_time是datetime对象
            if not isinstance(sync_time, datetime):
                print(f"[SYNC] 警告: sync_time不是datetime对象，类型为: {type(sync_time)}")
                sync_time = datetime.now()

            # 设置ttl=0表示永不过期
            sync_time_str = sync_time.isoformat()
            redis_client.set('last_sync_time', sync_time_str, ttl=0)
            print(f"[SYNC] 已保存同步时间到Redis: {sync_time_str}")

            # 验证保存是否成功
            saved_time = redis_client.get('last_sync_time')
            if saved_time:
                if isinstance(saved_time, bytes):
                    saved_time = saved_time.decode('utf-8')
                if saved_time == sync_time_str:
                    print(f"[SYNC] 验证同步时间保存成功")
                else:
                    print(f"[SYNC] 警告: 保存的同步时间与预期不符，预期: {sync_time_str}, 实际: {saved_time}")
            else:
                print(f"[SYNC] 警告: 无法验证同步时间是否保存成功")
        except Exception as e:
            print(f"[SYNC] 保存同步时间失败: {e}")
    
    def force_set_last_sync_time(self, sync_time: datetime = None):
        """强制设置上次同步时间（用于手动修复）"""
        self._set_last_sync_time(sync_time)
        return self._get_last_sync_time()
    
    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    def _update_progress(self, progress: float, step: str, message: str = None):
        """更新进度"""
        self.sync_stats['progress'] = progress
        self.sync_stats['current_step'] = step
        if message:
            self.sync_stats['message'] = message
        
        # 调用回调函数
        if self.progress_callback:
            self.progress_callback(self.sync_stats.copy())
    
    def sync_prescriptions_to_neo4j(
        self, 
        mysql_session: Session, 
        neo4j_session: Neo4jSession,
        since: datetime = None,
        limit: int = None
    ) -> Dict[str, Any]:
        """
        将MySQL中的方剂数据同步到Neo4j（批量处理，带进度更新）
        
        Args:
            mysql_session: MySQL数据库会话
            neo4j_session: Neo4j会话
            since: 只同步该时间之后更新的数据
            limit: 限制同步数量
            
        Returns:
            同步统计信息
        """
        stats = {
            'synced': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # 查询MySQL中的方剂数据
        query = mysql_session.query(Prescription)
        if since:
            query = query.filter(Prescription.updated_at >= since)
        
        # 获取总数
        total = query.count()
        if total == 0:
            print(f"[SYNC] 没有需要同步的方剂数据")
            return stats
        
        print(f"[SYNC] 找到 {total} 条需要同步的方剂数据")
        
        # 批量处理
        batch_size = 100
        offset = 0
        
        while offset < total:
            # 获取当前批次
            batch = query.offset(offset).limit(batch_size).all()
            if not batch:
                break
            
            # 批量同步
            for prescription in batch:
                try:
                    self._sync_single_prescription_to_neo4j(
                        mysql_session, neo4j_session, prescription
                    )
                    stats['synced'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['errors'].append({
                        'id': prescription.id,
                        'name': prescription.name,
                        'error': str(e)
                    })
            
            # 更新进度
            progress = min(100, (stats['synced'] / total) * 100)
            self._update_progress(
                progress, 
                "sync_prescriptions", 
                f"已同步 {stats['synced']}/{total} 条方剂"
            )
            
            offset += batch_size
        
        return stats
    
    def _sync_single_prescription_to_neo4j(
        self, 
        mysql_session: Session,
        neo4j_session: Neo4jSession, 
        prescription: Prescription
    ):
        """同步单个方剂到Neo4j（V2模型）"""
        # 创建或更新方剂节点
        cypher = """
        MERGE (p:Prescription {id: $id})
        SET p.name = $name,
            p.composition = $composition,
            p.function_indication = $function_indication,
            p.usage_dosage = $usage_dosage,
            p.source = $source,
            p.updated_at = $updated_at,
            p.source_db = 'mysql'
        """
        
        neo4j_session.run(cypher, {
            'id': prescription.id,
            'name': prescription.name,
            'composition': prescription.composition,
            'function_indication': prescription.function_indication,
            'usage_dosage': prescription.usage_dosage,
            'source': prescription.source,
            'updated_at': prescription.updated_at.isoformat() if prescription.updated_at else None
        })
        
        # 查询方剂-药材关联表（包含角色和用量）
        associations = mysql_session.query(prescription_herb_association).filter_by(
            prescription_id=prescription.id
        ).all()
        
        for assoc in associations:
            herb_id = assoc.herb_id
            role_id = assoc.role_id
            dosage = assoc.dosage
            
            # 获取药材信息
            herb = mysql_session.query(Herb).filter_by(id=herb_id).first()
            if not herb:
                continue
                
            # 创建药材节点（如果不存在）
            herb_cypher = """
            MERGE (h:Herb {id: $herb_id})
            SET h.name = $herb_name,
                h.pinyin = $pinyin,
                h.aliases = $aliases,
                h.source = $herb_source,
                h.source_text = $source_text,
                h.nature = $nature,
                h.function = $function,
                h.usage = $usage,
                h.link = $link,
                h.source_db = 'mysql'
            """
            neo4j_session.run(herb_cypher, {
                'herb_id': herb.id,
                'herb_name': herb.name,
                'pinyin': herb.pinyin,
                'aliases': herb.aliases,
                'herb_source': herb.source,
                'source_text': herb.source_text,
                'nature': herb.nature,
                'function': herb.function,
                'usage': herb.usage,
                'link': herb.link
            })
            
            # 创建方剂-药材关系，包含角色和用量属性
            rel_cypher = """
            MATCH (p:Prescription {id: $prescription_id})
            MATCH (h:Herb {id: $herb_id})
            MERGE (p)-[r:CONTAINS]->(h)
            SET r.dosage = $dosage,
                r.synced_at = $synced_at,
                r.source = 'mysql_sync'
            """
            params = {
                'prescription_id': prescription.id,
                'herb_id': herb_id,
                'dosage': dosage,
                'synced_at': datetime.now().isoformat()
            }
            
            # 如果有角色信息，添加角色属性
            if role_id:
                role = mysql_session.query(PrescriptionRole).filter_by(id=role_id).first()
                if role:
                    rel_cypher = """
                    MATCH (p:Prescription {id: $prescription_id})
                    MATCH (h:Herb {id: $herb_id})
                    MERGE (p)-[r:CONTAINS]->(h)
                    SET r.dosage = $dosage,
                        r.role = $role_name,
                        r.synced_at = $synced_at,
                        r.source = 'mysql_sync'
                    """
                    params['role_name'] = role.name
            
            neo4j_session.run(rel_cypher, params)
    
    def sync_herbs_to_neo4j(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        since: datetime = None,
        limit: int = None
    ) -> Dict[str, Any]:
        """将MySQL中的药材数据同步到Neo4j（批量处理，带进度更新）"""
        stats = {'synced': 0, 'failed': 0, 'errors': []}
        
        query = mysql_session.query(Herb)
        if since:
            query = query.filter(Herb.updated_at >= since)
        
        # 获取总数
        total = query.count()
        if total == 0:
            print(f"[SYNC] 没有需要同步的药材数据")
            return stats
        
        print(f"[SYNC] 找到 {total} 条需要同步的药材数据")
        
        # 批量处理
        batch_size = 100
        offset = 0
        
        while offset < total:
            batch = query.offset(offset).limit(batch_size).all()
            if not batch:
                break
            
            for herb in batch:
                try:
                    cypher = """
                    MERGE (h:Herb {id: $id})
                    SET h.name = $name,
                        h.pinyin = $pinyin,
                        h.aliases = $aliases,
                        h.source = $source,
                        h.source_text = $source_text,
                        h.nature = $nature,
                        h.function = $function,
                        h.usage = $usage,
                        h.link = $link,
                        h.updated_at = $updated_at,
                        h.source_db = 'mysql'
                    """
                    
                    neo4j_session.run(cypher, {
                        'id': herb.id,
                        'name': herb.name,
                        'pinyin': herb.pinyin,
                        'aliases': herb.aliases,
                        'source': herb.source,
                        'source_text': herb.source_text,
                        'nature': herb.nature,
                        'function': herb.function,
                        'usage': herb.usage,
                        'link': herb.link,
                        'updated_at': herb.updated_at.isoformat() if herb.updated_at else None
                    })
                    
                    stats['synced'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['errors'].append({'id': herb.id, 'name': herb.name, 'error': str(e)})
            
            # 更新进度
            progress = min(100, (stats['synced'] / total) * 100)
            self._update_progress(
                progress, 
                "sync_herbs", 
                f"已同步 {stats['synced']}/{total} 条药材"
            )
            
            offset += batch_size
        
        return stats
    
    def sync_medics_to_neo4j(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        since: datetime = None,
        limit: int = None
    ) -> Dict[str, Any]:
        """将MySQL中的中成药数据同步到Neo4j（批量处理，带进度更新）"""
        stats = {'synced': 0, 'failed': 0, 'errors': []}
        
        query = mysql_session.query(Medic).filter(Medic.is_deleted == 0)
        if since:
            query = query.filter(Medic.updated_at >= since)
        
        # 获取总数
        total = query.count()
        if total == 0:
            print(f"[SYNC] 没有需要同步的中成药数据")
            return stats
        
        print(f"[SYNC] 找到 {total} 条需要同步的中成药数据")
        
        # 批量处理
        batch_size = 50  # 中成药处理较慢，批次小一些
        offset = 0
        
        while offset < total:
            batch = query.offset(offset).limit(batch_size).all()
            if not batch:
                break
            
            for medic in batch:
                try:
                    # 创建中成药节点
                    cypher = """
                    MERGE (m:Medic {id: $id})
                    SET m.name = $name,
                        m.english_name = $english_name,
                        m.category = $category,
                        m.main_category = $main_category,
                        m.sub_category = $sub_category,
                        m.composition = $composition,
                        m.function_indication = $function_indication,
                        m.analysis = $analysis,
                        m.clinical_application = $clinical_application,
                        m.side_effects = $side_effects,
                        m.contraindications = $contraindications,
                        m.precautions = $precautions,
                        m.usage_dosage = $usage_dosage,
                        m.specification = $specification,
                        m.pharmacology = $pharmacology,
                        m.references = $references,
                        m.monarch_ministers_assistants_couriers = $monarch_ministers,
                        m.source = $source,
                        m.updated_at = $updated_at,
                        m.source_db = 'mysql'
                    """
                    
                    neo4j_session.run(cypher, {
                        'id': medic.id,
                        'name': medic.name,
                        'english_name': medic.english_name,
                        'category': medic.category,
                        'main_category': medic.main_category,
                        'sub_category': medic.sub_category,
                        'composition': medic.composition,
                        'function_indication': medic.function_indication,
                        'analysis': medic.analysis,
                        'clinical_application': medic.clinical_application,
                        'side_effects': medic.side_effects,
                        'contraindications': medic.contraindications,
                        'precautions': medic.precautions,
                        'usage_dosage': medic.usage_dosage,
                        'specification': medic.specification,
                        'pharmacology': medic.pharmacology,
                        'references': medic.references,
                        'monarch_ministers': medic.monarch_ministers_assistants_couriers,
                        'source': medic.source,
                        'updated_at': medic.updated_at.isoformat() if medic.updated_at else None
                    })
                    
                    stats['synced'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['errors'].append({'id': medic.id, 'name': medic.name, 'error': str(e)})
            
            # 更新进度
            progress = min(100, (stats['synced'] / total) * 100)
            self._update_progress(
                progress, 
                "sync_medics", 
                f"已同步 {stats['synced']}/{total} 条中成药"
            )
            
            offset += batch_size
        
        return stats
    
    def batch_sync_prescriptions(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int = 1000,
        max_workers: int = 10
    ) -> Dict[str, Any]:
        """
        批量同步方剂节点(优化版)
        支持并发处理多个批次
        """
        self._update_progress(0, "sync_prescriptions", "开始同步方剂节点...")
        
        total = mysql_session.query(Prescription).count()
        
        # 如果总数为0或max_workers<=1，使用顺序处理
        if total == 0 or max_workers <= 1:
            return self._sequential_sync_prescriptions(mysql_session, neo4j_session, batch_size, total)
        
        # 计算批次
        offsets = list(range(0, total, batch_size))
        total_batches = len(offsets)
        
        # 限制最大工作线程数
        workers = min(max_workers, total_batches)
        
        print(f"[SYNC] 方剂同步: 总数={total}, 批次={total_batches}, 并发数={workers}")
        
        # 准备线程安全计数器
        from threading import Lock
        synced_counter = 0
        failed_counter = 0
        errors = []
        lock = Lock()
        
        # 定义批次处理函数
        def process_batch(batch_offset: int):
            nonlocal synced_counter, failed_counter, errors
            
            batch_synced = 0
            batch_failed = 0
            batch_errors = []
            
            # 重试机制
            max_retries = 3
            retry_delay = 1  # 秒
            
            for retry in range(max_retries):
                try:
                    # 每个线程使用独立的数据库连接
                    mysql_db = next(get_db())
                    # 为每个线程创建独立的Neo4j驱动程序，避免线程间冲突
                    from neo4j import GraphDatabase
                    driver = GraphDatabase.driver(
                        settings.NEO4J_URI,
                        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                    )
                    
                    with driver.session(database=settings.NEO4J_DATABASE) as neo4j_sess:
                        # 查询当前批次数据
                        batch = mysql_db.query(Prescription).offset(batch_offset).limit(batch_size).all()
                        
                        # 准备批量数据
                        prescription_data = []
                        for p in batch:
                            prescription_data.append({
                                'id': p.id,
                                'name': p.name,
                                'composition': p.composition,
                                'function_indication': p.function_indication,
                                'usage_dosage': p.usage_dosage,
                                'source': p.source,
                                'updated_at': p.updated_at.isoformat() if p.updated_at else None
                            })
                        
                        # 批量创建节点
                        cypher = """
                        UNWIND $data as row
                        MERGE (p:Prescription {id: row.id})
                        SET p.name = row.name,
                            p.chinese_name = row.name,
                            p.composition = row.composition,
                            p.function_indication = row.function_indication,
                            p.usage_dosage = row.usage_dosage,
                            p.source = row.source,
                            p.updated_at = row.updated_at,
                            p.source_db = 'mysql'
                        """
                        neo4j_sess.run(cypher, {'data': prescription_data})
                        
                        # 检查是否存在同名的中成药，如果存在则添加Medic标签
                        for p in batch:
                            medic_exists = mysql_db.query(Medic).filter(
                                Medic.name == p.name
                            ).first()
                            if medic_exists:
                                # 添加Medic标签
                                add_label_cypher = """
                                MATCH (n:Prescription {id: $id})
                                SET n:Medic
                                """
                                neo4j_sess.run(add_label_cypher, {'id': p.id})
                        
                        batch_synced = len(batch)
                        
                        # 关闭连接
                        mysql_db.close()
                        driver.close()
                        
                    # 如果成功，跳出重试循环
                    break
                    
                except Exception as e:
                    # 如果是最后一次重试，记录错误
                    if retry == max_retries - 1:
                        batch_failed = 1
                        batch_errors.append({'offset': batch_offset, 'error': str(e), 'retries': retry + 1})
                        print(f"[SYNC ERROR] 方剂批次 {batch_offset} 同步失败 (重试{retry + 1}/{max_retries}): {e}")
                    else:
                        print(f"[SYNC WARNING] 方剂批次 {batch_offset} 同步失败，正在重试 ({retry + 1}/{max_retries}): {e}")
                        import time
                        time.sleep(retry_delay)
                        # 继续下一次重试
                        continue
            
            # 更新全局计数器
            with lock:
                synced_counter += batch_synced
                failed_counter += batch_failed
                errors.extend(batch_errors)
                
                # 更新进度
                progress = (synced_counter / total) * 100
                self._update_progress(
                    progress, 
                    "sync_prescriptions", 
                    f"已同步 {synced_counter}/{total} 条方剂"
                )
            
            return batch_synced, batch_failed, batch_errors
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有批次任务
            future_to_offset = {
                executor.submit(process_batch, offset): offset 
                for offset in offsets
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_offset):
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        failed_counter += 1
                        errors.append({'error': str(e)})
        
        print(f"[SYNC] 方剂同步完成: 成功={synced_counter}, 失败={failed_counter}")
        return {'synced': synced_counter, 'failed': failed_counter, 'errors': errors}
    
    def _sequential_sync_prescriptions(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int,
        total: int
    ) -> Dict[str, Any]:
        """顺序同步方剂节点 (兼容原有逻辑)"""
        offset = 0
        synced = 0
        
        while offset < total:
            batch = mysql_session.query(Prescription).offset(offset).limit(batch_size).all()
            
            # 准备批量数据
            prescription_data = []
            for p in batch:
                prescription_data.append({
                    'id': p.id,
                    'name': p.name,
                    'composition': p.composition,
                    'function_indication': p.function_indication,
                    'usage_dosage': p.usage_dosage,
                    'source': p.source,
                    'updated_at': p.updated_at.isoformat() if p.updated_at else None
                })
            
            # 批量创建节点
            cypher = """
            UNWIND $data as row
            MERGE (p:Prescription {id: row.id})
            SET p.name = row.name,
                p.chinese_name = row.name,
                p.composition = row.composition,
                p.function_indication = row.function_indication,
                p.usage_dosage = row.usage_dosage,
                p.source = row.source,
                p.updated_at = row.updated_at,
                p.source_db = 'mysql'
            """
            neo4j_session.run(cypher, {'data': prescription_data})
            
            # 检查是否存在同名的中成药，如果存在则添加Medic标签
            for p in batch:
                medic_exists = mysql_session.query(Medic).filter(
                    Medic.name == p.name
                ).first()
                if medic_exists:
                    # 添加Medic标签
                    add_label_cypher = """
                    MATCH (n:Prescription {id: $id})
                    SET n:Medic
                    """
                    neo4j_session.run(add_label_cypher, {'id': p.id})
            
            synced += len(batch)
            offset += batch_size
            
            # 更新进度
            progress = (synced / total) * 100
            self._update_progress(progress, "sync_prescriptions", f"已同步 {synced}/{total} 条方剂")
        
        return {'synced': synced, 'failed': 0, 'errors': []}
    
    def batch_sync_herbs(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int = 1000,
        max_workers: int = 10
    ) -> Dict[str, Any]:
        """
        批量同步药材节点(优化版)
        支持并发处理多个批次
        """
        self._update_progress(0, "sync_herbs", "开始同步药材节点...")
        
        total = mysql_session.query(Herb).count()
        
        # 如果总数为0或max_workers<=1，使用顺序处理
        if total == 0 or max_workers <= 1:
            return self._sequential_sync_herbs(mysql_session, neo4j_session, batch_size, total)
        
        # 计算批次
        offsets = list(range(0, total, batch_size))
        total_batches = len(offsets)
        
        # 限制最大工作线程数
        workers = min(max_workers, total_batches)
        
        print(f"[SYNC] 药材同步: 总数={total}, 批次={total_batches}, 并发数={workers}")
        
        # 准备线程安全计数器
        from threading import Lock
        synced_counter = 0
        failed_counter = 0
        errors = []
        lock = Lock()
        
        # 定义批次处理函数
        def process_batch(batch_offset: int):
            nonlocal synced_counter, failed_counter, errors
            
            batch_synced = 0
            batch_failed = 0
            batch_errors = []
            
            try:
                # 每个线程使用独立的数据库连接
                mysql_db = next(get_db())
                # 为每个线程创建独立的Neo4j驱动程序，避免线程间冲突
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
                
                with driver.session(database=settings.NEO4J_DATABASE) as neo4j_sess:
                    # 查询当前批次数据
                    batch = mysql_db.query(Herb).offset(batch_offset).limit(batch_size).all()
                    
                    # 准备批量数据
                    herb_data = []
                    for h in batch:
                        herb_data.append({
                            'id': h.id,
                            'name': h.name,
                            'pinyin': h.pinyin,
                            'aliases': h.aliases,
                            'source': h.source,
                            'source_text': h.source_text,
                            'nature': h.nature,
                            'function': h.function,
                            'usage': h.usage,
                            'link': h.link,
                            'updated_at': h.updated_at.isoformat() if h.updated_at else None
                        })
                    
                    # 批量创建节点
                    cypher = """
                    UNWIND $data as row
                    MERGE (h:Herb {id: row.id})
                    SET h.name = row.name,
                        h.chinese_name = row.name,
                        h.pinyin = row.pinyin,
                        h.aliases = row.aliases,
                        h.source = row.source,
                        h.source_text = row.source_text,
                        h.nature = row.nature,
                        h.function = row.function,
                        h.usage = row.usage,
                        h.link = row.link,
                        h.updated_at = row.updated_at,
                        h.source_db = 'mysql'
                    """
                    neo4j_sess.run(cypher, {'data': herb_data})
                    
                    batch_synced = len(batch)
                    
                    # 关闭连接
                    mysql_db.close()
                    driver.close()
                    
            except Exception as e:
                batch_failed = 1
                batch_errors.append({'offset': batch_offset, 'error': str(e)})
                print(f"[SYNC ERROR] 药材批次 {batch_offset} 同步失败: {e}")
            
            # 更新全局计数器
            with lock:
                synced_counter += batch_synced
                failed_counter += batch_failed
                errors.extend(batch_errors)
                
                # 更新进度
                progress = (synced_counter / total) * 100
                self._update_progress(
                    progress, 
                    "sync_herbs", 
                    f"已同步 {synced_counter}/{total} 条药材"
                )
            
            return batch_synced, batch_failed, batch_errors
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有批次任务
            future_to_offset = {
                executor.submit(process_batch, offset): offset 
                for offset in offsets
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_offset):
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        failed_counter += 1
                        errors.append({'error': str(e)})
        
        print(f"[SYNC] 药材同步完成: 成功={synced_counter}, 失败={failed_counter}")
        return {'synced': synced_counter, 'failed': failed_counter, 'errors': errors}
    
    def _sequential_sync_herbs(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int,
        total: int
    ) -> Dict[str, Any]:
        """顺序同步药材节点 (兼容原有逻辑)"""
        offset = 0
        synced = 0
        
        while offset < total:
            batch = mysql_session.query(Herb).offset(offset).limit(batch_size).all()
            
            # 准备批量数据
            herb_data = []
            for h in batch:
                herb_data.append({
                    'id': h.id,
                    'name': h.name,
                    'pinyin': h.pinyin,
                    'aliases': h.aliases,
                    'source': h.source,
                    'source_text': h.source_text,
                    'nature': h.nature,
                    'function': h.function,
                    'usage': h.usage,
                    'link': h.link,
                    'updated_at': h.updated_at.isoformat() if h.updated_at else None
                })
            
            # 批量创建节点
            cypher = """
            UNWIND $data as row
            MERGE (h:Herb {id: row.id})
            SET h.name = row.name,
                h.chinese_name = row.name,
                h.pinyin = row.pinyin,
                h.aliases = row.aliases,
                h.source = row.source,
                h.source_text = row.source_text,
                h.nature = row.nature,
                h.function = row.function,
                h.usage = row.usage,
                h.link = row.link,
                h.updated_at = row.updated_at,
                h.source_db = 'mysql'
            """
            neo4j_session.run(cypher, {'data': herb_data})
            
            synced += len(batch)
            offset += batch_size
            
            # 更新进度
            progress = (synced / total) * 100
            self._update_progress(progress, "sync_herbs", f"已同步 {synced}/{total} 条药材")
        
        return {'synced': synced, 'failed': 0, 'errors': []}
    
    def batch_sync_medics(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int = 1000,
        max_workers: int = 10
    ) -> Dict[str, Any]:
        """
        批量同步中成药节点(优化版)
        支持并发处理多个批次
        """
        self._update_progress(0, "sync_medics", "开始同步中成药节点...")
        
        # 只统计未删除的数据
        total = mysql_session.query(Medic).filter(Medic.is_deleted == 0).count()
        if total == 0:
            return {'synced': 0, 'failed': 0, 'errors': []}
        
        # 如果max_workers<=1，使用顺序处理
        if max_workers <= 1:
            return self._sequential_sync_medics(mysql_session, neo4j_session, batch_size, total)
        
        # 计算批次
        offsets = list(range(0, total, batch_size))
        total_batches = len(offsets)
        
        # 限制最大工作线程数
        workers = min(max_workers, total_batches)
        
        print(f"[SYNC] 中成药同步: 总数={total}, 批次={total_batches}, 并发数={workers}")
        
        # 准备线程安全计数器
        from threading import Lock
        synced_counter = 0
        failed_counter = 0
        errors = []
        lock = Lock()
        
        # 定义批次处理函数
        def process_batch(batch_offset: int):
            nonlocal synced_counter, failed_counter, errors
            
            batch_synced = 0
            batch_failed = 0
            batch_errors = []
            
            try:
                # 每个线程使用独立的数据库连接
                mysql_db = next(get_db())
                # 为每个线程创建独立的Neo4j驱动程序，避免线程间冲突
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
                
                with driver.session(database=settings.NEO4J_DATABASE) as neo4j_sess:
                    # 查询当前批次数据（只查询未删除的）
                    batch = mysql_db.query(Medic).filter(Medic.is_deleted == 0).offset(batch_offset).limit(batch_size).all()
                    
                    # 准备批量数据
                    medic_data = []
                    for m in batch:
                        medic_data.append({
                            'id': m.id,
                            'chinese_name': m.name,
                            'english_name': m.english_name,
                            'category': m.category,
                            'main_category': m.main_category,
                            'sub_category': m.sub_category,
                            'composition': m.composition,
                            'function_indication': m.function_indication,
                            'analysis': m.analysis,
                            'clinical_application': m.clinical_application,
                            'side_effects': m.side_effects,
                            'contraindications': m.contraindications,
                            'precautions': m.precautions,
                            'usage_dosage': m.usage_dosage,
                            'specification': m.specification,
                            'pharmacology': m.pharmacology,
                            'references': m.references,
                            'monarch_ministers': m.monarch_ministers_assistants_couriers,
                            'source': m.source,
                            'updated_at': m.updated_at.isoformat() if m.updated_at else None
                        })
                    
                    # 批量创建节点
                    cypher = """
                    UNWIND $data as row
                    MERGE (m:Medic {id: row.id})
                    SET m.name = row.chinese_name,
                        m.chinese_name = row.chinese_name,
                        m.english_name = row.english_name,
                        m.category = row.category,
                        m.main_category = row.main_category,
                        m.sub_category = row.sub_category,
                        m.composition = row.composition,
                        m.function_indication = row.function_indication,
                        m.analysis = row.analysis,
                        m.clinical_application = row.clinical_application,
                        m.side_effects = row.side_effects,
                        m.contraindications = row.contraindications,
                        m.precautions = row.precautions,
                        m.usage_dosage = row.usage_dosage,
                        m.specification = row.specification,
                        m.pharmacology = row.pharmacology,
                        m.references = row.references,
                        m.monarch_ministers_assistants_couriers = row.monarch_ministers,
                        m.source = row.source,
                        m.updated_at = row.updated_at,
                        m.source_db = 'mysql'
                    """
                    neo4j_sess.run(cypher, {'data': medic_data})
                    
                    batch_synced = len(batch)
                    
                    # 关闭连接
                    mysql_db.close()
                    driver.close()
                    
            except Exception as e:
                batch_failed = 1
                batch_errors.append({'offset': batch_offset, 'error': str(e)})
                print(f"[SYNC ERROR] 中成药批次 {batch_offset} 同步失败: {e}")
            
            # 更新全局计数器
            with lock:
                synced_counter += batch_synced
                failed_counter += batch_failed
                errors.extend(batch_errors)
                
                # 更新进度
                progress = (synced_counter / total) * 100
                self._update_progress(
                    progress, 
                    "sync_medics", 
                    f"已同步 {synced_counter}/{total} 条中成药"
                )
            
            return batch_synced, batch_failed, batch_errors
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有批次任务
            future_to_offset = {
                executor.submit(process_batch, offset): offset 
                for offset in offsets
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_offset):
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        failed_counter += 1
                        errors.append({'error': str(e)})
        
        print(f"[SYNC] 中成药同步完成: 成功={synced_counter}, 失败={failed_counter}")
        return {'synced': synced_counter, 'failed': failed_counter, 'errors': errors}
    
    def _sequential_sync_medics(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int,
        total: int
    ) -> Dict[str, Any]:
        """顺序同步中成药节点 (兼容原有逻辑)"""
        offset = 0
        synced = 0
        
        while offset < total:
            batch = mysql_session.query(Medic).filter(Medic.is_deleted == 0).offset(offset).limit(batch_size).all()
            
            # 准备批量数据
            medic_data = []
            for m in batch:
                medic_data.append({
                    'id': m.id,
                    'chinese_name': m.name,
                    'english_name': m.english_name,
                    'category': m.category,
                    'main_category': m.main_category,
                    'sub_category': m.sub_category,
                    'composition': m.composition,
                    'function_indication': m.function_indication,
                    'analysis': m.analysis,
                    'clinical_application': m.clinical_application,
                    'side_effects': m.side_effects,
                    'contraindications': m.contraindications,
                    'precautions': m.precautions,
                    'usage_dosage': m.usage_dosage,
                    'specification': m.specification,
                    'pharmacology': m.pharmacology,
                    'references': m.references,
                    'monarch_ministers': m.monarch_ministers_assistants_couriers,
                    'source': m.source,
                    'updated_at': m.updated_at.isoformat() if m.updated_at else None
                })
            
            # 批量创建节点
            cypher = """
            UNWIND $data as row
            MERGE (m:Medic {id: row.id})
            SET m.name = row.chinese_name,
                m.chinese_name = row.chinese_name,
                m.english_name = row.english_name,
                m.category = row.category,
                m.main_category = row.main_category,
                m.sub_category = row.sub_category,
                m.composition = row.composition,
                m.function_indication = row.function_indication,
                m.analysis = row.analysis,
                m.clinical_application = row.clinical_application,
                m.side_effects = row.side_effects,
                m.contraindications = row.contraindications,
                m.precautions = row.precautions,
                m.usage_dosage = row.usage_dosage,
                m.specification = row.specification,
                m.pharmacology = row.pharmacology,
                m.references = row.references,
                m.monarch_ministers_assistants_couriers = row.monarch_ministers,
                m.source = row.source,
                m.updated_at = row.updated_at,
                m.source_db = 'mysql'
            """
            neo4j_session.run(cypher, {'data': medic_data})
            
            synced += len(batch)
            offset += batch_size
            
            # 更新进度
            progress = (synced / total) * 100
            self._update_progress(progress, "sync_medics", f"已同步 {synced}/{total} 条中成药")
        
        return {'synced': synced, 'failed': 0, 'errors': []}
    
    def batch_sync_prescription_relationships(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int = 5000,
        max_workers: int = 10
    ) -> Dict[str, Any]:
        """
        批量同步方剂-药材关系
        支持并发处理多个批次
        """
        self._update_progress(0, "sync_prescription_relationships", "开始同步方剂-药材关系...")
        
        total = mysql_session.query(prescription_herb_association).count()
        
        # 如果总数为0或max_workers<=1，使用顺序处理
        if total == 0 or max_workers <= 1:
            return self._sequential_sync_prescription_relationships(mysql_session, neo4j_session, batch_size, total)
        
        # 先获取所有角色信息到缓存（主线程加载，传递给工作线程）
        roles = {}
        for role in mysql_session.query(PrescriptionRole).all():
            roles[role.id] = role.name
        
        # 计算批次
        offsets = list(range(0, total, batch_size))
        total_batches = len(offsets)
        
        # 限制最大工作线程数
        workers = min(max_workers, total_batches)
        
        print(f"[SYNC] 方剂-药材关系同步: 总数={total}, 批次={total_batches}, 并发数={workers}")
        
        # 准备线程安全计数器
        from threading import Lock
        synced_counter = 0
        failed_counter = 0
        errors = []
        lock = Lock()
        
        # 定义批次处理函数
        def process_batch(batch_offset: int):
            nonlocal synced_counter, failed_counter, errors
            
            batch_synced = 0
            batch_failed = 0
            batch_errors = []
            
            # 重试机制 - 处理Neo4j死锁
            max_retries = 5
            retry_delay = 2  # 秒
            
            for retry in range(max_retries):
                try:
                    # 每个线程使用独立的数据库连接
                    mysql_db = next(get_db())
                    # 为每个线程创建独立的Neo4j驱动程序，避免线程间冲突
                    from neo4j import GraphDatabase
                    driver = GraphDatabase.driver(
                        settings.NEO4J_URI,
                        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                    )
                    
                    with driver.session(database=settings.NEO4J_DATABASE) as neo4j_sess:
                        # 查询当前批次数据
                        batch = mysql_db.query(prescription_herb_association).offset(batch_offset).limit(batch_size).all()
                        
                        # 准备批量数据
                        relation_data = []
                        for assoc in batch:
                            relation_data.append({
                                'prescription_id': assoc.prescription_id,
                                'herb_id': assoc.herb_id,
                                'dosage': assoc.dosage,
                                'role': roles.get(assoc.role_id, ''),
                                'synced_at': datetime.now().isoformat()
                            })
                        
                        # 批量创建关系 - 添加RETRY逻辑避免死锁
                        cypher = """
                        UNWIND $data as row
                        MATCH (p:Prescription {id: row.prescription_id})
                        MATCH (h:Herb {id: row.herb_id})
                        MERGE (p)-[r:CONTAINS]->(h)
                        SET r.dosage = row.dosage,
                            r.role = row.role,
                            r.synced_at = row.synced_at,
                            r.source = 'mysql_sync'
                        """
                        neo4j_sess.run(cypher, {'data': relation_data})
                        
                        batch_synced = len(batch)
                        
                        # 关闭连接
                        mysql_db.close()
                        driver.close()
                        
                    # 如果成功，跳出重试循环
                    break
                    
                except Exception as e:
                    error_str = str(e)
                    # 检查是否是死锁错误
                    is_deadlock = 'DeadlockDetected' in error_str or 'ForsetiClient' in error_str
                    
                    if is_deadlock and retry < max_retries - 1:
                        # 死锁错误，进行指数退避重试
                        wait_time = retry_delay * (2 ** retry)  # 指数退避: 2, 4, 8, 16, 32秒
                        print(f"[SYNC WARNING] 方剂-药材关系批次 {batch_offset} 检测到死锁，等待 {wait_time}s 后重试 ({retry + 1}/{max_retries})")
                        import time
                        time.sleep(wait_time)
                        continue
                    elif retry == max_retries - 1:
                        # 最后一次重试失败
                        batch_failed = 1
                        batch_errors.append({'offset': batch_offset, 'error': error_str, 'retries': retry + 1})
                        print(f"[SYNC ERROR] 方剂-药材关系批次 {batch_offset} 同步失败 (重试{retry + 1}/{max_retries}): {e}")
                    else:
                        # 其他错误，直接失败
                        batch_failed = 1
                        batch_errors.append({'offset': batch_offset, 'error': error_str})
                        print(f"[SYNC ERROR] 方剂-药材关系批次 {batch_offset} 同步失败: {e}")
                        break
            
            # 更新全局计数器
            with lock:
                synced_counter += batch_synced
                failed_counter += batch_failed
                errors.extend(batch_errors)
                
                # 更新进度
                progress = (synced_counter / total) * 100
                self._update_progress(
                    progress, 
                    "sync_prescription_relationships", 
                    f"已同步 {synced_counter}/{total} 个方剂-药材关系"
                )
            
            return batch_synced, batch_failed, batch_errors
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有批次任务
            future_to_offset = {
                executor.submit(process_batch, offset): offset 
                for offset in offsets
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_offset):
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        failed_counter += 1
                        errors.append({'error': str(e)})
        
        print(f"[SYNC] 方剂-药材关系同步完成: 成功={synced_counter}, 失败={failed_counter}")
        return {'synced': synced_counter, 'failed': failed_counter, 'errors': errors}
    
    def _sequential_sync_prescription_relationships(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int,
        total: int
    ) -> Dict[str, Any]:
        """顺序同步方剂-药材关系 (兼容原有逻辑)"""
        offset = 0
        synced = 0
        
        # 先获取所有角色信息到缓存
        roles = {}
        for role in mysql_session.query(PrescriptionRole).all():
            roles[role.id] = role.name
        
        while offset < total:
            batch = mysql_session.query(prescription_herb_association).offset(offset).limit(batch_size).all()
            
            # 准备批量数据
            relation_data = []
            for assoc in batch:
                relation_data.append({
                    'prescription_id': assoc.prescription_id,
                    'herb_id': assoc.herb_id,
                    'dosage': assoc.dosage,
                    'role': roles.get(assoc.role_id, ''),
                    'synced_at': datetime.now().isoformat()
                })
            
            # 批量创建关系
            cypher = """
            UNWIND $data as row
            MATCH (p:Prescription {id: row.prescription_id})
            MATCH (h:Herb {id: row.herb_id})
            MERGE (p)-[r:CONTAINS]->(h)
            SET r.dosage = row.dosage,
                r.role = row.role,
                r.synced_at = row.synced_at,
                r.source = 'mysql_sync'
            """
            neo4j_session.run(cypher, {'data': relation_data})
            
            synced += len(batch)
            offset += batch_size
            
            # 更新进度
            progress = (synced / total) * 100
            self._update_progress(progress, "sync_prescription_relationships", f"已同步 {synced}/{total} 个方剂-药材关系")
        
        return {'synced': synced, 'failed': 0, 'errors': []}
    
    def batch_sync_medic_relationships(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int = 5000,
        max_workers: int = 10
    ) -> Dict[str, Any]:
        """
        批量同步中成药-药材关系
        支持并发处理多个批次
        """
        self._update_progress(0, "sync_medic_relationships", "开始同步中成药-药材关系...")
        
        total = mysql_session.query(medic_herb_association).count()
        if total == 0:
            return {'synced': 0, 'failed': 0, 'errors': []}
        
        # 强制使用顺序处理以避免Neo4j死锁问题
        max_workers = 1
        
        return self._sequential_sync_medic_relationships(mysql_session, neo4j_session, batch_size, total)
        
        # 先获取所有角色信息到缓存（主线程加载，传递给工作线程）
        roles = {}
        for role in mysql_session.query(PrescriptionRole).all():
            roles[role.id] = role.name
        
        # 计算批次
        offsets = list(range(0, total, batch_size))
        total_batches = len(offsets)
        
        # 限制最大工作线程数
        workers = min(max_workers, total_batches)
        
        # 准备线程安全计数器
        from threading import Lock
        synced_counter = 0
        failed_counter = 0
        errors = []
        lock = Lock()
        
        # 定义批次处理函数
        def process_batch(batch_offset: int):
            nonlocal synced_counter, failed_counter, errors
            
            batch_synced = 0
            batch_failed = 0
            batch_errors = []
            
            # 重试机制 - 处理Neo4j死锁
            max_retries = 5
            retry_delay = 2  # 秒
            
            for retry in range(max_retries):
                try:
                    # 每个线程使用独立的数据库连接
                    mysql_db = next(get_db())
                    # 为每个线程创建独立的Neo4j驱动程序，避免线程间冲突
                    from neo4j import GraphDatabase
                    driver = GraphDatabase.driver(
                        settings.NEO4J_URI,
                        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                    )
                    
                    with driver.session(database=settings.NEO4J_DATABASE) as neo4j_sess:
                        # 查询当前批次数据
                        batch = mysql_db.query(medic_herb_association).offset(batch_offset).limit(batch_size).all()
                        
                        # 准备批量数据
                        relation_data = []
                        for assoc in batch:
                            relation_data.append({
                                'medic_id': assoc.medic_id,
                                'herb_id': assoc.herb_id,
                                'dosage': assoc.dosage,
                                'role': roles.get(assoc.role_id, ''),
                                'synced_at': datetime.now().isoformat()
                            })
                        
                        # 批量创建关系
                        cypher = """
                        UNWIND $data as row
                        MATCH (m:Medic {id: row.medic_id})
                        MATCH (h:Herb {id: row.herb_id})
                        MERGE (m)-[r:CONTAINS]->(h)
                        SET r.dosage = row.dosage,
                            r.role = row.role,
                            r.synced_at = row.synced_at,
                            r.source = 'mysql_sync'
                        """
                        neo4j_sess.run(cypher, {'data': relation_data})
                        
                        batch_synced = len(batch)
                        
                        # 关闭连接
                        mysql_db.close()
                        driver.close()
                        
                    # 如果成功，跳出重试循环
                    break
                    
                except Exception as e:
                    error_str = str(e)
                    # 检查是否是死锁错误
                    is_deadlock = 'DeadlockDetected' in error_str or 'ForsetiClient' in error_str
                    
                    if is_deadlock and retry < max_retries - 1:
                        # 死锁错误，进行指数退避重试
                        wait_time = retry_delay * (2 ** retry)  # 指数退避: 2, 4, 8, 16, 32秒
                        print(f"[SYNC WARNING] 中成药-药材关系批次 {batch_offset} 检测到死锁，等待 {wait_time}s 后重试 ({retry + 1}/{max_retries})")
                        import time
                        time.sleep(wait_time)
                        continue
                    elif retry == max_retries - 1:
                        # 最后一次重试失败
                        batch_failed = 1
                        batch_errors.append({'offset': batch_offset, 'error': error_str, 'retries': retry + 1})
                        print(f"[SYNC ERROR] 中成药-药材关系批次 {batch_offset} 同步失败 (重试{retry + 1}/{max_retries}): {e}")
                    else:
                        # 其他错误，直接失败
                        batch_failed = 1
                        batch_errors.append({'offset': batch_offset, 'error': error_str})
                        print(f"[SYNC ERROR] 中成药-药材关系批次 {batch_offset} 同步失败: {e}")
                        break
            
            # 更新全局计数器
            with lock:
                synced_counter += batch_synced
                failed_counter += batch_failed
                errors.extend(batch_errors)
                
                # 更新进度
                progress = (synced_counter / total) * 100
                self._update_progress(
                    progress, 
                    "sync_medic_relationships", 
                    f"已同步 {synced_counter}/{total} 个中成药-药材关系"
                )
            
            return batch_synced, batch_failed, batch_errors
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有批次任务
            future_to_offset = {
                executor.submit(process_batch, offset): offset 
                for offset in offsets
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_offset):
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        failed_counter += 1
                        errors.append({'error': str(e)})
        
        print(f"[SYNC] 中成药-药材关系同步完成: 成功={synced_counter}, 失败={failed_counter}")
        return {'synced': synced_counter, 'failed': failed_counter, 'errors': errors}
    
    def _sequential_sync_medic_relationships(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        batch_size: int,
        total: int
    ) -> Dict[str, Any]:
        """顺序同步中成药-药材关系 (兼容原有逻辑)"""
        offset = 0
        synced = 0
        
        # 先获取所有角色信息到缓存
        roles = {}
        for role in mysql_session.query(PrescriptionRole).all():
            roles[role.id] = role.name
        
        while offset < total:
            batch = mysql_session.query(medic_herb_association).offset(offset).limit(batch_size).all()
            
            # 准备批量数据
            relation_data = []
            for assoc in batch:
                relation_data.append({
                    'medic_id': assoc.medic_id,
                    'herb_id': assoc.herb_id,
                    'dosage': assoc.dosage,
                    'role': roles.get(assoc.role_id, ''),
                    'synced_at': datetime.now().isoformat()
                })
            
            # 批量创建关系
            cypher = """
            UNWIND $data as row
            MATCH (m:Medic {id: row.medic_id})
            MATCH (h:Herb {id: row.herb_id})
            MERGE (m)-[r:CONTAINS]->(h)
            SET r.dosage = row.dosage,
                r.role = row.role,
                r.synced_at = row.synced_at,
                r.source = 'mysql_sync'
            """
            neo4j_session.run(cypher, {'data': relation_data})
            
            synced += len(batch)
            offset += batch_size
            
            # 更新进度
            progress = (synced / total) * 100
            self._update_progress(progress, "sync_medic_relationships", f"已同步 {synced}/{total} 个中成药-药材关系")
        
        return {'synced': synced, 'failed': 0, 'errors': []}
    
    def sync_attributes_to_neo4j(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession
    ) -> Dict[str, Any]:
        """
        同步功效、性味、归经节点和关系到Neo4j
        """
        self._update_progress(0, "sync_attributes", "开始同步属性数据...")
        
        results = {
            'efficacies': {'synced': 0, 'failed': 0},
            'natures': {'synced': 0, 'failed': 0},
            'meridians': {'synced': 0, 'failed': 0},
            'herb_efficacies': {'synced': 0, 'failed': 0},
            'herb_natures': {'synced': 0, 'failed': 0},
            'herb_meridians': {'synced': 0, 'failed': 0}
        }
        
        # 1. 同步功效节点
        self._update_progress(10, "sync_efficacies", "同步功效节点...")
        efficacies = mysql_session.query(Efficacy).all()
        efficacy_data = [{'id': e.id, 'name': e.name, 'description': e.description or ''} for e in efficacies]
        
        batch_size = 500
        for i in range(0, len(efficacy_data), batch_size):
            batch = efficacy_data[i:i+batch_size]
            cypher = """
            UNWIND $data as row
            MERGE (e:Efficacy {id: row.id})
            SET e.name = row.name, e.description = row.description
            """
            neo4j_session.run(cypher, {'data': batch})
        results['efficacies']['synced'] = len(efficacies)
        
        # 2. 同步性味节点
        self._update_progress(25, "sync_natures", "同步性味节点...")
        natures = mysql_session.query(Nature).all()
        nature_data = [{'id': n.id, 'name': n.name, 'description': n.description or ''} for n in natures]
        
        for i in range(0, len(nature_data), batch_size):
            batch = nature_data[i:i+batch_size]
            cypher = """
            UNWIND $data as row
            MERGE (n:Nature {id: row.id})
            SET n.name = row.name, n.description = row.description
            """
            neo4j_session.run(cypher, {'data': batch})
        results['natures']['synced'] = len(natures)
        
        # 3. 同步归经节点
        self._update_progress(40, "sync_meridians", "同步归经节点...")
        meridians = mysql_session.query(Meridian).all()
        meridian_data = [{'id': m.id, 'name': m.name, 'description': m.description or ''} for m in meridians]
        
        for i in range(0, len(meridian_data), batch_size):
            batch = meridian_data[i:i+batch_size]
            cypher = """
            UNWIND $data as row
            MERGE (m:Meridian {id: row.id})
            SET m.name = row.name, m.description = row.description
            """
            neo4j_session.run(cypher, {'data': batch})
        results['meridians']['synced'] = len(meridians)
        
        # 4. 建立Herb-Efficacy关系
        self._update_progress(55, "sync_herb_efficacies", "建立药材-功效关系...")
        result = mysql_session.execute(text("SELECT herb_id, efficacy_id FROM herb_efficacies"))
        associations = result.fetchall()
        
        batch_size = 1000
        total = len(associations)
        for i in range(0, total, batch_size):
            batch = associations[i:i+batch_size]
            rel_data = [{'herb_id': a.herb_id, 'efficacy_id': a.efficacy_id} for a in batch]
            cypher = """
            UNWIND $data as row
            MATCH (h:Herb {id: row.herb_id})
            MATCH (e:Efficacy {id: row.efficacy_id})
            MERGE (h)-[r:HAS_EFFICACY]->(e)
            """
            neo4j_session.run(cypher, {'data': rel_data})
            self._update_progress(55 + (i/total)*15, "sync_herb_efficacies", f"已同步 {min(i+batch_size, total)}/{total} 个药材-功效关系")
        results['herb_efficacies']['synced'] = total
        
        # 5. 建立Herb-Nature关系
        self._update_progress(70, "sync_herb_natures", "建立药材-性味关系...")
        result = mysql_session.execute(text("SELECT herb_id, nature_id FROM herb_natures"))
        associations = result.fetchall()
        
        total = len(associations)
        for i in range(0, total, batch_size):
            batch = associations[i:i+batch_size]
            rel_data = [{'herb_id': a.herb_id, 'nature_id': a.nature_id} for a in batch]
            cypher = """
            UNWIND $data as row
            MATCH (h:Herb {id: row.herb_id})
            MATCH (n:Nature {id: row.nature_id})
            MERGE (h)-[r:HAS_NATURE]->(n)
            """
            neo4j_session.run(cypher, {'data': rel_data})
            self._update_progress(70 + (i/total)*15, "sync_herb_natures", f"已同步 {min(i+batch_size, total)}/{total} 个药材-性味关系")
        results['herb_natures']['synced'] = total
        
        # 6. 建立Herb-Meridian关系
        self._update_progress(85, "sync_herb_meridians", "建立药材-归经关系...")
        result = mysql_session.execute(text("SELECT herb_id, meridian_id FROM herb_meridians"))
        associations = result.fetchall()
        
        total = len(associations)
        for i in range(0, total, batch_size):
            batch = associations[i:i+batch_size]
            rel_data = [{'herb_id': a.herb_id, 'meridian_id': a.meridian_id} for a in batch]
            cypher = """
            UNWIND $data as row
            MATCH (h:Herb {id: row.herb_id})
            MATCH (m:Meridian {id: row.meridian_id})
            MERGE (h)-[r:BELONGS_TO_MERIDIAN]->(m)
            """
            neo4j_session.run(cypher, {'data': rel_data})
            self._update_progress(85 + (i/total)*15, "sync_herb_meridians", f"已同步 {min(i+batch_size, total)}/{total} 个药材-归经关系")
        results['herb_meridians']['synced'] = total
        
        self._update_progress(100, "sync_attributes", "属性数据同步完成")
        
        return results
    
    def _cleanup_invalid_medic_labels(self, neo4j_session: Neo4jSession):
        """
        清理无效的Medic标签 - 移除ID > 1832的节点上的Medic标签
        这些节点实际上是Prescription节点被错误地标记了Medic标签
        """
        try:
            # 检查是否存在需要清理的节点
            result = neo4j_session.run("MATCH (m:Medic) WHERE m.id > 1832 RETURN count(m) as cnt")
            nodes_to_cleanup = result.single()["cnt"]
            
            if nodes_to_cleanup > 0:
                print(f"[SYNC] 发现 {nodes_to_cleanup} 个无效的Medic标签，正在清理...")
                
                # 移除ID > 1832的节点上的Medic标签
                result = neo4j_session.run("""
                MATCH (n:Medic) 
                WHERE n.id > 1832 
                REMOVE n:Medic
                RETURN count(n) as removed_count
                """)
                removed_count = result.single()["removed_count"]
                print(f"[SYNC] ✅ 成功清理了 {removed_count} 个无效的Medic标签")
            else:
                print("[SYNC] 未发现无效的Medic标签")
                
        except Exception as e:
            print(f"[SYNC] 清理无效Medic标签时出错: {e}")
    
    def _final_medic_consistency_check(self, neo4j_session: Neo4jSession):
        """
        全量同步完成后的最终一致性检查和修复
        确保Neo4j中的Medic节点数量与MySQL完全一致
        """
        try:
            # 获取MySQL中Medic的实际数量
            from app.db.session import SessionLocal
            from app.models.models import Medic
            db = SessionLocal()
            mysql_medic_count = db.query(Medic).filter(Medic.is_deleted == 0).count()
            db.close()
            
            # 获取Neo4j中Medic的数量
            result = neo4j_session.run("MATCH (m:Medic) RETURN count(m) as cnt")
            neo4j_medic_count = result.single()["cnt"]
            
            print(f"[SYNC] 最终一致性检查 - MySQL Medic: {mysql_medic_count}, Neo4j Medic: {neo4j_medic_count}")
            
            if neo4j_medic_count != mysql_medic_count:
                print(f"[SYNC] ⚠️  发现数据不一致，执行最终修复...")
                # 执行清理
                self._cleanup_invalid_medic_labels(neo4j_session)
                
                # 再次检查
                result = neo4j_session.run("MATCH (m:Medic) RETURN count(m) as cnt")
                final_count = result.single()["cnt"]
                
                if final_count == mysql_medic_count:
                    print(f"[SYNC] ✅ 最终修复成功！Medic节点数量现在一致: {final_count}")
                else:
                    print(f"[SYNC] ⚠️  最终修复后仍不一致 - MySQL: {mysql_medic_count}, Neo4j: {final_count}")
            else:
                print(f"[SYNC] ✅ 数据一致性验证通过！")
                
        except Exception as e:
            print(f"[SYNC] 最终一致性检查时出错: {e}")
    
    def full_sync_mysql_to_neo4j(
        self,
        sync_prescriptions: bool = True,
        sync_herbs: bool = True,
        sync_medics: bool = True,
        sync_relationships: bool = True,
        sync_attributes: bool = True,
        batch_size: int = 1000,
        max_workers: int = 10
    ) -> Dict[str, Any]:
        """
        执行全量同步（MySQL -> Neo4j）
        支持批量同步、进度追踪、并发处理
        
        Args:
            sync_prescriptions: 是否同步方剂
            sync_herbs: 是否同步药材
            sync_medics: 是否同步中成药
            sync_relationships: 是否同步关系
            sync_attributes: 是否同步属性(功效、性味、归经)
            batch_size: 批量操作大小
            max_workers: 最大并发线程数
        
        Returns:
            同步结果统计
        """
        self.sync_stats['status'] = SyncStatus.RUNNING.value
        self.sync_stats['start_time'] = datetime.now().isoformat()
        self.sync_stats['in_progress'] = True
        self.sync_stats['error_message'] = None
        
        total_stats = {
            'prescriptions': {'synced': 0, 'failed': 0, 'errors': []},
            'herbs': {'synced': 0, 'failed': 0, 'errors': []},
            'medics': {'synced': 0, 'failed': 0, 'errors': []},
            'prescription_relationships': {'synced': 0, 'failed': 0, 'errors': []},
            'medic_relationships': {'synced': 0, 'failed': 0, 'errors': []},
            'attributes': {},
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'errors': []
        }
        
        try:
            mysql_db = next(get_db())
            driver = get_neo4j_driver()
            
            with driver.session(database=settings.NEO4J_DATABASE) as neo4j_session:
                # 0. 清空Neo4j中的所有数据（全量同步前）
                self._update_progress(0, "clear_neo4j", "正在清空Neo4j数据...")
                print("[SYNC] 开始清空Neo4j数据...")

                # 先删除所有关系
                neo4j_session.run("MATCH ()-[r]->() DELETE r")
                print("[SYNC] 已删除所有关系")

                # 再删除所有节点
                neo4j_session.run("MATCH (n) DELETE n")
                print("[SYNC] 已删除所有节点")

                self._update_progress(0, "clear_neo4j", "Neo4j数据已清空")
                
                # 0.1. 清理可能存在的无效标签（虽然刚清空了，但为了保险起见）
                self._cleanup_invalid_medic_labels(neo4j_session)

                # 1. 同步方剂节点
                if sync_prescriptions:
                    self._update_progress(0, "sync_prescriptions", "开始同步方剂节点...")
                    prescription_stats = self.batch_sync_prescriptions(mysql_db, neo4j_session, batch_size, max_workers)
                    total_stats['prescriptions'] = prescription_stats
                
                # 2. 同步药材节点
                if sync_herbs:
                    self._update_progress(20, "sync_herbs", "开始同步药材节点...")
                    herb_stats = self.batch_sync_herbs(mysql_db, neo4j_session, batch_size, max_workers)
                    total_stats['herbs'] = herb_stats
                
                # 3. 同步中成药节点
                if sync_medics:
                    self._update_progress(40, "sync_medics", "开始同步中成药节点...")
                    medic_stats = self.batch_sync_medics(mysql_db, neo4j_session, batch_size, max_workers)
                    total_stats['medics'] = medic_stats
                
                # 4. 同步关系
                if sync_relationships:
                    self._update_progress(60, "sync_relationships", "开始同步关系...")
                    # 关系同步使用单线程避免死锁（多个线程同时操作相同节点会导致锁冲突）
                    relation_workers = 1
                    relation_batch_size = batch_size * 2
                    # 方剂-药材关系
                    pres_rel_stats = self.batch_sync_prescription_relationships(mysql_db, neo4j_session, relation_batch_size, relation_workers)
                    total_stats['prescription_relationships'] = pres_rel_stats
                    # 中成药-药材关系
                    medic_rel_stats = self.batch_sync_medic_relationships(mysql_db, neo4j_session, relation_batch_size, relation_workers)
                    total_stats['medic_relationships'] = medic_rel_stats
                
                # 5. 同步属性
                if sync_attributes:
                    self._update_progress(80, "sync_attributes", "开始同步属性数据...")
                    attr_stats = self.sync_attributes_to_neo4j(mysql_db, neo4j_session)
                    total_stats['attributes'] = attr_stats
                
                # 6. 执行最终一致性检查和修复
                self._update_progress(95, "final_check", "执行最终数据一致性检查和修复...")
                self._final_medic_consistency_check(neo4j_session)
                
                self._update_progress(100, "completed", "同步完成!")
            
            driver.close()
            
            # 清除相关缓存
            cache_clear("prescription_*")
            cache_clear("herb_*")
            cache_clear("medic_*")
            
            self.sync_stats['status'] = SyncStatus.COMPLETED.value
            self.sync_stats['total_synced'] = (
                total_stats['prescriptions']['synced'] + 
                total_stats['herbs']['synced'] +
                total_stats['medics']['synced'] +
                total_stats['prescription_relationships']['synced'] +
                total_stats['medic_relationships']['synced']
            )
            
        except Exception as e:
            self.sync_stats['status'] = SyncStatus.FAILED.value
            self.sync_stats['error_message'] = str(e)
            total_stats['errors'].append(str(e))
            raise
        finally:
            total_stats['end_time'] = datetime.now().isoformat()
            self._set_last_sync_time()  # 保存到Redis
            self.sync_stats['end_time'] = datetime.now().isoformat()
            self.sync_stats['in_progress'] = False
        
        return total_stats
    
    def incremental_sync(
        self,
        since: datetime = None,
        sync_prescriptions: bool = True,
        sync_herbs: bool = True,
        sync_medics: bool = True
    ) -> Dict[str, Any]:
        """
        执行增量同步
        
        Args:
            since: 同步该时间之后更新的数据，默认为上次同步时间
        """
        # 获取Neo4j连接（用于备用时间获取）
        from app.db.session import get_db, get_neo4j_driver
        from app.core.config import settings
        
        mysql_db = next(get_db())
        driver = get_neo4j_driver()
        
        # 在增量同步前清理无效标签
        try:
            with driver.session(database=settings.NEO4J_DATABASE) as neo4j_session:
                self._cleanup_invalid_medic_labels(neo4j_session)
        except Exception as e:
            print(f"[SYNC] 清理无效标签时出错: {e}")
        
        if since is None:
            # 优先使用Redis中的上次同步时间
            last_sync = self._get_last_sync_time()
            if last_sync:
                since = last_sync
                print(f"[SYNC] 使用Redis中的上次同步时间: {since}")
            else:
                # 备用方案：从Neo4j获取最大更新时间
                try:
                    with driver.session(database=settings.NEO4J_DATABASE) as neo4j_session:
                        neo4j_max_time = self._get_neo4j_max_updated_time(neo4j_session)
                    
                    if neo4j_max_time:
                        since = neo4j_max_time
                        print(f"[SYNC] 使用Neo4j最大更新时间作为参考: {since}")
                    else:
                        # 如果仍然没有找到同步时间，返回跳过信息
                        return {
                            'skipped': True,
                            'message': '未找到上次同步时间，请先执行全量同步'
                        }
                except Exception as e:
                    print(f"[SYNC] 获取Neo4j最大更新时间时出错: {e}")
                    return {
                        'skipped': True,
                        'message': '未找到上次同步时间，请先执行全量同步'
                    }
        
        print(f"[SYNC] 执行增量同步，从 {since} 开始...")
        
        # 设置同步状态
        self.sync_stats['status'] = SyncStatus.RUNNING.value
        self.sync_stats['start_time'] = datetime.now().isoformat()
        self.sync_stats['in_progress'] = True
        self.sync_stats['error_message'] = None
        
        total_stats = {
            'prescriptions': {'synced': 0, 'failed': 0, 'errors': []},
            'herbs': {'synced': 0, 'failed': 0, 'errors': []},
            'medics': {'synced': 0, 'failed': 0, 'errors': []},
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'errors': []
        }
        
        try:
            # 获取更新的节点ID列表（用于后续关系同步）
            updated_prescription_ids = set()
            updated_herb_ids = set()
            updated_medic_ids = set()
            
            if sync_prescriptions and since:
                updated_prescription_ids = {
                    p.id for p in mysql_db.query(Prescription.id)
                    .filter(Prescription.updated_at >= since)
                    .all()
                }
            
            if sync_herbs and since:
                updated_herb_ids = {
                    h.id for h in mysql_db.query(Herb.id)
                    .filter(Herb.updated_at >= since)
                    .all()
                }
            
            if sync_medics and since:
                updated_medic_ids = {
                    m.id for m in mysql_db.query(Medic.id)
                    .filter(Medic.updated_at >= since)
                    .all()
                }
            
            # 先统计需要同步的总数
            total_to_sync = 0
            if sync_prescriptions:
                total_to_sync += len(updated_prescription_ids)
            if sync_herbs:
                total_to_sync += len(updated_herb_ids)
            if sync_medics:
                total_to_sync += len(updated_medic_ids)
            
            print(f"[SYNC] 增量同步: {len(updated_prescription_ids)} 方剂, {len(updated_herb_ids)} 药材, {len(updated_medic_ids)} 中成药")
            
            if total_to_sync == 0:
                self._update_progress(100, "completed", "没有需要同步的数据")
                driver.close()
                self._set_last_sync_time()  # 即使没有数据也更新同步时间
                return total_stats
            
            synced_total = 0
            
            with driver.session(database=settings.NEO4J_DATABASE) as neo4j_session:
                # 同步方剂节点
                if sync_prescriptions and updated_prescription_ids:
                    self._update_progress(0, "sync_prescriptions", f"开始同步 {len(updated_prescription_ids)} 个更新的方剂...")
                    prescription_stats = self.sync_prescriptions_to_neo4j(
                        mysql_db, neo4j_session, since=since
                    )
                    total_stats['prescriptions'] = prescription_stats
                    synced_total += prescription_stats['synced']
                    
                    # 同步更新的方剂的关系
                    if prescription_stats['synced'] > 0:
                        self._update_progress(25, "sync_relationships", "同步方剂-药材关系...")
                        self._sync_prescription_relations_for_ids(
                            mysql_db, neo4j_session, updated_prescription_ids
                        )
                
                # 同步药材节点
                if sync_herbs and updated_herb_ids:
                    progress = min(99, (synced_total / total_to_sync) * 100) if total_to_sync > 0 else 0
                    self._update_progress(progress, "sync_herbs", f"开始同步 {len(updated_herb_ids)} 个更新的药材...")
                    herb_stats = self.sync_herbs_to_neo4j(
                        mysql_db, neo4j_session, since=since
                    )
                    total_stats['herbs'] = herb_stats
                    synced_total += herb_stats['synced']
                    
                    # 同步更新的药材的属性和关系
                    if herb_stats['synced'] > 0:
                        self._update_progress(50, "sync_attributes", "同步药材属性...")
                        self._sync_herb_attributes_for_ids(
                            mysql_db, neo4j_session, updated_herb_ids
                        )
                
                # 同步中成药节点
                if sync_medics and updated_medic_ids:
                    progress = min(99, (synced_total / total_to_sync) * 100) if total_to_sync > 0 else 0
                    self._update_progress(progress, "sync_medics", f"开始同步 {len(updated_medic_ids)} 个更新的中成药...")
                    medic_stats = self.sync_medics_to_neo4j(
                        mysql_db, neo4j_session, since=since
                    )
                    total_stats['medics'] = medic_stats
                    synced_total += medic_stats['synced']
                    
                    # 同步更新的中成药的关系
                    if medic_stats['synced'] > 0:
                        self._update_progress(75, "sync_relationships", "同步中成药-药材关系...")
                        self._sync_medic_relations_for_ids(
                            mysql_db, neo4j_session, updated_medic_ids
                        )
                
                self._update_progress(100, "completed", f"增量同步完成! 共同步 {synced_total} 条数据")
            
            driver.close()
            
            # 清除相关缓存
            from app.cache import cache_clear
            cache_clear("prescription_*")
            cache_clear("herb_*")
            cache_clear("medic_*")
            
            self.sync_stats['status'] = SyncStatus.COMPLETED.value
            self.sync_stats['total_synced'] = (
                total_stats['prescriptions']['synced'] + 
                total_stats['herbs']['synced'] +
                total_stats['medics']['synced']
            )
            
        except Exception as e:
            self.sync_stats['status'] = SyncStatus.FAILED.value
            self.sync_stats['error_message'] = str(e)
            total_stats['errors'].append(str(e))
            raise
        finally:
            total_stats['end_time'] = datetime.now().isoformat()
            self._set_last_sync_time()  # 保存到Redis
            self.sync_stats['end_time'] = datetime.now().isoformat()
            self.sync_stats['in_progress'] = False
        
        return total_stats
    
    def _sync_prescription_relations_for_ids(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        prescription_ids: set
    ):
        """同步指定方剂的关系（增量）- 批量优化版"""
        if not prescription_ids:
            return
        
        print(f"[SYNC] 同步 {len(prescription_ids)} 个方剂的关系...")
        
        # 查询这些方剂的关联关系
        associations = mysql_session.query(prescription_herb_association).filter(
            prescription_herb_association.c.prescription_id.in_(prescription_ids)
        ).all()
        
        if not associations:
            print(f"[SYNC] 没有需要同步的方剂关系")
            return
        
        # 获取角色信息缓存
        roles = {}
        for role in mysql_session.query(PrescriptionRole).all():
            roles[role.id] = role.name
        
        # 批量准备数据
        relation_data = []
        for assoc in associations:
            relation_data.append({
                'prescription_id': assoc.prescription_id,
                'herb_id': assoc.herb_id,
                'dosage': assoc.dosage,
                'role': roles.get(assoc.role_id, ''),
                'synced_at': datetime.now().isoformat()
            })
        
        # 批量创建关系 - 使用UNWIND
        batch_size = 1000
        total = len(relation_data)
        for i in range(0, total, batch_size):
            batch = relation_data[i:i+batch_size]
            try:
                cypher = """
                UNWIND $data as row
                MATCH (p:Prescription {id: row.prescription_id})
                MATCH (h:Herb {id: row.herb_id})
                MERGE (p)-[r:CONTAINS]->(h)
                SET r.dosage = row.dosage,
                    r.role = row.role,
                    r.synced_at = row.synced_at,
                    r.source = 'incremental_sync'
                """
                neo4j_session.run(cypher, {'data': batch})
                print(f"[SYNC] 已同步方剂关系 {min(i+batch_size, total)}/{total}")
            except Exception as e:
                print(f"[SYNC WARNING] 批量同步方剂关系失败: {e}")
    
    def _sync_medic_relations_for_ids(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        medic_ids: set
    ):
        """同步指定中成药的关系（增量）- 批量优化版"""
        if not medic_ids:
            return
        
        print(f"[SYNC] 同步 {len(medic_ids)} 个中成药的关系...")
        
        # 查询这些中成药的关联关系
        associations = mysql_session.query(medic_herb_association).filter(
            medic_herb_association.c.medic_id.in_(medic_ids)
        ).all()
        
        if not associations:
            print(f"[SYNC] 没有需要同步的中成药关系")
            return
        
        # 获取角色信息缓存
        roles = {}
        for role in mysql_session.query(PrescriptionRole).all():
            roles[role.id] = role.name
        
        # 批量准备数据
        relation_data = []
        for assoc in associations:
            relation_data.append({
                'medic_id': assoc.medic_id,
                'herb_id': assoc.herb_id,
                'dosage': assoc.dosage,
                'role': roles.get(assoc.role_id, ''),
                'synced_at': datetime.now().isoformat()
            })
        
        # 批量创建关系 - 使用UNWIND
        batch_size = 1000
        total = len(relation_data)
        for i in range(0, total, batch_size):
            batch = relation_data[i:i+batch_size]
            try:
                cypher = """
                UNWIND $data as row
                MATCH (m:Medic {id: row.medic_id})
                MATCH (h:Herb {id: row.herb_id})
                MERGE (m)-[r:CONTAINS]->(h)
                SET r.dosage = row.dosage,
                    r.role = row.role,
                    r.synced_at = row.synced_at,
                    r.source = 'incremental_sync'
                """
                neo4j_session.run(cypher, {'data': batch})
                print(f"[SYNC] 已同步中成药关系 {min(i+batch_size, total)}/{total}")
            except Exception as e:
                print(f"[SYNC WARNING] 批量同步中成药关系失败: {e}")
    
    def _sync_herb_attributes_for_ids(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession,
        herb_ids: set
    ):
        """同步指定药材的属性（功效、性味、归经）（增量）- 批量优化版"""
        if not herb_ids:
            return
        
        print(f"[SYNC] 同步 {len(herb_ids)} 个药材的属性...")
        
        # 同步功效
        from app.models.v2_models import herb_efficacy_association, Efficacy
        efficacy_assocs = mysql_session.query(herb_efficacy_association).filter(
            herb_efficacy_association.c.herb_id.in_(herb_ids)
        ).all()
        
        if efficacy_assocs:
            # 批量获取功效数据
            efficacy_ids = {a.efficacy_id for a in efficacy_assocs}
            efficacies = mysql_session.query(Efficacy).filter(Efficacy.id.in_(efficacy_ids)).all()
            efficacy_map = {e.id: e for e in efficacies}
            
            # 批量创建功效节点
            efficacy_data = [{'id': e.id, 'name': e.name} for e in efficacies]
            if efficacy_data:
                neo4j_session.run("""
                    UNWIND $data as row
                    MERGE (e:Efficacy {id: row.id})
                    SET e.name = row.name, e.source_db = 'mysql'
                """, {'data': efficacy_data})
            
            # 批量创建关系
            rel_data = [{'herb_id': a.herb_id, 'efficacy_id': a.efficacy_id} for a in efficacy_assocs]
            neo4j_session.run("""
                UNWIND $data as row
                MATCH (h:Herb {id: row.herb_id})
                MATCH (e:Efficacy {id: row.efficacy_id})
                MERGE (h)-[r:HAS_EFFICACY]->(e)
                SET r.source = 'incremental_sync'
            """, {'data': rel_data})
            print(f"[SYNC] 已同步 {len(efficacy_assocs)} 个药材-功效关系")
        
        # 同步性味
        from app.models.v2_models import herb_nature_association, Nature
        nature_assocs = mysql_session.query(herb_nature_association).filter(
            herb_nature_association.c.herb_id.in_(herb_ids)
        ).all()
        
        if nature_assocs:
            # 批量获取性味数据
            nature_ids = {a.nature_id for a in nature_assocs}
            natures = mysql_session.query(Nature).filter(Nature.id.in_(nature_ids)).all()
            
            # 批量创建性味节点
            nature_data = [{'id': n.id, 'name': n.name} for n in natures]
            if nature_data:
                neo4j_session.run("""
                    UNWIND $data as row
                    MERGE (n:Nature {id: row.id})
                    SET n.name = row.name, n.source_db = 'mysql'
                """, {'data': nature_data})
            
            # 批量创建关系
            rel_data = [{'herb_id': a.herb_id, 'nature_id': a.nature_id} for a in nature_assocs]
            neo4j_session.run("""
                UNWIND $data as row
                MATCH (h:Herb {id: row.herb_id})
                MATCH (n:Nature {id: row.nature_id})
                MERGE (h)-[r:HAS_NATURE]->(n)
                SET r.source = 'incremental_sync'
            """, {'data': rel_data})
            print(f"[SYNC] 已同步 {len(nature_assocs)} 个药材-性味关系")
        
        # 同步归经
        from app.models.v2_models import herb_meridian_association, Meridian
        meridian_assocs = mysql_session.query(herb_meridian_association).filter(
            herb_meridian_association.c.herb_id.in_(herb_ids)
        ).all()
        
        if meridian_assocs:
            # 批量获取归经数据
            meridian_ids = {a.meridian_id for a in meridian_assocs}
            meridians = mysql_session.query(Meridian).filter(Meridian.id.in_(meridian_ids)).all()
            
            # 批量创建归经节点
            meridian_data = [{'id': m.id, 'name': m.name} for m in meridians]
            if meridian_data:
                neo4j_session.run("""
                    UNWIND $data as row
                    MERGE (m:Meridian {id: row.id})
                    SET m.name = row.name, m.source_db = 'mysql'
                """, {'data': meridian_data})
            
            # 批量创建关系
            rel_data = [{'herb_id': a.herb_id, 'meridian_id': a.meridian_id} for a in meridian_assocs]
            neo4j_session.run("""
                UNWIND $data as row
                MATCH (h:Herb {id: row.herb_id})
                MATCH (m:Meridian {id: row.meridian_id})
                MERGE (h)-[r:BELONGS_TO_MERIDIAN]->(m)
                SET r.source = 'incremental_sync'
            """, {'data': rel_data})
            print(f"[SYNC] 已同步 {len(meridian_assocs)} 个药材-归经关系")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        is_in_progress = self.sync_stats['status'] == SyncStatus.RUNNING.value
        return {
            'status': self.sync_stats['status'],
            'last_sync_time': self._get_last_sync_time().isoformat() if self._get_last_sync_time() else None,
            'total_synced': self.sync_stats['total_synced'],
            'failed_count': self.sync_stats['failed_count'],
            'in_progress': is_in_progress
        }
    
    def validate_data_consistency(
        self,
        mysql_session: Session,
        neo4j_session: Neo4jSession
    ) -> Dict[str, Any]:
        """
        验证MySQL和Neo4j数据一致性
        
        Returns:
            一致性检查结果
        """
        result = {
            'consistent': True,
            'differences': [],
            'mysql_counts': {},
            'neo4j_counts': {}
        }
        
        # 统计MySQL数据
        result['mysql_counts']['prescriptions'] = mysql_session.query(Prescription).count()
        result['mysql_counts']['herbs'] = mysql_session.query(Herb).count()
        result['mysql_counts']['efficacies'] = mysql_session.query(Efficacy).count()
        result['mysql_counts']['medics'] = mysql_session.query(Medic).count()
        result['mysql_counts']['prescription_roles'] = mysql_session.query(PrescriptionRole).count()
        
        # 统计Neo4j数据
        neo4j_result = neo4j_session.run("""
            MATCH (p:Prescription) RETURN count(p) as count
        """)
        result['neo4j_counts']['prescriptions'] = neo4j_result.single()['count']
        
        neo4j_result = neo4j_session.run("""
            MATCH (h:Herb) RETURN count(h) as count
        """)
        result['neo4j_counts']['herbs'] = neo4j_result.single()['count']
        
        neo4j_result = neo4j_session.run("""
            MATCH (e:Efficacy) RETURN count(e) as count
        """)
        result['neo4j_counts']['efficacies'] = neo4j_result.single()['count']
        
        neo4j_result = neo4j_session.run("""
            MATCH (m:Medic) RETURN count(m) as count
        """)
        result['neo4j_counts']['medics'] = neo4j_result.single()['count']
        
        neo4j_result = neo4j_session.run("""
            MATCH (n:Nature) RETURN count(n) as count
        """)
        result['neo4j_counts']['natures'] = neo4j_result.single()['count']
        
        neo4j_result = neo4j_session.run("""
            MATCH (m:Meridian) RETURN count(m) as count
        """)
        result['neo4j_counts']['meridians'] = neo4j_result.single()['count']
        
        # 统计MySQL中的属性数据
        result['mysql_counts']['natures'] = mysql_session.query(Nature).count()
        result['mysql_counts']['meridians'] = mysql_session.query(Meridian).count()
        
        # 统计关系数量
        neo4j_result = neo4j_session.run("""
            MATCH ()-[r]->() RETURN count(r) as count
        """)
        result['neo4j_counts']['relationships'] = neo4j_result.single()['count']
        
        # 检查差异
        entities = ['prescriptions', 'herbs', 'efficacies', 'medics', 'natures', 'meridians']
        for entity in entities:
            mysql_count = result['mysql_counts'].get(entity, 0)
            neo4j_count = result['neo4j_counts'].get(entity, 0)
            
            if mysql_count != neo4j_count:
                result['consistent'] = False
                result['differences'].append({
                    'entity': entity,
                    'mysql_count': mysql_count,
                    'neo4j_count': neo4j_count,
                    'difference': mysql_count - neo4j_count
                })
        
        return result


# 全局同步服务实例
sync_service = DataSyncService()
