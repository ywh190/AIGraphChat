"""
通用Pydantic验证模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Generic, TypeVar


class ResponseModel(BaseModel):
    """通用API响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    error: Optional[dict] = Field(None, description="错误详情")


class PaginationParams(BaseModel):
    """分页参数模型"""
    skip: int = Field(0, ge=0, description="跳过数量")
    limit: int = Field(100, ge=1, le=1000, description="限制数量")

    class Config:
        json_schema_extra = {
            "example": {
                "skip": 0,
                "limit": 100
            }
        }


class PaginatedResponse(BaseModel, Generic[TypeVar('T')]):
    """分页响应模型"""
    total: int = Field(..., description="总数")
    skip: int = Field(..., description="跳过数量")
    limit: int = Field(..., description="限制数量")
    items: List[Any] = Field(..., description="数据列表")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 1000,
                "skip": 0,
                "limit": 100,
                "items": []
            }
        }


class BulkDeleteRequest(BaseModel):
    """批量删除请求模型"""
    ids: List[int] = Field(..., min_length=1, description="要删除的ID列表")

    @classmethod
    def validate_ids(cls, v):
        if len(v) > 1000:
            raise ValueError('一次最多删除1000条记录')
        return v


class BulkUpdateRequest(BaseModel):
    """批量更新请求模型"""
    ids: List[int] = Field(..., min_length=1, description="要更新的ID列表")
    updates: dict = Field(..., description="更新内容")

    @classmethod
    def validate_ids(cls, v):
        if len(v) > 1000:
            raise ValueError('一次最多更新1000条记录')
        return v


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    database: dict = Field(..., description="数据库状态")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: dict = Field(..., description="错误详情")

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "输入验证失败",
                    "details": {
                        "field": "username",
                        "reason": "用户名已存在"
                    }
                }
            }
        }
