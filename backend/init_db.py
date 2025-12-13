"""
N8 Control Center - 数据库初始化脚本
创建默认管理员用户和API Key
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models_merged import Base, User, APIKey, UserRole


def init_database():
    """初始化数据库"""
    database_url = os.getenv("DATABASE_URL", "postgresql://n8_user:n8_password_2024@localhost:5432/n8_control")
    
    print(f"Connecting to database: {database_url}")
    
    # 创建引擎
    engine = create_engine(database_url)
    
    # 创建所有表
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("✅ Tables created successfully")
    
    # 创建会话
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # 检查是否已有管理员用户
        admin = session.query(User).filter_by(username="admin").first()
        
        if admin:
            print("⚠️  Admin user already exists")
        else:
            # 创建默认管理员用户
            print("Creating default admin user...")
            admin = User(
                username="admin",
                display_name="系统管理员",
                role=UserRole.ADMIN,
                description="N8控制中心默认管理员账户"
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            print(f"✅ Admin user created: {admin.username} (ID: {admin.id})")
            
            # 为管理员创建默认API Key
            print("Creating default API key for admin...")
            # 使用 api_key_manager 的逻辑生成 hash
            import bcrypt
            secret = "admin_secret_2024"
            hashed_secret = bcrypt.hashpw(secret.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            api_key = APIKey(
                api_key="web_admin_api_key_2024_v1",
                api_name="默认管理员密钥",
                api_type="web",
                hashed_secret=hashed_secret,
                permissions=["*"],
                created_by="system"
            )
            session.add(api_key)
            session.commit()
            session.refresh(api_key)
            
            print("\n" + "="*60)
            print("🎉 初始化完成！")
            print("="*60)
            print(f"\n管理员账户信息：")
            print(f"  用户名: {admin.username}")
            print(f"  角色: {admin.role.value}")
            print(f"\nAPI Key（请妥善保管）：")
            print(f"  Key: {api_key.api_key}")
            print(f"  Secret: {secret}")
            print(f"\n使用方式：")
            print(f"  curl -H 'X-API-Key: {api_key.api_key}' -H 'X-API-Secret: {secret}' http://localhost:18032/api/v1/devices")
            print("\n" + "="*60)
        
        # 创建示例操作员用户（可选）
        operator = session.query(User).filter_by(username="operator").first()
        if not operator:
            print("\nCreating example operator user...")
            operator = User(
                username="operator",
                display_name="示例操作员",
                role=UserRole.OPERATOR,
                description="示例操作员账户，可以执行设备命令"
            )
            session.add(operator)
            session.commit()
            session.refresh(operator)
            
            # 为操作员创建API Key
            op_secret = "operator_secret_2024"
            op_hashed = bcrypt.hashpw(op_secret.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            operator_key = APIKey(
                api_key=APIKey.generate_key(),
                api_name="操作员密钥",
                api_type="internal",
                hashed_secret=op_hashed,
                permissions=["read_devices", "execute_command"],
                created_by="system"
            )
            session.add(operator_key)
            session.commit()
            session.refresh(operator_key)
            
            print(f"✅ Operator user created: {operator.username}")
            print(f"   API Key: {operator_key.api_key}")
            print(f"   Secret: {op_secret}")
        
        session.commit()
        print("\n✅ Database initialization completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during initialization: {e}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    init_database()
