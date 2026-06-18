"""
用户模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
import enum

# 导入统一的Base，确保所有模型使用同一个元数据
from app.db.session import Base


class UserRole(str, enum.Enum):
    """用户角色枚举"""
    ADMIN = "admin"          # 管理员
    USER = "user"            # 普通用户


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, comment="用户ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="加密密码")
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False, comment="用户角色")
    is_active = Column(Boolean, default=True, comment="是否激活")
    full_name = Column(String(100), comment="全名")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
