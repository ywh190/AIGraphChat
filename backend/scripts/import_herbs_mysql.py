#!/usr/bin/env python3
"""
导入药材数据 V3
简化版本，专注于成功导入
"""
import sys
from pathlib import Path
import json

backend_dir = Path(__file__).parent.parent
root_dir = backend_dir.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import engine, SessionLocal
from app.models.models import Base, Herb
from sqlalchemy.exc import IntegrityError
import inspect


def import_herbs():
    """导入药材数据"""
    print("\n" + "=" * 70)
    print("导入药材数据")
    print("=" * 70)

    # 文件路径
    herb_file = root_dir / "药材数据.json"

    # 检查文件是否存在
    if not herb_file.exists():
        print(f"\n[ERROR] 文件不存在: {herb_file}")
        return

    try:
        # 创建表（先删除旧表以确保结构最新）
        print("\n[1/4] 创建表...")
        try:
            Herb.__table__.drop(engine, checkfirst=True)
            print("[INFO] 已删除旧表")
        except Exception as e:
            print(f"[INFO] 删除旧表失败（可能不存在）: {e}")
        Base.metadata.create_all(bind=engine)
        print("[OK] 表创建完成")

        # 读取数据
        print("\n[2/4] 读取数据文件...")
        with open(herb_file, 'r', encoding='utf-8') as f:
            herb_data = json.load(f)

        print(f"[INFO] 找到 {len(herb_data)} 条药材记录")
        
        # 调试：打印第一条记录的键和部分值
        if herb_data:
            first_item = herb_data[0]
            print(f"[DEBUG] 第一条记录键名: {list(first_item.keys())}")
            print(f"[DEBUG] '药材名称' 字段值: '{first_item.get('药材名称', '')}'")
            print(f"[DEBUG] '来源信息' 类型: {type(first_item.get('来源信息'))}")
            if isinstance(first_item.get('来源信息'), dict):
                print(f"[DEBUG] '来源信息' 键名: {list(first_item.get('来源信息').keys())}")
            elif isinstance(first_item.get('来源信息'), list):
                print(f"[DEBUG] '来源信息' 列表长度: {len(first_item.get('来源信息'))}")
                if first_item.get('来源信息'):
                    print(f"[DEBUG] 列表第一个元素类型: {type(first_item.get('来源信息')[0])}")

        # 创建数据库会话
        db = SessionLocal()

        # 检查是否已有数据
        existing_count = db.query(Herb).count()
        if existing_count > 0:
            print(f"\n[WARN] 数据库中已有 {existing_count} 条药材记录")
            # 自动清空旧数据
            choice = 'yes'
            if choice == 'yes':
                print("\n[3/4] 清空旧数据...")
                db.query(Herb).delete()
                db.commit()
                print("[OK] 旧数据已清空")
            else:
                print("\n[INFO] 跳过导入")
                return

        # 导入数据
        print(f"\n[4/4] 开始导入 {len(herb_data)} 条记录...")
        
        # 字段长度限制（根据 v2_models.py 新设计）
        FIELD_LIMITS = {
            'name': 200,      # String(200)
            'pinyin': 200,    # String(200)
            'english_name': 200, # String(200)
            'source': 500,    # String(500)
            'meridians': 200, # String(200)
            'nature': 100,    # String(100)
            'link': 500,      # String(500)
            # Text字段的安全限制（MySQL Text类型最大65,535字节，utf8mb4编码下约16,000字符）
            'aliases': 16000,
            'source_text': 16000,
            'habitat': 16000,
            'original_morphology': 16000,
            'properties': 16000,
            'chemical_composition': 16000,
            'function': 16000,
            'usage': 16000,
            'discussions': 16000,
            'excerpt': 16000,
            'harvest_storage': 16000,
            'processing': 16000,
            'clinical_application': 16000,
            'storage': 16000,
            'identification': 16000,
            'pharmacological_effects': 16000,
        }
        
        def truncate_field(field_name, value, record_index):
            """截断字段值到数据库限制长度"""
            if field_name in FIELD_LIMITS:
                limit = FIELD_LIMITS[field_name]
                if value and len(value) > limit:
                    # 截断并添加省略号
                    truncated = value[:limit-3] + '...' if limit > 3 else value[:limit]
                    print(f"[WARN] 第 {record_index} 条记录 '{field_name}' 字段过长 ({len(value)} > {limit})，已截断")
                    return truncated
            return value

        imported_count = 0
        skipped_count = 0
        error_count = 0
        seen_names = set()  # 跟踪本次导入已处理的名称

        for i, item in enumerate(herb_data, 1):
            try:
                # 提取药材信息
                name = item.get('药材名称', '').strip()
                link = item.get('url', '')
                source_info = item.get('来源信息', {})

                # 提取来源信息 - 处理嵌套结构，提取所有字段
                def extract_herb_info(source_info):
                    """从嵌套的来源信息中提取药材数据，支持字典和列表结构，提取所有字段"""
                    result = {
                        'pinyin': '',
                        'aliases': '',
                        'english_name': '',
                        'source': '',
                        'source_text': '',
                        'habitat': '',
                        'original_morphology': '',
                        'properties': '',
                        'chemical_composition': '',
                        'meridians': '',
                        'nature': '',
                        'function': '',
                        'usage': '',
                        'discussions': '',
                        'excerpt': '',
                        'harvest_storage': '',
                        'processing': '',
                        'clinical_application': '',
                        'storage': '',
                        'identification': '',
                        'pharmacological_effects': ''
                    }

                    # 跳过的键名
                    skip_keys = {'前一个药材', '后一个药材'}
                    
                    # 统一处理：将 source_info 转换为列表
                    items = []
                    if isinstance(source_info, dict):
                        # 如果是字典，将每个键值对作为一项，但跳过 skip_keys
                        for key, value in source_info.items():
                            if isinstance(key, str) and key in skip_keys:
                                continue
                            items.append((key, value))
                    elif isinstance(source_info, list):
                        # 如果是列表，将列表索引作为 source_name
                        for idx, item in enumerate(source_info):
                            items.append((f"source_{idx}", item))
                    else:
                        # 其他类型，直接返回空结果
                        return result
                    
                    # 处理每个数据项
                    for source_name, data in items:
                        if not isinstance(data, dict):
                            continue
                            
                        # 提取所有可能字段
                        field_mapping = {
                            '拼音注音': 'pinyin',
                            '别名': 'aliases',
                            '英文名': 'english_name',
                            '来源': 'source',
                            '出处': 'source_text',
                            '生境分布': 'habitat',
                            '原形态': 'original_morphology',
                            '性状': 'properties',
                            '化学成分': 'chemical_composition',
                            '归经': 'meridians',
                            '性味': 'nature',
                            '功能主治': 'function',
                            '用法用量': 'usage',
                            '各家论述': 'discussions',
                            '摘录': 'excerpt',
                            '采收和储藏': 'harvest_storage',
                            '炮制': 'processing',
                            '临床应用': 'clinical_application',
                            '贮藏': 'storage',
                            '鉴别': 'identification',
                            '药理作用': 'pharmacological_effects'
                        }
                        
                        for data_key, result_key in field_mapping.items():
                            if data.get(data_key) and not result[result_key]:
                                result[result_key] = str(data[data_key])
                        
                        # 如果大部分重要字段都已获取，可以提前退出（避免重复处理）
                        if result['pinyin'] and result['aliases'] and result['nature']:
                            break
                    
                    return result

                herb_info = extract_herb_info(source_info)
                pinyin = herb_info['pinyin']
                aliases = herb_info['aliases']
                english_name = herb_info['english_name']
                source = herb_info['source']
                source_text = herb_info['source_text']
                habitat = herb_info['habitat']
                original_morphology = herb_info['original_morphology']
                properties = herb_info['properties']
                chemical_composition = herb_info['chemical_composition']
                meridians = herb_info['meridians']
                nature = herb_info['nature']
                function = herb_info['function']
                usage = herb_info['usage']
                discussions = herb_info['discussions']
                excerpt = herb_info['excerpt']
                harvest_storage = herb_info['harvest_storage']
                processing = herb_info['processing']
                clinical_application = herb_info['clinical_application']
                storage = herb_info['storage']
                identification = herb_info['identification']
                pharmacological_effects = herb_info['pharmacological_effects']

                # 检查名称是否为空
                if not name:
                    print(f"[WARN] 第 {i} 条记录名称字段为空")
                    error_count += 1
                    continue

                # 检查是否已处理过（去重）
                if name in seen_names:
                    skipped_count += 1
                    continue

                # 检查数据库中是否已存在
                existing = db.query(Herb).filter(Herb.name == name).first()
                if existing:
                    seen_names.add(name)
                    skipped_count += 1
                    continue

                # 截断字段以确保不超过数据库限制
                name = truncate_field('name', name, i)
                pinyin = truncate_field('pinyin', pinyin, i)
                english_name = truncate_field('english_name', english_name, i)
                source = truncate_field('source', source, i)
                meridians = truncate_field('meridians', meridians, i)
                nature = truncate_field('nature', nature, i)
                link = truncate_field('link', link, i)
                # 截断Text字段
                aliases = truncate_field('aliases', aliases, i)
                source_text = truncate_field('source_text', source_text, i)
                habitat = truncate_field('habitat', habitat, i)
                original_morphology = truncate_field('original_morphology', original_morphology, i)
                properties = truncate_field('properties', properties, i)
                chemical_composition = truncate_field('chemical_composition', chemical_composition, i)
                function = truncate_field('function', function, i)
                usage = truncate_field('usage', usage, i)
                discussions = truncate_field('discussions', discussions, i)
                excerpt = truncate_field('excerpt', excerpt, i)
                harvest_storage = truncate_field('harvest_storage', harvest_storage, i)
                processing = truncate_field('processing', processing, i)
                clinical_application = truncate_field('clinical_application', clinical_application, i)
                storage = truncate_field('storage', storage, i)
                identification = truncate_field('identification', identification, i)
                pharmacological_effects = truncate_field('pharmacological_effects', pharmacological_effects, i)

                # 创建记录（包含所有字段）
                herb = Herb(
                    name=name,
                    pinyin=pinyin,
                    aliases=aliases,
                    english_name=english_name,
                    source=source,
                    source_text=source_text,
                    habitat=habitat,
                    original_morphology=original_morphology,
                    properties=properties,
                    chemical_composition=chemical_composition,
                    meridians=meridians,
                    nature=nature,
                    function=function,
                    usage=usage,
                    discussions=discussions,
                    excerpt=excerpt,
                    harvest_storage=harvest_storage,
                    processing=processing,
                    clinical_application=clinical_application,
                    storage=storage,
                    identification=identification,
                    pharmacological_effects=pharmacological_effects,
                    link=link
                )

                db.add(herb)
                seen_names.add(name)
                imported_count += 1

                # 每1000条提交一次
                if imported_count % 1000 == 0:
                    try:
                        db.commit()
                        print(f"[PROGRESS] 已导入 {imported_count}/{len(herb_data)} 条")
                    except IntegrityError as e:
                        db.rollback()
                        print(f"[WARN] 批量提交时遇到重复，已回滚")
                        # 重新添加当前批次到会话
                        pass

            except IntegrityError:
                # 捕获重复键错误
                db.rollback()
                skipped_count += 1
            except Exception as e:
                import traceback
                print(f"[ERROR] 导入第 {i} 条失败: {e}")
                traceback.print_exc()
                error_count += 1
                db.rollback()

        # 最后提交
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            print(f"[WARN] 最终提交时遇到重复记录")

        # 统计信息
        print(f"\n[OK] 导入完成")
        print(f"  成功: {imported_count} 条")
        print(f"  跳过(重复/已存在): {skipped_count} 条")
        print(f"  错误: {error_count} 条")
        print(f"  数据库现有: {db.query(Herb).count()} 条")

        db.close()

    except Exception as e:
        print(f"\n[ERROR] 导入失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import_herbs()
