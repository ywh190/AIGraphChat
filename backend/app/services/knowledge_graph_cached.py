"""
带缓存的知识图谱查询服务
包装原始服务，添加Redis缓存支持
"""
from typing import Dict, List, Any, Optional
from app.cache import cache, cache_clear, cache_delete
from app.db.session import get_neo4j_session
from app.services import knowledge_graph_service as kg_service


class CachedKnowledgeGraphService:
    """带缓存的知识图谱查询服务"""
    
    @staticmethod
    @cache(ttl=3600, key_prefix="prescription_roles")
    def get_prescription_with_roles(prescription_name: str) -> Dict:
        """
        获取方剂的君臣佐使信息（带缓存）
        
        Cache Key: prescription_roles:{prescription_name_hash}
        TTL: 1小时
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.get_prescription_with_roles(s, prescription_name)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return {'prescription': None, 'roles': {'君': [], '臣': [], '佐': [], '使': []}}
    
    @staticmethod
    @cache(ttl=3600, key_prefix="herbs_by_role")
    def get_herbs_by_role(prescription_name: str, role: str) -> List[Dict]:
        """
        获取某方剂中担任特定角色的药材（带缓存）
        
        Cache Key: herbs_by_role:{prescription_name}_{role}_hash
        TTL: 1小时
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.get_herbs_by_role(s, prescription_name, role)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return []
    
    @staticmethod
    @cache(ttl=1800, key_prefix="herb_prescriptions")
    def get_herb_prescriptions(herb_name: str) -> List[Dict]:
        """
        获取某药材的所有方剂及其在该方剂中的角色（带缓存）
        
        Cache Key: herb_prescriptions:{herb_name_hash}
        TTL: 30分钟
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.get_herb_prescriptions(s, herb_name)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return []
    
    @staticmethod
    @cache(ttl=3600, key_prefix="prescription_analysis")
    def analyze_prescription_composition(prescription_name: str) -> Optional[Dict]:
        """
        分析方剂组成（带缓存）
        
        Cache Key: prescription_analysis:{prescription_name_hash}
        TTL: 1小时
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.analyze_prescription_composition(s, prescription_name)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return None
    
    @staticmethod
    @cache(ttl=3600, key_prefix="prescription_herbs_detailed")
    def get_prescription_herbs_detailed(prescription_name: str) -> List[Dict]:
        """
        获取方剂的详细药材信息（带缓存）
        
        Cache Key: prescription_herbs_detailed:{prescription_name_hash}
        TTL: 1小时
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.get_prescription_herbs_detailed(s, prescription_name)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return []
    
    @staticmethod
    @cache(ttl=7200, key_prefix="graph_statistics")
    def get_graph_statistics() -> Dict:
        """
        获取图谱统计信息（带缓存）
        
        Cache Key: graph_statistics
        TTL: 2小时（统计数据变化不频繁）
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.get_graph_statistics(s)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return {
                'total_nodes': 0,
                'total_relationships': 0,
                'label_distribution': []
            }
    
    @staticmethod
    @cache(ttl=1800, key_prefix="search_nodes")
    def search_nodes(query: str, node_type: str = None, limit: int = 10) -> List[Dict]:
        """
        搜索节点（带缓存）
        
        Cache Key: search_nodes:{query}_{node_type}_{limit}_hash
        TTL: 30分钟（搜索结果可能随数据变化）
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.search_nodes(s, query, node_type, limit)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return []
    
    @staticmethod
    @cache(ttl=3600, key_prefix="efficacy_statistics")
    def get_efficacy_statistics() -> List[Dict]:
        """
        获取功效统计信息（带缓存）
        
        Cache Key: efficacy_statistics
        TTL: 1小时
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.get_efficacy_statistics(s)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return []
    
    @staticmethod
    @cache(ttl=3600, key_prefix="category_statistics")
    def get_category_statistics() -> List[Dict]:
        """
        获取类别统计信息（带缓存）
        
        Cache Key: category_statistics
        TTL: 1小时
        """
        session = get_neo4j_session()
        try:
            with session as s:
                return kg_service.get_category_statistics(s)
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return []
    
    # ==================== 缓存管理方法 ====================
    
    @staticmethod
    def clear_prescription_cache(prescription_name: str = None):
        """清除方剂相关缓存"""
        if prescription_name:
            # 清除特定方剂的缓存
            cache_delete(f"prescription_roles:{prescription_name}")
            cache_delete(f"prescription_analysis:{prescription_name}")
            cache_delete(f"prescription_herbs_detailed:{prescription_name}")
            print(f"[INFO] 清除方剂 '{prescription_name}' 的缓存")
        else:
            # 清除所有方剂缓存
            cache_clear("prescription_*")
            print("[INFO] 清除所有方剂缓存")
    
    @staticmethod
    def clear_herb_cache(herb_name: str = None):
        """清除药材相关缓存"""
        if herb_name:
            cache_delete(f"herb_prescriptions:{herb_name}")
            print(f"[INFO] 清除药材 '{herb_name}' 的缓存")
        else:
            cache_clear("herb_*")
            print("[INFO] 清除所有药材缓存")
    
    @staticmethod
    def clear_statistics_cache():
        """清除统计数据缓存"""
        cache_clear("graph_statistics")
        cache_clear("efficacy_statistics")
        cache_clear("category_statistics")
        print("[INFO] 清除所有统计数据缓存")
    
    @staticmethod
    def clear_all_cache():
        """清除所有缓存"""
        cache_clear("*")
        print("[INFO] 清除所有缓存")


# 便捷导出
cached_kg_service = CachedKnowledgeGraphService()
