"""
认证和授权依赖
用于FastAPI路由保护
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

# OAuth2密码Bearer令牌配置
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前登录用户

    Args:
        token: JWT令牌
        db: 数据库会话

    Returns:
        当前用户对象

    Raises:
        HTTPException: 认证失败时抛出401错误
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 解码令牌
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    # 提取用户ID（sub是字符串，需要转换为整数）
    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    # 查询用户
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户已被禁用"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前活跃用户

    Args:
        current_user: 当前用户

    Returns:
        活跃用户对象

    Raises:
        HTTPException: 用户不活跃时抛出400错误
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户不活跃"
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前管理员用户

    Args:
        current_user: 当前用户

    Returns:
        管理员用户对象

    Raises:
        HTTPException: 非管理员用户时抛出403错误
    """
    # 兼容字符串和枚举类型的角色比较
    user_role = current_user.role
    if isinstance(user_role, UserRole):
        user_role = user_role.value
    
    if user_role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限"
        )
    return current_user


# 可选的认证依赖（允许匿名访问）
async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    可选的当前用户（允许未认证访问）

    Args:
        token: JWT令牌（可选）
        db: 数据库会话

    Returns:
        用户对象，如果未提供令牌或令牌无效则返回None
    """
    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload is None:
            return None

        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            return None

        user = db.query(User).filter(User.id == user_id).first()
        return user
    except (JWTError, Exception):
        return None
