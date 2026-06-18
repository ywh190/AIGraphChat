#!/usr/bin/env python3
"""
导入中成药数据 V3
简化版本
"""
import sys
from pathlib import Path
import pandas as pd

backend_dir = Path(__file__).parent.parent
root_dir = backend_dir.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir)).
    .
    .

from app.db.session import engine, SessionLocal
from app.models.models import Base, Medic
from sqlalchemy.exc import IntegrityError


def import_medics():
    """导入中成药数据"""
    print("\n" + "=" * 70)
    print("导入中成药数据")
    print("=" * 70)

    # 文件路径
    medic_file = root_dir / "中成药数据_含君臣佐使.csv"

    # 检查文件是否存在
    if not medic_file.exists():
        print(f"\n[ERROR] 文件不存在: {medic_file}")
        return

    try:
        # 创建表（先删除旧表以确保结构最新）
        print("\n[1/4] 创建表...")
        try:
            Medic.__table__.drop(engine, checkfirst=True)
            print("[INFO] 已删除旧表")
        except Exception as e:
            print(f"[INFO] 删除旧表失败（可能不存在）: {e}")
        Base.metadata.create_all(bind=engine)
        print("[OK] 表创建完成")

        # 读取CSV
        print("\n[2/4] 读取CSV文件...")
        df = pd.read_csv(medic_file, encoding='utf-8')

        print(f"[INFO] CSV包含 {len(df)} 条记录，{len(df.columns)} 列")
        print(f"[INFO] 列名: {list(df.columns)[:10]}...")

        # 转换为字典列表
        medic_data = df.to_dict('records')

        # 创建数据库会话
        db = SessionLocal()

        # 检查是否已有数据
        existing_count = db.query(Medic).count()

        if existing_count > 0:
            print(f"\n[WARN] 数据库中已有 {existing_count} 条中成药记录")
            choice = input("是否清空旧数据并重新导入？(yes/no): ").strip().lower()
            if choice == 'yes':
                print("\n[3/4] 清空旧数据...")
                db.query(Medic).delete()
                db.commit()
                print("[OK] 旧数据已清空")
            else:
                print("\n[INFO] 跳过导入")
                return

        # 导入数据
        print(f"\n[4/4] 开始导入 {len(medic_data)} 条记录...")

        imported_count = 0
        skipped_count = 0
        error_count = 0
        seen_names = set()  # 跟踪本次导入已处理的名称

        for i, item in enumerate(medic_data, 1):
            try:
                # 提取中成药信息
                chinese_name = str(item.get('中文名称', '')).strip()
                english_name = str(item.get('英文名称', '')).strip() if pd.notna(item.get('英文名称', '')) else ''
                category = str(item.get('科室类别', '')).strip() if pd.notna(item.get('科室类别', '')) else ''
                main_category = str(item.get('大类', '')).strip() if pd.notna(item.get('大类', '')) else ''
                sub_category = str(item.get('小类', '')).strip() if pd.notna(item.get('小类', '')) else ''

                composition = str(item.get('药物组成', '')) if pd.notna(item.get('药物组成', '')) else ''
                function_indication = str(item.get('功能与主治', '')) if pd.notna(item.get('功能与主治', '')) else ''
                analysis = str(item.get('方解', '')) if pd.notna(item.get('方解', '')) else ''
                clinical_application = str(item.get('临床应用', '')) if pd.notna(item.get('临床应用', '')) else ''
                side_effects = str(item.get('不良反应', '')) if pd.notna(item.get('不良反应', '')) else ''
                contraindications = str(item.get('禁忌', '')) if pd.notna(item.get('禁忌', '')) else ''
                precautions = str(item.get('注意事项', '')) if pd.notna(item.get('注意事项', '')) else ''
                usage_dosage = str(item.get('用法与用量', '')) if pd.notna(item.get('用法与用量', '')) else ''
                specification = str(item.get('规格', '')) if pd.notna(item.get('规格', '')) else ''
                pharmacology = str(item.get('药理毒理', '')) if pd.notna(item.get('药理毒理', '')) else ''
                references = str(item.get('参考文献', '')) if pd.notna(item.get('参考文献', '')) else ''
                monarch_ministers_assistants_couriers = str(item.get('君臣佐使', '')) if pd.notna(item.get('君臣佐使', '')) else ''
                data_source = str(item.get('数据来源', '中国药典')).strip() if pd.notna(item.get('数据来源', '')) else '中国药典'

                # 检查名称是否为空
                if not chinese_name:
                    error_count += 1
                    continue

                # 检查是否已处理过（去重）
                if chinese_name in seen_names:
                    skipped_count += 1
                    continue

                # 检查数据库中是否已存在
                existing = db.query(Medic).filter(
                    Medic.name == chinese_name
                ).first()
                if existing:
                    seen_names.add(chinese_name)
                    skipped_count += 1
                    continue

                # 创建记录
                medic = Medic(
                    name=chinese_name,
                    english_name=english_name,
                    category=category,
                    main_category=main_category,
                    sub_category=sub_category,
                    composition=composition,
                    function_indication=function_indication,
                    analysis=analysis,
                    clinical_application=clinical_application,
                    side_effects=side_effects,
                    contraindications=contraindications,
                    precautions=precautions,
                    usage_dosage=usage_dosage,
                    specification=specification,
                    pharmacology=pharmacology,
                    references=references,
                    monarch_ministers_assistants_couriers=monarch_ministers_assistants_couriers,
                    source=data_source
                )

                db.add(medic)
                seen_names.add(chinese_name)
                imported_count += 1

                # 每500条提交一次
                if imported_count % 500 == 0:
                    try:
                        db.commit()
                        print(f"[PROGRESS] 已导入 {imported_count}/{len(medic_data)} 条")
                    except IntegrityError:
                        db.rollback()
                        print(f"[WARN] 批量提交时遇到重复，已回滚")

            except IntegrityError:
                # 捕获重复键错误
                db.rollback()
                skipped_count += 1
            except Exception as e:
                print(f"[ERROR] 导入第 {i} 条失败: {e}")
                error_count += 1
                db.rollback()

        # 最后提交
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print(f"[WARN] 最终提交时遇到重复记录")

        # 统计信息
        print(f"\n[OK] 导入完成")
        print(f"  成功: {imported_count} 条")
        print(f"  跳过(重复/已存在): {skipped_count} 条")
        print(f"  错误: {error_count} 条")
        print(f"  数据库现有: {db.query(Medic).count()} 条")

        db.close()

    except Exception as e:
        print(f"\n[ERROR] 导入失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import_medics()
