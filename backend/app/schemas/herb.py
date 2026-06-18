"""
药材相关的Pydantic验证模型
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union, Any
from datetime import datetime


class HerbBase(BaseModel):
    """药材基础模型"""
    name: str = Field(..., min_length=1, max_length=200, description="药材名称")
    pinyin: Optional[str] = Field(None, max_length=200, description="拼音注音")
    aliases: Optional[str] = Field(None, description="别名")
    english_name: Optional[str] = Field(None, max_length=200, description="英文名")
    source: Optional[str] = Field(None, max_length=500, description="药材基源")
    source_text: Optional[str] = Field(None, description="出处")
    habitat: Optional[str] = Field(None, description="生境分布")
    original_morphology: Optional[str] = Field(None, description="原形态")
    properties: Optional[str] = Field(None, description="性状")
    chemical_composition: Optional[str] = Field(None, description="化学成分")
    meridians: Optional[Union[str, List[Any]]] = Field(None, max_length=200, description="归经")
    nature: Optional[str] = Field(None, max_length=100, description="性味")
    function: Optional[str] = Field(None, description="功能主治")
    usage: Optional[str] = Field(None, description="用法用量")
    discussions: Optional[str] = Field(None, description="各家论述")
    excerpt: Optional[str] = Field(None, description="摘录")
    harvest_storage: Optional[str] = Field(None, description="采收和储藏")
    processing: Optional[str] = Field(None, description="炮制")
    clinical_application: Optional[str] = Field(None, description="临床应用")
    storage: Optional[str] = Field(None, description="贮藏")
    identification: Optional[str] = Field(None, description="鉴别")
    pharmacological_effects: Optional[str] = Field(None, description="药理作用")
    link: Optional[str] = Field(None, max_length=500, description="数据来源链接")

    @validator('name')
    def name_not_empty(cls, v):
        if not v or v.strip() == '':
            raise ValueError('药材名称不能为空')
        return v.strip()


class HerbCreate(HerbBase):
    """药材创建模型"""
    pass


class HerbUpdate(BaseModel):
    """药材更新模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    pinyin: Optional[str] = Field(None, max_length=200)
    aliases: Optional[str] = None
    english_name: Optional[str] = Field(None, max_length=200)
    source: Optional[str] = Field(None, max_length=500)
    source_text: Optional[str] = None
    habitat: Optional[str] = None
    original_morphology: Optional[str] = None
    properties: Optional[str] = None
    chemical_composition: Optional[str] = None
    meridians: Optional[Union[str, List[Any]]] = Field(None, max_length=200)
    nature: Optional[str] = Field(None, max_length=100)
    function: Optional[str] = None
    usage: Optional[str] = None
    discussions: Optional[str] = None
    excerpt: Optional[str] = None
    harvest_storage: Optional[str] = None
    processing: Optional[str] = None
    clinical_application: Optional[str] = None
    storage: Optional[str] = None
    identification: Optional[str] = None
    pharmacological_effects: Optional[str] = None
    link: Optional[str] = Field(None, max_length=500)


class HerbResponse(HerbBase):
    """药材响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    @validator('meridians', pre=True)
    def convert_meridians(cls, v):
        if isinstance(v, list):
            # 将Meridian对象列表转换为逗号分隔的名称字符串
            names = []
            for item in v:
                if hasattr(item, 'name'):
                    names.append(item.name)
                elif isinstance(item, dict) and 'name' in item:
                    names.append(item['name'])
                elif isinstance(item, str):
                    names.append(item)
            return ', '.join(names) if names else None
        return v

    class Config:
        from_attributes = True


class HerbListResponse(BaseModel):
    """药材列表响应模型"""
    total: int = Field(..., description="总数")
    skip: int = Field(..., description="跳过数量")
    limit: int = Field(..., description="限制数量")
    items: List[HerbResponse] = Field(..., description="药材列表")


class HerbSearchRequest(BaseModel):
    """药材搜索请求模型"""
    keyword: Optional[str] = Field(None, description="搜索关键词")
    search_type: Optional[str] = Field(None, description="搜索类型: name-名称, function-功效, nature-性味, all-全部")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    nature: Optional[str] = Field(None, max_length=100, description="性味")
    skip: int = Field(0, ge=0, description="跳过数量")
    limit: int = Field(100, ge=1, le=1000, description="限制数量")

    @validator('limit')
    def validate_limit(cls, v):
        if v > 1000:
            raise ValueError('每页最多返回1000条记录')
        return v
