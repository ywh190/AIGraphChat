# 认证系统使用文档

## 概述

认证系统提供了完整的用户注册、登录、权限管理功能，支持基于JWT令牌的身份验证和角色授权。

## 功能特性

### 1. 用户角色
- **ADMIN（管理员）**：拥有所有权限，可以管理所有用户和数据
- **USER（普通用户）**：拥有基本访问权限

### 2. 认证机制
- 使用JWT（JSON Web Token）进行身份验证
- 支持访问令牌和刷新令牌
- 密码使用bcrypt加密存储
- 令牌过期时间：访问令牌30分钟，刷新令牌7天

## API接口

### 1. 用户注册

```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com",
  "password": "password123",
  "full_name": "用户全名"
}
```

**响应示例**：
```json
{
  "id": 3,
  "username": "newuser",
  "email": "user@example.com",
  "full_name": "用户全名",
  "role": "user",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

### 2. 用户登录（表单格式）

```bash
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

### 3. 用户登录（JSON格式）

```bash
POST /api/auth/login/json
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

**响应示例**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "系统管理员",
    "role": "admin",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
}
```

### 4. 获取当前用户信息

```bash
GET /api/auth/me
Authorization: Bearer {access_token}
```

### 5. 更新当前用户信息

```bash
PUT /api/auth/me
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "email": "newemail@example.com",
  "full_name": "新全名"
}
```

### 6. 修改密码

```bash
POST /api/auth/change-password
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "old_password": "oldpass123",
  "new_password": "newpass456"
}
```

### 7. 获取所有用户（管理员权限）

```bash
GET /api/auth/users?skip=0&limit=100
Authorization: Bearer {admin_access_token}
```

### 8. 获取指定用户信息（管理员权限）

```bash
GET /api/auth/users/{user_id}
Authorization: Bearer {admin_access_token}
```

### 9. 更新指定用户（管理员权限）

```bash
PUT /api/auth/users/{user_id}
Authorization: Bearer {admin_access_token}
Content-Type: application/json

{
  "email": "updated@example.com",
  "full_name": "更新后的全名",
  "role": "user"
}
```

### 10. 删除用户（管理员权限）

```bash
DELETE /api/auth/users/{user_id}
Authorization: Bearer {admin_access_token}
```

## 使用示例

### Python客户端示例

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. 登录获取令牌
login_data = {
    "username": "admin",
    "password": "admin123"
}
response = requests.post(f"{BASE_URL}/api/auth/login/json", json=login_data)
result = response.json()
token = result['access_token']

# 2. 使用令牌访问受保护的API
headers = {
    "Authorization": f"Bearer {token}"
}
response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
print(response.json())
```

### JavaScript客户端示例

```javascript
const BASE_URL = "http://localhost:8000";

// 1. 登录获取令牌
async function login() {
  const response = await fetch(`${BASE_URL}/api/auth/login/json`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: 'admin',
      password: 'admin123',
    }),
  });

  const data = await response.json();
  return data.access_token;
}

// 2. 使用令牌访问受保护的API
async function getUserInfo(token) {
  const response = await fetch(`${BASE_URL}/api/auth/me`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  return await response.json();
}

// 使用示例
login().then(token => {
  return getUserInfo(token);
}).then(userInfo => {
  console.log(userInfo);
});
```

## 保护API端点

在API路由中添加认证依赖：

```python
from fastapi import Depends
from app.core.dependencies import get_current_active_user, get_current_admin_user
from app.models.user import User

# 需要登录的接口
@app.get("/api/protected")
async def protected_route(current_user: User = Depends(get_current_active_user)):
    return {"message": "这是受保护的内容", "user": current_user.username}

# 需要管理员权限的接口
@app.get("/api/admin")
async def admin_route(current_user: User = Depends(get_current_admin_user)):
    return {"message": "这是管理员接口", "user": current_user.username}
```

## 配置说明

在 `.env` 文件中配置JWT相关参数：

```env
# JWT认证配置
SECRET_KEY=your-secret-key-change-this-in-production-environment
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**重要提示**：
- 在生产环境中，请务必修改 `SECRET_KEY` 为一个强随机字符串
- 可以使用以下命令生成随机密钥：
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

## 初始化数据库

运行以下命令初始化认证数据库并创建默认用户：

```bash
cd backend
python scripts/init_auth_db.py
```

默认账户：
- **管理员**：
  - 用户名：`admin`
  - 密码：`admin123`
  - 邮箱：`admin@example.com`

- **测试用户**：
  - 用户名：`testuser`
  - 密码：`test123`
  - 邮箱：`test@example.com`

**安全警告**：在生产环境中请立即修改默认密码！

## 测试认证功能

运行测试脚本验证认证系统是否正常工作：

```bash
# 1. 启动后端服务器
cd backend
python -m uvicorn app.main:app --reload

# 2. 在另一个终端运行测试脚本
python scripts/test_auth.py
```

## 数据验证

所有输入参数都经过Pydantic验证：
- 用户名：3-50字符，仅字母数字
- 邮箱：有效的邮箱格式
- 密码：最少6位

## 错误处理

系统返回标准化的错误响应：

```json
{
  "detail": "错误描述信息"
}
```

常见错误码：
- `400 Bad Request`：请求参数错误
- `401 Unauthorized`：未提供令牌或令牌无效
- `403 Forbidden`：权限不足
- `404 Not Found`：资源不存在
- `422 Unprocessable Entity`：数据验证失败

## 安全建议

1. **生产环境配置**：
   - 修改默认的 `SECRET_KEY`
   - 修改默认管理员密码
   - 启用HTTPS

2. **令牌管理**：
   - 访问令牌过期时间建议设置为30分钟
   - 刷新令牌过期时间建议设置为7天
   - 在前端妥善存储令牌（推荐使用HttpOnly Cookie）

3. **密码策略**：
   - 要求使用强密码
   - 实施密码复杂度检查
   - 定期要求用户修改密码

## 扩展功能

可以进一步扩展的功能：
- 邮箱验证
- 密码重置（通过邮件）
- 二次认证（2FA）
- 登录历史记录
- 令牌黑名单
- 社交登录集成
