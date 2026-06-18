"""
MySQL 数据访问层实现
封装 MySQL 关系数据库操作
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.models import Herb, Prescription, Efficacy
from .base import BaseDAL


class MySQLDAL(BaseDAL):
    """MySQL 数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_node_by_id(self, node_id: Any) -> Optional[Dict]:
        """根据ID获取节点（支持药材、方剂、功效）"""
        # 尝试从不同表中查找
        node = (self.session.query(Herb).filter(Herb.id == node_id).first() or
                self.session.query(Prescription).filter(Prescription.id == node_id).first() or
                self.session.query(Efficacy).filter(Efficacy.id == node_id).first())
        
        if node:
            return self._model_to_dict(node)
        return None
    
    def search_nodes(self, query: str, node_type: str = None, limit: int = 10) -> List[Dict]:
        """搜索节点（按名称模糊匹配）"""
        results = []
        
        if node_type is None or node_type == 'herb':
            herbs = self.session.query(Herb).filter(
                Herb.name.ilike(f'%{query}%')
            ).limit(limit).all()
            results.extend([self._model_to_dict(h) for h in herbs])
        
        if node_type is None or node_type == 'prescription':
            prescriptions = self.session.query(Prescription).filter(
                Prescription.name.ilike(f'%{query}%')
            ).limit(limit).all()
            results.extend([self._model_to_dict(p) for p in prescriptions])
        
        if node_type is None or node_type == 'efficacy':
            efficacies = self.session.query(Efficacy).filter(
                Efficacy.name.ilike(f'%{query}%')
            ).limit(limit).all()
            results.extend([self._model_to_dict(e) for e in efficacies])
        
        return results[:limit]
    
    def create_node(self, node_data: Dict) -> Dict:
        """创建节点"""
        node_type = node_data.get('type', 'herb')
        properties = node_data.get('properties', {})
        
        if node_type == 'herb':
            model = Herb(**properties)
        elif node_type == 'prescription':
            model = Prescription(**properties)
        elif node_type == 'efficacy':
            model = Efficacy(**properties)
        else:
            raise ValueError(f"不支持的节点类型: {node_type}")
        
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        
        return self._model_to_dict(model)
    
    def update_node(self, node_id: Any, update_data: Dict) -> Optional[Dict]:
        """更新节点属性"""
        node = self.get_node_by_id(node_id)
        if not node:
            return None
        
        # 根据节点类型获取对应的模型
        model_class = self._get_model_class(node['type'])
        model = self.session.query(model_class).filter(model_class.id == node_id).first()
        
        if model:
            for key, value in update_data.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            self.session.commit()
            self.session.refresh(model)
            return self._model_to_dict(model)
        return None
    
    def delete_node(self, node_id: Any) -> bool:
        """删除节点"""
        node = self.get_node_by_id(node_id)
        if not node:
            return False
        
        model_class = self._get_model_class(node['type'])
        model = self.session.query(model_class).filter(model_class.id == node_id).first()
        
        if model:
            self.session.delete(model)
            self.session.commit()
            return True
        return False
    
    def create_relationship(self, from_id: Any, to_id: Any, rel_type: str, properties: Dict = None) -> bool:
        """创建关系（MySQL中通常通过关联表实现）"""
        # 根据具体业务逻辑实现
        # 例如：方剂-药材关联、药材-功效关联等
        # 这里需要根据实际的关联表结构进行实现
        # 当前版本暂不实现复杂的关联关系创建
        raise NotImplementedError("MySQL关系创建需要根据具体关联表实现")
    
    def execute_query(self, query: str, parameters: Dict = None) -> List[Dict]:
        """执行自定义SQL查询"""
        if parameters is None:
            parameters = {}
        
        # 使用SQLAlchemy的text()执行原生SQL
        from sqlalchemy import text
        result = self.session.execute(text(query), parameters)
        
        records = []
        for row in result:
            records.append(dict(row._mapping))
        return records
    
    # MySQL 专用方法
    def get_herb_with_prescriptions(self, herb_id: int) -> Dict:
        """获取药材及其相关的方剂"""
        herb = self.session.query(Herb).filter(Herb.id == herb_id).first()
        if not herb:
            return None
        
        # 查询包含该药材的方剂
        from sqlalchemy.orm import aliased
        from app.models.models import prescription_herb_association
        
        prescriptions = self.session.query(Prescription).join(
            prescription_herb_association
        ).filter(
            prescription_herb_association.c.herb_id == herb_id
        ).all()
        
        return {
            'herb': self._model_to_dict(herb),
            'prescriptions': [self._model_to_dict(p) for p in prescriptions]
        }
    
    # 辅助方法
    def _model_to_dict(self, model) -> Dict:
        """将SQLAlchemy模型转换为字典"""
        if model is None:
            return None
        
        result = {column.name: getattr(model, column.name) 
                 for column in model.__table__.columns}
        result['type'] = model.__tablename__
        return result
    
    def _get_model_class(self, node_type: str):
        """根据节点类型获取模型类"""
        if node_type == 'herb':
            return Herb
        elif node_type == 'prescription':
            return Prescription
        elif node_type == 'efficacy':
            return Efficacy
        else:
            raise ValueError(f"不支持的节点类型: {node_type}")