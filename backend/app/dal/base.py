"""
数据访问层基础抽象类
定义统一的数据库操作接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseDAL(ABC):
    """数据访问层基础抽象类"""
    
    @abstractmethod
    def get_node_by_id(self, node_id: Any) -> Optional[Dict]:
        """根据ID获取节点"""
        pass
    
    @abstractmethod
    def search_nodes(self, query: str, node_type: str = None, limit: int = 10) -> List[Dict]:
        """搜索节点"""
        pass
    
    @abstractmethod
    def create_node(self, node_data: Dict) -> Dict:
        """创建节点"""
        pass
    
    @abstractmethod
    def update_node(self, node_id: Any, update_data: Dict) -> Optional[Dict]:
        """更新节点"""
        pass
    
    @abstractmethod
    def delete_node(self, node_id: Any) -> bool:
        """删除节点"""
        pass
    
    @abstractmethod
    def create_relationship(self, from_id: Any, to_id: Any, rel_type: str, properties: Dict = None) -> bool:
        """创建关系"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, parameters: Dict = None) -> List[Dict]:
        """执行自定义查询"""
        pass