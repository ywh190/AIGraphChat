from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime

class HerbBase(BaseModel):
    name: str
    pinyin: Optional[str] = None
    aliases: Optional[str] = None
    english_name: Optional[str] = None
    source: Optional[str] = None
    source_text: Optional[str] = None
    habitat: Optional[str] = None
    original_morphology: Optional[str] = None
    properties: Optional[str] = None
    chemical_composition: Optional[str] = None
    meridians: Optional[str] = None
    nature: Optional[str] = None
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
    link: Optional[str] = None

class HerbCreate(HerbBase):
    pass

class Herb(HerbBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class EfficacyBase(BaseModel):
    name: str
    description: Optional[str] = None

class EfficacyCreate(EfficacyBase):
    pass

class Efficacy(EfficacyBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class PrescriptionBase(BaseModel):
    name: str
    composition: Optional[str] = None
    function_indication: Optional[str] = None
    usage_dosage: Optional[str] = None
    source: Optional[str] = None

class PrescriptionCreate(PrescriptionBase):
    pass

class Prescription(PrescriptionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    herbs: List[Herb] = []

    class Config:
        orm_mode = True

class SearchQuery(BaseModel):
    query: str
    limit: int = 10

class RAGQuery(BaseModel):
    """AI问答请求模型"""
    question: Optional[str] = None
    message: Optional[str] = None
    context: Optional[str] = None
    
    def get_question(self) -> str:
        """获取问题文本，优先使用question，其次使用message"""
        if self.question:
            return self.question
        elif self.message:
            return self.message
        else:
            raise ValueError("必须提供question或message字段")

class ChatRequest(BaseModel):
    """AI聊天请求模型（包含会话ID）"""
    message: str
    session_id: Optional[str] = None

class KnowledgeGraphQuery(BaseModel):
    node_type: str  # herb, prescription, efficacy
    node_id: int
    depth: int = 2

class MedicBase(BaseModel):
    """中成药基础模型"""
    name: str = Field(..., min_length=1, max_length=200, description="中文名称")
    english_name: Optional[str] = Field(None, max_length=200, description="英文名称")
    category: Optional[str] = Field(None, max_length=100, description="科室类别")
    main_category: Optional[str] = Field(None, max_length=100, description="大类")
    sub_category: Optional[str] = Field(None, max_length=100, description="小类")
    composition: Optional[str] = Field(None, description="药物组成")
    function_indication: Optional[str] = Field(None, description="功能与主治")
    analysis: Optional[str] = Field(None, description="方解")
    clinical_application: Optional[str] = Field(None, description="临床应用")
    side_effects: Optional[str] = Field(None, description="不良反应")
    contraindications: Optional[str] = Field(None, description="禁忌")
    precautions: Optional[str] = Field(None, description="注意事项")
    usage_dosage: Optional[str] = Field(None, description="用法与用量")
    specification: Optional[str] = Field(None, description="规格")
    pharmacology: Optional[str] = Field(None, description="药理毒理")
    references: Optional[str] = Field(None, description="参考文献")
    monarch_ministers_assistants_couriers: Optional[str] = Field(None, description="君臣佐使")
    source: Optional[str] = Field(None, max_length=500, description="数据来源")

    @validator('name')
    def name_not_empty(cls, v):
        if not v or v.strip() == '':
            raise ValueError('中成药名称不能为空')
        return v.strip()

class MedicCreate(MedicBase):
    """中成药创建模型"""
    pass

class MedicUpdate(BaseModel):
    """中成药更新模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    english_name: Optional[str] = None
    category: Optional[str] = None
    main_category: Optional[str] = None
    sub_category: Optional[str] = None
    composition: Optional[str] = None
    function_indication: Optional[str] = None
    analysis: Optional[str] = None
    clinical_application: Optional[str] = None
    side_effects: Optional[str] = None
    contraindications: Optional[str] = None
    precautions: Optional[str] = None
    usage_dosage: Optional[str] = None
    specification: Optional[str] = None
    pharmacology: Optional[str] = None
    references: Optional[str] = None
    monarch_ministers_assistants_couriers: Optional[str] = None
    source: Optional[str] = Field(None, max_length=500)

class Medic(MedicBase):
    """中成药响应模型"""
    id: int
    is_deleted: Optional[int] = 0
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MedicListResponse(BaseModel):
    """中成药列表响应模型"""
    total: int
    skip: int
    limit: int
    items: List[Medic]

class MedicSearchRequest(BaseModel):
    """中成药搜索请求模型"""
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    search_type: Optional[str] = Field(None, description="搜索类型: name-名称, composition-组成, function-功效, all-全部")
    category: Optional[str] = Field(None, description="科室类别")
    main_category: Optional[str] = Field(None, description="大类")
    sub_category: Optional[str] = Field(None, description="小类")
    skip: int = Field(0, ge=0, description="跳过数量")
    limit: int = Field(10, ge=1, le=1000, description="限制数量")

# AI服务相关Schema
class GenerateExplanationRequest(BaseModel):
    """生成解释请求模型"""
    content_type: str = Field(..., description="内容类型: herb-药材, prescription-方剂, medic-中成药")
    content: str = Field(..., min_length=1, description="要解释的内容")

class RecommendPrescriptionsRequest(BaseModel):
    """推荐方剂请求模型"""
    symptoms: str = Field(..., min_length=1, description="症状描述")

class AnalyzeCompositionRequest(BaseModel):
    """分析组成请求模型"""
    composition: str = Field(..., min_length=1, description="方剂组成")
