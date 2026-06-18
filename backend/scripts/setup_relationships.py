#!/usr/bin/env python3
"""
完整设置关联关系流程
1. 检查并重建关联表
2. 建立方剂-药材关系
3. 建立中成药-药材关系
4. 同步到Neo4j
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def step1_check_and_recreate_tables():
    """步骤1: 检查并重建关联表"""
    print("\n" + "=" * 70)
    print("步骤 1/4: 检查并重建关联表")
    print("=" * 70)

    from app.db.session import engine
    from app.models.models import Base, prescription_herb_association, medic_herb_association
    from sqlalchemy import text, inspect

    try:
        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"\n当前数据库中的表:")
        for table in ['prescription_herbs', 'medic_herbs']:
            exists = table in tables
            status = "✓ 存在" if exists else "✗ 不存在"
            print(f"  {table}: {status}")

            if exists:
                # 检查数据量
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"    记录数: {count}")

        # 询问是否重建
        print("\n建议: 重建关联表以确保结构正确")
        choice = input("是否重建关联表？(yes/no): ").strip().lower()

        if choice != 'yes':
            print("[INFO] 跳过重建")
            return True

        # 删除旧表
        print("\n删除旧表...")
        try:
            prescription_herb_association.drop(engine, checkfirst=True)
            print("  ✓ 已删除 prescription_herbs")
        except:
            pass

        try:
            medic_herb_association.drop(engine, checkfirst=True)
            print("  ✓ 已删除 medic_herbs")
        except:
            pass

        # 创建新表
        print("\n创建新表...")
        Base.metadata.create_all(bind=engine)
        print("  ✓ 已创建 prescription_herbs")
        print("  ✓ 已创建 medic_herbs")

        # 验证
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if 'prescription_herbs' in tables and 'medic_herbs' in tables:
            print("\n[OK] 关联表创建成功!")
            return True
        else:
            print("\n[ERROR] 关联表创建失败")
            return False

    except Exception as e:
        print(f"\n[ERROR] 检查/重建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def step2_build_prescription_relationships():
    """步骤2: 建立方剂-药材关系"""
    print("\n" + "=" * 70)
    print("步骤 2/4: 建立方剂-药材关联关系")
    print("=" * 70)

    try:
        import import_prescription_relationships
        import_prescription_relationships.build_prescription_herb_relationships()
        return True
    except Exception as e:
        print(f"\n[ERROR] 建立方剂关系失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def step3_build_medic_relationships():
    """步骤3: 建立中成药-药材关系"""
    print("\n" + "=" * 70)
    print("步骤 3/4: 建立中成药-药材关联关系")
    print("=" * 70)

    try:
        import import_medic_relationships
        import_medic_relationships.build_medic_herb_relationships()
        return True
    except Exception as e:
        print(f"\n[ERROR] 建立中成药关系失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def step4_sync_to_neo4j():
    """步骤4: 同步关系到Neo4j"""
    print("\n" + "=" * 70)
    print("步骤 4/4: 同步关系到Neo4j")
    print("=" * 70)

    try:
        import verify_and_sync_relationships

        # 验证
        has_relationships = verify_and_sync_relationships.verify_relationships()

        if not has_relationships:
            print("\n[ERROR] MySQL中没有关联关系，无法同步")
            return False

        # 同步
        confirm = input("\n是否同步关系到Neo4j？(yes/no): ").strip().lower()
        if confirm != 'yes':
            print("[INFO] 已取消同步")
            return False

        verify_and_sync_relationships.sync_relationships_to_neo4j()
        return True

    except Exception as e:
        print(f"\n[ERROR] 同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主流程"""
    print("\n" + "=" * 70)
    print("Neo4j 关系建立完整流程")
    print("=" * 70)

    success = True

    # 步骤1: 检查并重建关联表
    if not step1_check_and_recreate_tables():
        success = False

    # 步骤2: 建立方剂-药材关系
    if success and not step2_build_prescription_relationships():
        success = False

    # 步骤3: 建立中成药-药材关系
    if success and not step3_build_medic_relationships():
        success = False

    # 步骤4: 同步到Neo4j
    if success and not step4_sync_to_neo4j():
        success = False

    # 最终结果
    print("\n" + "=" * 70)
    if success:
        print("✓ 所有步骤完成!")
        print("\nNeo4j中现在应该包含:")
        print("  - 方剂节点: 23685")
        print("  - 药材节点: 11132")
        print("  - 中成药节点: 1832")
        print("  - 关系: 数千到数万个")
    else:
        print("✗ 部分步骤失败，请检查错误信息")
    print("=" * 70)


if __name__ == "__main__":
    main()
