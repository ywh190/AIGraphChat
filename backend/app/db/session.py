from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# MySQL 数据库引擎
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Neo4j 驱动
from neo4j import GraphDatabase

# 全局 Neo4j driver 单例
_neo4j_driver = None

def get_neo4j_driver():
    """获取 Neo4j driver 单例"""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _neo4j_driver

def get_neo4j_session():
    """获取 Neo4j session（FastAPI依赖注入）"""
    driver = get_neo4j_driver()
    try:
        # Check if database is already specified in the URI
        if "/" in settings.NEO4J_URI.split(":", 2)[-1]:
            # Database is already in URI, don't specify it again
            session = driver.session()
        else:
            # Database is not in URI, specify it separately
            session = driver.session(database=settings.NEO4J_DATABASE)
        yield session
    finally:
        session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()