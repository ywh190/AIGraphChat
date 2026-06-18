"""
Neo4j 数据访问层实现
封装 Neo4j 图数据库操作
"""
from typing import List, Dict, Any, Optional
from neo4j import Session
from .base import BaseDAL


class Neo4jDAL(BaseDAL):
    """Neo4j 数据访问层"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_node_by_id(self, node_id: Any) -> Optional[Dict]:
        """根据ID获取节点（Neo4j使用element_id作为内部ID）"""
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        RETURN n, labels(n) as labels, properties(n) as properties
        """
        result = self.session.run(query, node_id=node_id)
        record = result.single()
        if record:
            return {
                'id': record['properties'].get('id'),
                'element_id': node_id,
                'labels': record['labels'],
                'properties': dict(record['properties']),
                'node': record['n']
            }
        return None
    
    def search_nodes(self, query: str, node_type: str = None, limit: int = 10) -> List[Dict]:
        """搜索节点（按名称模糊匹配）"""
        cypher_query = """
        MATCH (n)
        WHERE n.name CONTAINS $query
        """
        if node_type:
            cypher_query += f" AND '{node_type}' IN labels(n)"
        cypher_query += """
        RETURN n, labels(n) as labels, properties(n) as properties
        LIMIT $limit
        """
        result = self.session.run(cypher_query, query=query, limit=limit)
        nodes = []
        for record in result:
            nodes.append({
                'id': record['properties'].get('id'),
                'element_id': record['n'].element_id,
                'labels': record['labels'],
                'properties': dict(record['properties']),
                'node': record['n']
            })
        return nodes
    
    def create_node(self, node_data: Dict) -> Dict:
        """创建节点"""
        labels = node_data.get('labels', ['Node'])
        properties = node_data.get('properties', {})
        
        # 构建标签字符串
        label_str = ':'.join(labels)
        # 构建属性参数
        prop_params = {f'prop_{k}': v for k, v in properties.items()}
        
        query = f"CREATE (n:{label_str} $props) RETURN n, labels(n) as labels, properties(n) as properties"
        result = self.session.run(query, props=properties)
        record = result.single()
        
        if record:
            return {
                'id': record['properties'].get('id'),
                'element_id': record['n'].element_id,
                'labels': record['labels'],
                'properties': dict(record['properties']),
                'node': record['n']
            }
        return None
    
    def update_node(self, node_id: Any, update_data: Dict) -> Optional[Dict]:
        """更新节点属性"""
        # Neo4j 使用 element_id 作为内部标识
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        SET n += $update_data
        RETURN n, labels(n) as labels, properties(n) as properties
        """
        result = self.session.run(query, node_id=node_id, update_data=update_data)
        record = result.single()
        if record:
            return {
                'id': record['properties'].get('id'),
                'element_id': node_id,
                'labels': record['labels'],
                'properties': dict(record['properties']),
                'node': record['n']
            }
        return None
    
    def delete_node(self, node_id: Any) -> bool:
        """删除节点及其所有关系"""
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        DETACH DELETE n
        """
        result = self.session.run(query, node_id=node_id)
        summary = result.consume()
        return summary.counters.nodes_deleted > 0
    
    def create_relationship(self, from_id: Any, to_id: Any, rel_type: str, properties: Dict = None) -> bool:
        """创建关系"""
        if properties is None:
            properties = {}
        
        query = """
        MATCH (a), (b)
        WHERE elementId(a) = $from_id AND elementId(b) = $to_id
        CREATE (a)-[r:%s $props]->(b)
        RETURN r
        """ % rel_type
        
        result = self.session.run(query, from_id=from_id, to_id=to_id, props=properties)
        record = result.single()
        return record is not None
    
    def execute_query(self, query: str, parameters: Dict = None) -> List[Dict]:
        """执行自定义Cypher查询"""
        if parameters is None:
            parameters = {}
        result = self.session.run(query, **parameters)
        records = []
        for record in result:
            # 将Record对象转换为字典
            records.append(dict(record))
        return records
    
    # Neo4j 专用方法
    def get_graph_statistics(self) -> Dict:
        """获取图数据库统计信息"""
        query = """
        CALL apoc.meta.stats() YIELD labels, relTypesCount, propertyKeys, nodeCount, relCount
        RETURN labels, relTypesCount, propertyKeys, nodeCount, relCount
        """
        result = self.session.run(query)
        record = result.single()
        if record:
            return dict(record)
        return {}
    
    def find_paths(self, start_id: Any, end_id: Any, max_depth: int = 3) -> List[Dict]:
        """查找两个节点之间的路径"""
        query = """
        MATCH (a), (b)
        WHERE elementId(a) = $start_id AND elementId(b) = $end_id
        MATCH path = shortestPath((a)-[*..%d]-(b))
        RETURN path, nodes(path) as nodes, relationships(path) as relationships
        """ % max_depth
        
        result = self.session.run(query, start_id=start_id, end_id=end_id)
        paths = []
        for record in result:
            paths.append({
                'path': record['path'],
                'nodes': [dict(node) for node in record['nodes']],
                'relationships': [dict(rel) for rel in record['relationships']]
            })
        return paths