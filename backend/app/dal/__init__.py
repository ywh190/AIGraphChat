"""
数据访问层 (DAL) 模块
提供统一的数据库操作接口，封装 MySQL 和 Neo4j 的具体实现
"""

from .base import BaseDAL
from .neo4j_dal import Neo4jDAL
from .mysql_dal import MySQLDAL

__all__ = ["BaseDAL", "Neo4jDAL", "MySQLDAL"]