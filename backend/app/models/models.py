"""
新版本数据库模型
基于完整的数据分析重新设计
"""
import enum
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Table, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime

# 导入统一的Base
from app.db.session import Base


# 枚举类型
class DataSource(str, enum.Enum):
    """数据来源枚举"""
    HERB_DATA = 'herb_data'          # 药材数据
    PRESCRIPTION = 'prescription'       # 中药方剂数据
    MEDIC = 'medic'                   # 中成药数据


class UserRole(str, enum.Enum):
    """用户角色枚举"""
    ADMIN = 'admin'
    USER = 'user'


# ========== 关联表 ==========

# 方剂-药材关联表
prescription_herb_association = Table(
    'prescription_herbs', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('prescription_id', Integer, ForeignKey('prescriptions.id', ondelete='CASCADE')),
    Column('herb_id', Integer, ForeignKey('herbs.id', ondelete='CASCADE')),
    Column('role_id', Integer, ForeignKey('prescription_roles.id', ondelete='SET NULL')),
    Column('dosage', String(100), comment='用量'),
    Column('created_at', DateTime, default=datetime.utcnow),
    comment='方剂-药材关联表'
)

# 中成药-药材关联表
medic_herb_association = Table(
    'medic_herbs', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('medic_id', Integer, ForeignKey('medics.id', ondelete='CASCADE')),
    Column('herb_id', Integer, ForeignKey('herbs.id', ondelete='CASCADE')),
    Column('role_id', Integer, ForeignKey('prescription_roles.id', ondelete='SET NULL')),
    Column('dosage', String(100), comment='用量'),
    Column('created_at', DateTime, default=datetime.utcnow),
    comment='中成药-药材关联表'
)

# 药材-功效关联表
herb_efficacy_association = Table(
    'herb_efficacies', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('herb_id', Integer, ForeignKey('herbs.id', ondelete='CASCADE')),
    Column('efficacy_id', Integer, ForeignKey('efficacies.id', ondelete='CASCADE')),
    Column('created_at', DateTime, default=datetime.utcnow),
    comment='药材-功效关联表',
    mysql_engine='InnoDB',
    mysql_charset='utf8mb4'
)

# 药材-性味关联表
herb_nature_association = Table(
    'herb_natures', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('herb_id', Integer, ForeignKey('herbs.id', ondelete='CASCADE')),
    Column('nature_id', Integer, ForeignKey('natures.id', ondelete='CASCADE')),
    Column('created_at', DateTime, default=datetime.utcnow),
    comment='药材-性味关联表',
    mysql_engine='InnoDB',
    mysql_charset='utf8mb4'
)

# 药材-归经关联表
herb_meridian_association = Table(
    'herb_meridians', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('herb_id', Integer, ForeignKey('herbs.id', ondelete='CASCADE')),
    Column('meridian_id', Integer, ForeignKey('meridians.id', ondelete='CASCADE')),
    Column('created_at', DateTime, default=datetime.utcnow),
    comment='药材-归经关联表',
    mysql_engine='InnoDB',
    mysql_charset='utf8mb4'
)

# ========== 核心实体表 ==========

# 注意：User 模型已移至 app.models.user

class Medic(Base):
    """中成药表"""
    __tablename__ = "medics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, index=True, nullable=False, comment='中文名称')
    english_name = Column(String(200), comment='英文名称')
    category = Column(String(100), index=True, comment='科室类别')
    main_category = Column(String(100), index=True, comment='大类')
    sub_category = Column(String(100), comment='小类')
    composition = Column(Text, comment='药物组成')
    function_indication = Column(Text, comment='功能与主治')
    analysis = Column(Text, comment='方解')
    clinical_application = Column(Text, comment='临床应用')
    side_effects = Column(Text, comment='不良反应')
    contraindications = Column(Text, comment='禁忌')
    precautions = Column(Text, comment='注意事项')
    usage_dosage = Column(Text, comment='用法与用量')
    specification = Column(Text, comment='规格')
    pharmacology = Column(Text, comment='药理毒理')
    references = Column(Text, comment='参考文献')
    monarch_ministers_assistants_couriers = Column(Text, comment='君臣佐使')
    source = Column(String(500), comment='数据来源')

    # 软删除字段
    is_deleted = Column(Integer, default=0, comment='是否删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关系
    herbs = relationship("Herb", secondary=medic_herb_association, back_populates="medics")

    def __repr__(self):
        return f"<Medic(id={self.id}, name='{self.name}')>"


class Herb(Base):
    """药材表 - 基于实际数据结构重新设计，包含所有字段"""
    __tablename__ = "herbs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, index=True, nullable=False, comment='药材名称')
    pinyin = Column(String(200), comment='拼音注音')
    aliases = Column(Text, comment='别名')
    english_name = Column(String(200), comment='英文名')
    source = Column(String(500), comment='药材基源')
    source_text = Column(Text, comment='出处')
    habitat = Column(Text, comment='生境分布')
    original_morphology = Column(Text, comment='原形态')
    properties = Column(Text, comment='性状')
    chemical_composition = Column(Text, comment='化学成分')
    meridians = Column(String(200), comment='归经')
    nature = Column(String(100), index=True, comment='性味')
    function = Column(Text, comment='功能主治')
    usage = Column(Text, comment='用法用量')
    discussions = Column(Text, comment='各家论述')
    excerpt = Column(Text, comment='摘录')
    harvest_storage = Column(Text, comment='采收和储藏')
    processing = Column(Text, comment='炮制')
    clinical_application = Column(Text, comment='临床应用')
    storage = Column(Text, comment='贮藏')
    identification = Column(Text, comment='鉴别')
    pharmacological_effects = Column(Text, comment='药理作用')
    link = Column(String(500), comment='数据来源链接')

    # 软删除字段
    is_deleted = Column(Integer, default=0, comment='是否删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关系
    efficacies = relationship("Efficacy", secondary=herb_efficacy_association, back_populates="herbs")
    prescriptions = relationship("Prescription", secondary=prescription_herb_association, back_populates="herbs")
    medics = relationship("Medic", secondary=medic_herb_association, back_populates="herbs")

    def __repr__(self):
        return f"<Herb(id={self.id}, name='{self.name}')>"


class Prescription(Base):
    """中药方剂表"""
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, index=True, nullable=False, comment='方剂名称')
    composition = Column(Text, comment='方剂组成')
    function_indication = Column(Text, comment='功能主治')
    usage_dosage = Column(Text, comment='用法用量')
    source = Column(String(500), comment='数据来源')

    # 软删除字段
    is_deleted = Column(Integer, default=0, comment='是否删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关系
    herbs = relationship("Herb", secondary=prescription_herb_association, back_populates="prescriptions")

    def __repr__(self):
        return f"<Prescription(id={self.id}, name='{self.name}')>"


class PrescriptionRole(Base):
    """君臣佐使角色表"""
    __tablename__ = "prescription_roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, comment='角色名称')
    description = Column(Text, comment='角色描述')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')

    def __repr__(self):
        return f"<PrescriptionRole(id={self.id}, name='{self.name}')>"


class Efficacy(Base):
    """功效表"""
    __tablename__ = "efficacies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False, comment='功效名称')
    description = Column(Text, comment='功效描述')

    # 软删除字段
    is_deleted = Column(Integer, default=0, comment='是否删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')

    # 关系
    herbs = relationship("Herb", secondary=herb_efficacy_association, back_populates="efficacies")

    def __repr__(self):
        return f"<Efficacy(id={self.id}, name='{self.name}')>"


class Nature(Base):
    """性味表"""
    __tablename__ = "natures"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False, comment='性味名称')
    description = Column(Text, comment='性味描述')

    # 软删除字段
    is_deleted = Column(Integer, default=0, comment='是否删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')

    # 关系
    herbs = relationship("Herb", secondary=herb_nature_association, back_populates="natures")

    def __repr__(self):
        return f"<Nature(id={self.id}, name='{self.name}')>"


class Meridian(Base):
    """归经表"""
    __tablename__ = "meridians"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False, comment='归经名称')
    description = Column(Text, comment='归经描述')

    # 软删除字段
    is_deleted = Column(Integer, default=0, comment='是否删除')
    deleted_at = Column(DateTime, nullable=True, comment='删除时间')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')

    # 关系
    herbs = relationship("Herb", secondary=herb_meridian_association, back_populates="meridians")

    def __repr__(self):
        return f"<Meridian(id={self.id}, name='{self.name}')>"


# 添加反向关系到Herb
Herb.prescriptions = relationship("Prescription", secondary=prescription_herb_association, back_populates="herbs")
Herb.medics = relationship("Medic", secondary=medic_herb_association, back_populates="herbs")
Herb.natures = relationship("Nature", secondary=herb_nature_association, back_populates="herbs")
Herb.meridians = relationship("Meridian", secondary=herb_meridian_association, back_populates="herbs")