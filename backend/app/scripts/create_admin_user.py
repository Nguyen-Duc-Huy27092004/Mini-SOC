#!/usr/bin/env python
"""
Create initial admin user for Mini SOC Portal
Usage: python create_admin_user.py --email admin@example.com --password "SecurePass123!"
"""

import asyncio
import argparse
import sys
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent to path
sys.path.insert(0, '/app')

from app.core.config import settings
from app.core.database import async_session_maker, Base, engine
from app.models.user import User, Role
from app.services.auth_service import hash_password
from sqlalchemy.future import select
import uuid


async def create_admin():
    """Create admin user and roles."""
    
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        # Create default roles
        roles_data = [
            {"name": "Super Admin", "description": "Full system access"},
            {"name": "SOC Analyst", "description": "Security operations analyst"},
            {"name": "IT Admin", "description": "IT administrator"},
            {"name": "Manager", "description": "SOC manager"},
            {"name": "Auditor", "description": "Audit and compliance"},
        ]
        
        existing_roles = {}
        for role_data in roles_data:
            # Check if role exists
            stmt = select(Role).where(Role.name == role_data["name"])
            existing = await session.execute(stmt)
            role = existing.scalars().first()
            
            if not role:
                role = Role(
                    id=uuid.uuid4(),
                    name=role_data["name"],
                    description=role_data["description"]
                )
                session.add(role)
                print(f"✓ Created role: {role_data['name']}")
            
            existing_roles[role_data["name"]] = role
        
        await session.commit()
        
        # Create admin user
        admin_email = "admin@soc.com"
        
        # Check if admin already exists
        stmt = select(User).where(User.email == admin_email)
        existing_admin = await session.execute(stmt)
        admin = existing_admin.scalars().first()
        
        if admin:
            print(f"⚠️  Admin user already exists: {admin_email}")
            return
        
        # Create admin user
        admin = User(
            id=uuid.uuid4(),
            email=admin_email,
            hashed_password=await hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            full_name="System Administrator",
            is_active=True,
            must_change_password=True,
        )
        
        # Assign Super Admin role
        admin.roles.append(existing_roles["Super Admin"])
        
        session.add(admin)
        await session.commit()
        
        print(f"✓ Created admin user: {admin_email}")
        print(f"✓ Temporary password: {settings.DEFAULT_ADMIN_PASSWORD}")
        print("⚠️  IMPORTANT: Admin must change password on first login!")


async def main():
    try:
        await create_admin()
        print("\n✅ Admin user creation completed successfully!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
