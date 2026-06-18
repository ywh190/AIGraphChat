import sys
import os
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import get_neo4j_driver
from neo4j import GraphDatabase

class Neo4jManager:

    """Neo4j数据库管理工具"""

    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        self.uri = uri
        self.user = user
        self.password = password

    def test_connection(self):
        """测试连接"""
        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            driver.verify_connectivity()
            print("✅ Neo4j连接成功！")
            driver.close()
            return True
        except Exception as e:
            print(f"❌ Neo4j连接失败: {e}")
            return False

    def list_databases(self):
        """列出所有数据库"""
        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            with driver.session() as session:
                result = session.run("SHOW DATABASES")
                print("\n📊 现有数据库列表:")
                print("-" * 60)
                for record in result:
                    name = record.get("name")
                    status = record.get("default", "")
                    is_default = " [默认]" if status == "default" else ""
                    current = record.get("currentStatus", "")
                    print(f"  📦 {name}{is_default} - {current}")
                print("-" * 60)
            driver.close()
        except Exception as e:
            print(f"❌ 获取数据库列表失败: {e}")

    def create_database(self, db_name):
        """创建新数据库"""
        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            with driver.session() as session:
                # 创建数据库
                query = f"CREATE DATABASE `{db_name}` IF NOT EXISTS"
                session.run(query)
                print(f"✅ 数据库 '{db_name}' 创建成功！")

                # 显示新数据库状态
                result = session.run("SHOW DATABASES")
                for record in result:
                    if record.get("name") == db_name:
                        print(f"   状态: {record.get('currentStatus')}")
                        break
            driver.close()
            return True
        except Exception as e:
            print(f"❌ 创建数据库失败: {e}")
            return False

    def delete_database(self, db_name):
        """删除数据库"""
        if db_name == "neo4j":
            print("⚠️  不能删除默认的 'neo4j' 数据库！")
            return False

        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            with driver.session() as session:
                query = f"DROP DATABASE `{db_name}` IF EXISTS"
                session.run(query)
                print(f"✅ 数据库 '{db_name}' 删除成功！")
            driver.close()
            return True
        except Exception as e:
            print(f"❌ 删除数据库失败: {e}")
            return False

    def switch_database(self, db_name):
        """切换到指定数据库（需要重启连接）"""
        print(f"ℹ️  切换到数据库 '{db_name}'")
        print(f"ℹ️  请更新配置文件中的 NEO4J_URI 为:")
        print(f"    bolt://localhost:7687/{db_name}")
        print(f"ℹ️  或者使用:")
        print(f"    NEO4J_URI=bolt://localhost:7687")
        print(f"    NEO4J_DATABASE={db_name}")

    def show_database_info(self, db_name="neo4j"):
        """显示数据库详细信息"""
        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            with driver.session(database=db_name) as session:
                print(f"\n📊 数据库 '{db_name}' 详细信息:")
                print("-" * 60)

                # 获取节点统计
                result = session.run("MATCH (n) RETURN labels(n) as label, count(n) as count ORDER BY count DESC")
                print("\n节点统计:")
                has_nodes = False
                for record in result:
                    label = record.get("label", "[无标签]")
                    count = record.get("count", 0)
                    if label:
                        print(f"  📦 {label}: {count} 个节点")
                        has_nodes = True
                if not has_nodes:
                    print("  📭 暂无节点")

                # 获取关系统计
                result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC")
                print("\n关系统计:")
                has_relations = False
                for record in result:
                    rel_type = record.get("type", "[无类型]")
                    count = record.get("count", 0)
                    if rel_type:
                        print(f"  🔗 {rel_type}: {count} 条关系")
                        has_relations = True
                if not has_relations:
                    print("  📭 暂无关系")

                print("-" * 60)
            driver.close()
        except Exception as e:
            print(f"❌ 获取数据库信息失败: {e}")

    def clear_database(self, db_name="neo4j"):
        """清空数据库中的所有数据"""
        print(f"⚠️  警告: 即将清空数据库 '{db_name}' 的所有数据！")

        confirm = input("确认清空? (输入 'yes' 确认): ")
        if confirm.lower() != 'yes':
            print("已取消操作")
            return False

        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            with driver.session(database=db_name) as session:
                result = session.run("MATCH (n) DETACH DELETE n")
                count = result.consume().counters.nodes_deleted
                print(f"✅ 已删除 {count} 个节点")
                print(f"✅ 数据库 '{db_name}' 清空完成！")
            driver.close()
            return True
        except Exception as e:
            print(f"❌ 清空数据库失败: {e}")
            return False


def main():
    print("=" * 60)
    print("     Neo4j 数据库管理工具")
    print("=" * 60)
    print()

    # 从配置文件读取连接信息
    try:
        from app.core.config import settings
        manager = Neo4jManager(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        print(f"使用配置文件中的连接信息:")
        print(f"  URI: {settings.NEO4J_URI}")
        print(f"  用户: {settings.NEO4J_USER}")
        print()
    except:
        print("⚠️  无法读取配置，使用默认连接信息")
        print("  URI: bolt://localhost:7687")
        print("  用户: neo4j")
        print()
        manager = Neo4jManager()

    # 测试连接
    if not manager.test_connection():
        print("\n请确保:")
        print("  1. Neo4j服务已启动")
        print("  2. 连接信息正确")
        print("  3. 防火墙允许连接")
        input("\n按回车键退出...")
        return

    while True:
        print("\n" + "=" * 60)
        print("请选择操作:")
        print("=" * 60)
        print("  1. 查看所有数据库")
        print("  2. 创建新数据库")
        print("  3. 删除数据库")
        print("  4. 查看数据库详情")
        print("  5. 清空数据库")
        print("  6. 切换数据库")
        print("  0. 退出")
        print("=" * 60)

        choice = input("\n请输入选项 (0-6): ").strip()

        if choice == '0':
            print("再见！")
            break
        elif choice == '1':
            manager.list_databases()
        elif choice == '2':
            db_name = input("请输入新数据库名称: ").strip()
            if db_name:
                manager.create_database(db_name)
        elif choice == '3':
            manager.list_databases()
            db_name = input("请输入要删除的数据库名称: ").strip()
            if db_name:
                manager.delete_database(db_name)
        elif choice == '4':
            db_name = input("请输入数据库名称 (默认neo4j): ").strip()
            if not db_name:
                db_name = "neo4j"
            manager.show_database_info(db_name)
        elif choice == '5':
            db_name = input("请输入数据库名称 (默认neo4j): ").strip()
            if not db_name:
                db_name = "neo4j"
            manager.clear_database(db_name)
        elif choice == '6':
            manager.list_databases()
            db_name = input("请输入要切换的数据库名称: ").strip()
            if db_name:
                manager.switch_database(db_name)
        else:
            print("❌ 无效选项，请重新选择")

        input("\n按回车键继续...")


if __name__ == '__main__':
    main()
