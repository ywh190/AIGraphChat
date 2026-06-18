"""
处方相关的Pydantic验证模型
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from .herb import HerbResponse


class PrescriptionBase(BaseModel):
    """处方基础模型"""
    name: str = Field(..., min_length=1, max_length=200, description="方剂名称")
    composition: Optional[str] = Field(None, description="方剂组成")
    function_indication: Optional[str] = Field(None, description="功能主治")
    usage_dosage: Optional[str] = Field(None, description="用法用量")
    source: Optional[str] = Field(None, max_length=500, description="数据来源")

    @validator('name')
    def name_not_empty(cls, v):
        if not v or v.strip() == '':
            raise ValueError('方剂名称不能为空')
        return v.strip()


class PrescriptionCreate(PrescriptionBase):
    """处方创建模型"""
    pass


class PrescriptionUpdate(BaseModel):
    """处方更新模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    composition: Optional[str] = None
    function_indication: Optional[str] = None
    usage_dosage: Optional[str] = None
    source: Optional[str] = Field(None, max_length=500)


class PrescriptionResponse(PrescriptionBase):
    """处方响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    herbs: List[HerbResponse] = []  # 注意：需要导入HerbResponse，但这里使用字符串引用避免循环导入

    class Config:
        from_attributes = True


class PrescriptionListResponse(BaseModel):
    """处方列表响应模型"""
    total: int = Field(..., description="总数")
    skip: int = Field(..., description="跳过数量")
    limit: int = Field(..., description="限制数量")
    items: List[PrescriptionResponse] = Field(..., description="处方列表")


class PrescriptionSearchRequest(BaseModel):
    """处方搜索请求模型"""
    keyword: Optional[str] = Field(None, description="搜索关键词")
    search_type: Optional[str] = Field(None, description="搜索类型: name-名称, composition-组成, function-功效, all-全部")
    skip: int = Field(0, ge=0, description="跳过数量")
    limit: int = Field(100, ge=1, le=1000, description="限制数量")

    @validator('limit')
    def validate_limit(cls, v):
        if v > 1000:
            raise ValueError('每页最多返回1000条记录')
        return v
