"""
安全工具模块
包含密码哈希、JWT令牌生成和验证等功能
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码

    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    生成密码哈希

    Args:
        password: 明文密码

    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌

    Args:
        data: 要编码的数据（通常包含用户ID和用户名）
        expires_delta: 过期时间增量

    Returns:
        JWT令牌字符串
    """
    to_encode = data.copy()

    # 将sub转换为字符串（JWT标准要求）
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)  # 默认30分钟过期

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    创建刷新令牌（有效期更长）

    Args:
        data: 要编码的数据

    Returns:
        JWT令牌字符串
    """
    to_encode = data.copy()
    
    # 将sub转换为字符串（JWT标准要求）
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    
    expire = datetime.utcnow() + timedelta(days=7)  # 刷新令牌7天有效

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    解码令牌

    Args:
        token: JWT令牌字符串

    Returns:
        解码后的数据，如果无效则返回None
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        print(f"Token解码失败: {e}")
        return None
