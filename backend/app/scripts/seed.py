import asyncio
import sys
import os
import structlog

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.future import select
from app.core.config import settings
from app.core.database import engine, Base, async_session_maker
from app.services.auth_service import hash_password
from app.models.user import User, Role
from app.models.asset import Asset

logger = structlog.get_logger()

ROLES = [
    {"name": "Super Admin", "description": "Toàn quyền quản trị hệ thống SOC"},
    {"name": "SOC Analyst", "description": "Giám sát, phân tích và xử lý sự cố an ninh mạng"},
    {"name": "IT Admin", "description": "Quản lý cơ sở hạ tầng, cấu hình backup và máy chủ"},
    {"name": "Manager", "description": "Xem báo cáo tổng quan, KPI an ninh mạng (Executive)"},
    {"name": "Auditor", "description": "Đọc dữ liệu log audit, kiểm tra tính tuân thủ an toàn"}
]

USERS = [
    {
        "email": "admin@soc.local",
        "full_name": "SOC System Administrator",
        "role": "Super Admin"
    },
    {
        "email": "analyst@soc.local",
        "full_name": "Senior SOC Analyst",
        "role": "SOC Analyst"
    },
    {
        "email": "manager@soc.local",
        "full_name": "SOC Manager / CISO",
        "role": "Manager"
    },
    {
        "email": "auditor@soc.local",
        "full_name": "Compliance Auditor",
        "role": "Auditor"
    }
]

ASSETS = [
    {
        "agent_id": "001",
        "hostname": "AD-Controller",
        "ip_address": "192.168.10.10",
        "os_name": "Windows Server 2022",
        "os_version": "21H2",
        "department": "Security & Infrastructure",
        "owner": "Nguyen Van A",
        "criticality": "high",
        "location": "Hanoi Datacenter",
        "risk_score": 12.5
    },
    {
        "agent_id": "002",
        "hostname": "Web-Prod-Server",
        "ip_address": "10.0.0.15",
        "os_name": "Ubuntu 22.04 LTS",
        "os_version": "22.04.4",
        "department": "E-Commerce System",
        "owner": "Tran Thi B",
        "criticality": "critical",
        "location": "AWS AP-East-1",
        "risk_score": 35.8
    },
    {
        "agent_id": "003",
        "hostname": "DB-Production",
        "ip_address": "10.0.0.20",
        "os_name": "CentOS Stream 9",
        "os_version": "9.0",
        "department": "Database Services",
        "owner": "Hoang Van C",
        "criticality": "critical",
        "location": "AWS AP-East-1",
        "risk_score": 8.0
    },
    {
        "agent_id": "004",
        "hostname": "CEO-Laptop-Macbook",
        "ip_address": "192.168.20.105",
        "os_name": "macOS Sonoma",
        "os_version": "14.4",
        "department": "Executive Office",
        "owner": "Pham Van D",
        "criticality": "high",
        "location": "Hanoi Headquarters",
        "risk_score": 24.0
    },
    {
        "agent_id": "005",
        "hostname": "HR-Desktop-01",
        "ip_address": "192.168.30.50",
        "os_name": "Windows 11 Enterprise",
        "os_version": "23H2",
        "department": "Human Resources",
        "owner": "Le Thi E",
        "criticality": "low",
        "location": "Da Nang Branch",
        "risk_score": 2.5
    }
]

async def seed_data():
    logger.info("Starting database seeding...")
    
    # 1. Create tables if not exists
    async with engine.begin() as conn:
        logger.info("Initializing database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized.")

    async with async_session_maker() as session:
        # 2. Seed Roles
        role_map = {}
        for role_data in ROLES:
            stmt = select(Role).where(Role.name == role_data["name"])
            existing_role = (await session.execute(stmt)).scalars().first()
            if not existing_role:
                role = Role(name=role_data["name"], description=role_data["description"])
                session.add(role)
                role_map[role_data["name"]] = role
                logger.info(f"Added role: {role_data['name']}")
            else:
                role_map[role_data["name"]] = existing_role
        
        await session.commit()

        # 3. Seed Users
        password_hash = await hash_password(settings.DEFAULT_ADMIN_PASSWORD)
        for user_data in USERS:
            stmt = select(User).where(User.email == user_data["email"])
            existing_user = (await session.execute(stmt)).scalars().first()
            if not existing_user:
                new_user = User(
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=password_hash,
                    is_active=True,
                    must_change_password=True
                )
                role = role_map[user_data["role"]]
                new_user.roles.append(role)
                session.add(new_user)
                logger.info(f"Seeded user: {user_data['email']} with role {user_data['role']}")
            else:
                logger.info(f"User {user_data['email']} already exists.")
                
        # 4. Seed Assets
        for asset_data in ASSETS:
            stmt = select(Asset).where(Asset.hostname == asset_data["hostname"])
            existing_asset = (await session.execute(stmt)).scalars().first()
            if not existing_asset:
                new_asset = Asset(**asset_data)
                session.add(new_asset)
                logger.info(f"Seeded asset: {asset_data['hostname']}")
            else:
                logger.info(f"Asset {asset_data['hostname']} already exists.")

        await session.commit()
        logger.info("Database seeding completed successfully!")

if __name__ == "__main__":
    from app.core.logging import setup_logging
    setup_logging()
    asyncio.run(seed_data())
