#!/usr/bin/env python3
"""
建立方剂-药材关联关系
从composition字段中解析药材名称，匹配herbs表，创建关联表记录
"""
import sys
from pathlib import Path
import json
import re

backend_dir = Path(__file__).parent.parent
root_dir = backend_dir.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import engine, SessionLocal
from app.models.models import Base, Prescription, Herb, prescription_herb_association
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


def build_prescription_herb_relationships():
    """建立方剂-药材关联关系"""
    print("\n" + "=" * 70)
    print("建立方剂-药材关联关系")
    print("=" * 70)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 清空现有关联关系
        print("\n[1/4] 清空现有关联关系...")
        session.execute(text("DELETE FROM prescription_herbs"))
        session.commit()
        print("[OK] 已清空")

        # 查询所有方剂
        print("\n[2/4] 查询方剂数据...")
        prescriptions = session.query(Prescription).all()
        print(f"[INFO] 找到 {len(prescriptions)} 条方剂")

        # 查询所有药材，建立名称到ID的映射
        print("\n[3/4] 构建药材名称映射...")
        herbs = session.query(Herb).all()
        herb_name_map = {}
        for herb in herbs:
            herb_name_map[herb.name.strip()] = herb.id
            # 添加别名映射
            if herb.aliases:
                for alias in herb.aliases.split('、'):
                    alias = alias.strip()
                    if alias:
                        herb_name_map[alias] = herb.id

        print(f"[INFO] 药材映射表包含 {len(herb_name_map)} 个名称/别名")

        # 正则表达式匹配药材名称（支持中文药材名）
        # 常见药材名模式：2-6个中文字符
        herb_pattern = re.compile(r'[\u4e00-\u9fa5]{2,6}')

        # 建立关联关系
        print("\n[4/4] 建立关联关系...")
        success_count = 0
        error_count = 0

        for i, prescription in enumerate(prescriptions, 1):
            try:
                composition = prescription.composition or ""
                if not composition.strip():
                    continue

                # 从组成中提取药材名称
                herbs_in_composition = set()
                matches = herb_pattern.findall(composition)

                for herb_name in matches:
                    if herb_name in herb_name_map:
                        herbs_in_composition.add(herb_name_map[herb_name])

                # 创建关联关系
                for herb_id in herbs_in_composition:
                    insert_stmt = text("""
                        INSERT INTO prescription_herbs
                        (prescription_id, herb_id, created_at)
                        VALUES (:prescription_id, :herb_id, NOW())
                    """)
                    session.execute(insert_stmt, {
                        'prescription_id': prescription.id,
                        'herb_id': herb_id
                    })

                success_count += len(herbs_in_composition)

                if i % 1000 == 0:
                    session.commit()
                    print(f"[PROGRESS] 已处理 {i}/{len(prescriptions)} 条方剂，已建立 {success_count} 个关联")

            except Exception as e:
                error_count += 1
                print(f"[ERROR] 处理方剂 {prescription.name} 失败: {e}")
                session.rollback()

        # 最后提交
        session.commit()

        # 统计结果
        total_relationships = session.execute(text("SELECT COUNT(*) FROM prescription_herbs")).scalar()
        print(f"\n[OK] 关联建立完成")
        print(f"  方剂总数: {len(prescriptions)}")
        print(f"  建立关联数: {success_count}")
        print(f"  失败数: {error_count}")
        print(f"  数据库中的关系总数: {total_relationships}")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] 建立关联关系失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    build_prescription_herb_relationships()
