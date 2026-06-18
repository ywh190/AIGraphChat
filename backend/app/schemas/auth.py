"""
认证相关的Pydantic模型
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")


class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=6, max_length=100, description="密码")

    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('用户名只能包含字母和数字')
        return v

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v


class UserUpdate(BaseModel):
    """用户更新模型"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """用户登录模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class Token(BaseModel):
    """令牌模型"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """令牌数据模型"""
    username: Optional[str] = None
    user_id: Optional[int] = None


class PasswordChange(BaseModel):
    """修改密码模型"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")

    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('新密码长度至少6位')
        return v


class PasswordReset(BaseModel):
    """密码重置模型"""
    email: EmailStr = Field(..., description="邮箱")
