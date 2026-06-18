#!/usr/bin/env python3
"""
初始化认证数据库
创建用户表和默认管理员账户
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import engine, SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash


def init_database():
    """初始化数据库"""
    print("=" * 60)
    print("[INIT] 初始化认证数据库")
    print("=" * 60)

    # 创建所有表
    print("\n[1/3] 创建数据库表...")
    from app.db.session import Base

    Base.metadata.create_all(bind=engine)
    print("[OK] 数据库表创建成功")

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 检查是否已有管理员账户
        print("\n[2/3] 检查管理员账户...")
        admin = db.query(User).filter(User.username == "admin").first()

        if admin:
            print("[INFO] 管理员账户已存在")
            print(f"  用户名: {admin.username}")
            print(f"  邮箱: {admin.email}")
        else:
            # 创建默认管理员账户
            print("[INFO] 创建默认管理员账户...")
            admin_password = "admin123"  # 默认密码
            admin = User(
                username="admin",
                email="admin@example.com",
                full_name="系统管理员",
                hashed_password=get_password_hash(admin_password),
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

            print("[OK] 管理员账户创建成功")
            print(f"  用户名: admin")
            print(f"  密码: {admin_password}")
            print(f"  邮箱: admin@example.com")
            print(f"\n[WARN] 请在生产环境中修改默认密码！")

        # 创建测试用户账户
        print("\n[3/3] 检查测试用户账户...")
        test_user = db.query(User).filter(User.username == "testuser").first()

        if test_user:
            print("[INFO] 测试用户账户已存在")
        else:
            print("[INFO] 创建测试用户账户...")
            test_password = "test123"
            test_user = User(
                username="testuser",
                email="test@example.com",
                full_name="测试用户",
                hashed_password=get_password_hash(test_password),
                role=UserRole.USER,
                is_active=True
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

            print("[OK] 测试用户账户创建成功")
            print(f"  用户名: testuser")
            print(f"  密码: {test_password}")

        # 统计用户数量
        user_count = db.query(User).count()
        print(f"\n[STATS] 当前系统共有 {user_count} 个用户")

        print("\n" + "=" * 60)
        print("[OK] 认证数据库初始化完成")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
