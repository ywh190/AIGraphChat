"""
认证和用户管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    UserCreate, UserResponse, UserUpdate,
    UserLogin, Token, PasswordChange
)
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token
)
from app.core.dependencies import (
    get_current_active_user,
    get_current_admin_user
)
from app.core.config import settings

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    用户注册

    - **username**: 用户名（3-50字符，仅字母数字）
    - **email**: 邮箱地址
    - **password**: 密码（至少6位）
    - **full_name**: 全名（可选）
    """
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 检查邮箱是否已存在
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用"
        )

    # 创建用户
    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole.USER  # 默认为普通用户
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    用户登录

    使用OAuth2密码流，返回访问令牌和刷新令牌
    """
    # 查找用户
    user = db.query(User).filter(User.username == form_data.username).first()

    # 验证用户和密码
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查账户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账户已被禁用"
        )

    # 创建令牌
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/login/json", response_model=Token)
async def login_json(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    用户登录（JSON格式）

    与 /login 功能相同，但使用JSON格式而非表单格式
    """
    user = db.query(User).filter(User.username == login_data.username).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账户已被禁用"
        )

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前登录用户信息

    需要认证
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新当前用户信息

    需要认证
    """
    # 更新邮箱
    if user_update.email and user_update.email != current_user.email:
        # 检查邮箱是否已被其他用户使用
        existing_email = db.query(User).filter(
            User.email == user_update.email,
            User.id != current_user.id
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被其他用户使用"
            )
        current_user.email = user_update.email

    # 更新全名
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    # 更新密码
    if user_update.password:
        current_user.hashed_password = get_password_hash(user_update.password)

    db.commit()
    db.refresh(current_user)

    return current_user


@router.post("/change-password")
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    修改当前用户密码

    需要认证
    """
    # 验证旧密码
    if not verify_password(password_change.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )

    # 更新密码
    current_user.hashed_password = get_password_hash(password_change.new_password)
    db.commit()

    return {"message": "密码修改成功"}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取所有用户列表（管理员权限）

    需要管理员权限
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取指定用户信息（管理员权限）

    需要管理员权限
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    更新指定用户信息（管理员权限）

    需要管理员权限
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 更新邮箱
    if user_update.email:
        existing_email = db.query(User).filter(
            User.email == user_update.email,
            User.id != user_id
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )
        user.email = user_update.email

    # 更新全名
    if user_update.full_name is not None:
      user.full_name = user_update.full_name

    # 更新密码
    if user_update.password:
      user.hashed_password = get_password_hash(user_update.password)

    # 更新角色
    if user_update.role is not None:
      user.role = user_update.role

    # 更新激活状态
    if user_update.is_active is not None:
      user.is_active = user_update.is_active

    db.commit()
    db.refresh(user)

    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    删除指定用户（管理员权限）

    需要管理员权限
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    db.delete(user)
    db.commit()

    return {"message": "用户已删除"}
