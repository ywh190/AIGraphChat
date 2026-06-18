#!/usr/bin/env python3
"""
导入中药方剂数据 V3
简化版本
"""
import sys
from pathlib import Path
import json

backend_dir = Path(__file__).parent.parent
root_dir = backend_dir.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import engine, SessionLocal
from app.models.models import Base, Prescription
from sqlalchemy.exc import IntegrityError


def import_prescriptions():
    """导入中药方剂数据"""
    print("\n" + "=" * 70)
    print("导入中药方剂数据")
    print("=" * 70)

    # 文件路径
    prescription_file = root_dir / "中药方剂数据.json"

    # 检查文件是否存在
    if not prescription_file.exists():
        print(f"\n[ERROR] 文件不存在: {prescription_file}")
        return

    try:
        # 创建表（先删除旧表以确保结构最新）
        print("\n[1/4] 创建表...")
        try:
            Prescription.__table__.drop(engine, checkfirst=True)
            print("[INFO] 已删除旧表")
        except Exception as e:
            print(f"[INFO] 删除旧表失败（可能不存在）: {e}")
        Base.metadata.create_all(bind=engine)
        print("[OK] 表创建完成")

        # 读取数据
        print("\n[2/4] 读取数据文件...")
        with open(prescription_file, 'r', encoding='utf-8') as f:
            prescription_data = json.load(f)

        print(f"[INFO] 找到 {len(prescription_data)} 条方剂记录")

        # 创建数据库会话
        db = SessionLocal()

        # 检查是否已有数据
        existing_count = db.query(Prescription).count()

        if existing_count > 0:
            print(f"\n[WARN] 数据库中已有 {existing_count} 条中药方剂记录")
            choice = input("是否清空旧数据并重新导入？(yes/no): ").strip().lower()
            if choice == 'yes':
                print("\n[3/4] 清空旧数据...")
                db.query(Prescription).delete()
                db.commit()
                print("[OK] 旧数据已清空")
            else:
                print("\n[INFO] 跳过导入")
                return

        # 导入数据
        print(f"\n[4/4] 开始导入 {len(prescription_data)} 条记录...")

        imported_count = 0
        skipped_count = 0
        error_count = 0
        seen_names = set()  # 跟踪本次导入已处理的名称

        for i, item in enumerate(prescription_data, 1):
            try:
                # 提取方剂信息
                name = item.get('name', '').strip()
                prescription_text = item.get('prescription', '')
                function = item.get('function', '')
                usage = item.get('usage', '')
                source = item.get('source', '')

                # 检查名称是否为空
                if not name:
                    error_count += 1
                    continue

                # 检查是否已处理过（去重）
                if name in seen_names:
                    skipped_count += 1
                    continue

                # 检查数据库中是否已存在
                existing = db.query(Prescription).filter(
                    Prescription.name == name
                ).first()
                if existing:
                    seen_names.add(name)
                    skipped_count += 1
                    continue

                # 创建记录
                prescription = Prescription(
                    name=name,
                    composition=prescription_text,
                    function_indication=function,
                    usage_dosage=usage,
                    source=source
                )

                db.add(prescription)
                seen_names.add(name)
                imported_count += 1

                # 每1000条提交一次
                if imported_count % 1000 == 0:
                    try:
                        db.commit()
                        print(f"[PROGRESS] 已导入 {imported_count}/{len(prescription_data)} 条")
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
        print(f"  数据库现有: {db.query(Prescription).count()} 条")

        db.close()

    except Exception as e:
        print(f"\n[ERROR] 导入失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import_prescriptions()
