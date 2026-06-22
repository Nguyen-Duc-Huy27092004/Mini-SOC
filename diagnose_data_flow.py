#!/usr/bin/env python3
"""
Wazuh Data Flow Diagnostic Script
Checks và xác định chính xác lý do dữ liệu bị trống
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Load .env explicitly
from dotenv import load_dotenv
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

async def main():
    """Run diagnostics"""
    
    print("\n" + "="*80)
    print("WAZUH DATA FLOW DIAGNOSTICS")
    print("="*80 + "\n")
    
    # 1. Check Configuration
    print("1️⃣  CHECKING CONFIGURATION")
    print("-" * 80)
    
    from app.core.config import settings
    
    alerts_file = settings.WAZUH_ALERTS_FILE
    wazuh_url = settings.WAZUH_API_URL
    wazuh_user = settings.WAZUH_API_USER
    
    print(f"   ✓ WAZUH_ALERTS_FILE: {alerts_file if alerts_file else '❌ EMPTY!'}")
    print(f"   ✓ WAZUH_API_URL: {wazuh_url}")
    print(f"   ✓ WAZUH_API_USER: {wazuh_user}")
    
    if not alerts_file:
        print("\n   ⚠️  CRITICAL: WAZUH_ALERTS_FILE is empty!")
        print("   → Collector will NOT start")
        print("   → No data will be collected from Wazuh")
    else:
        if Path(alerts_file).exists():
            stat = os.stat(alerts_file)
            print(f"\n   ✓ Alert file exists")
            print(f"      - Size: {stat.st_size} bytes")
            print(f"      - Modified: {stat.st_mtime}")
        else:
            print(f"\n   ❌ Alert file does NOT exist: {alerts_file}")
            print("   → Collector will wait for file to appear")
    
    # 2. Check Database Connection
    print("\n2️⃣  CHECKING DATABASE")
    print("-" * 80)
    
    try:
        from app.core.database import async_session_maker
        from app.models.event import WazuhEvent, EndpointInventory
        from sqlalchemy import select, func
        
        async with async_session_maker() as db:
            # Check WazuhEvent count
            count_events = await db.scalar(select(func.count(WazuhEvent.id)))
            count_today = await db.scalar(
                select(func.count(WazuhEvent.id)).where(
                    WazuhEvent.event_timestamp >= WazuhEvent.event_timestamp.type
                )
            )
            
            # Check EndpointInventory count
            count_agents = await db.scalar(select(func.count(EndpointInventory.id)))
            
            print(f"   ✓ WazuhEvent table: {count_events or 0} total records")
            print(f"   ✓ EndpointInventory table: {count_agents or 0} agents")
            
            if count_events == 0:
                print("\n   ⚠️  WARNING: WazuhEvent table is EMPTY!")
            if count_agents == 0:
                print("\n   ⚠️  WARNING: EndpointInventory table is EMPTY!")
    
    except Exception as e:
        print(f"\n   ❌ Database error: {e}")
    
    # 3. Check Collector Status
    print("\n3️⃣  CHECKING COLLECTOR")
    print("-" * 80)
    
    try:
        from app.collector import get_collector
        
        collector = get_collector()
        stats = collector.get_stats()
        
        print(f"   ✓ Collector instance: {collector}")
        print(f"   ✓ Running: {stats.get('running', False)}")
        print(f"   ✓ Processed: {stats.get('processed', 0)}")
        print(f"   ✓ Errors: {stats.get('errors', 0)}")
        print(f"   ✓ Dropped: {stats.get('dropped', 0)}")
        print(f"   ✓ Queue size: {stats.get('queue_size', 0)}")
        
        if not stats.get('running'):
            print("\n   ⚠️  WARNING: Collector is NOT running!")
    
    except Exception as e:
        print(f"\n   ❌ Collector error: {e}")
    
    # 4. Test Wazuh API Connection
    print("\n4️⃣  TESTING WAZUH API CONNECTION")
    print("-" * 80)
    
    try:
        from app.integrations.wazuh_client import WazuhAPIClient
        
        client = WazuhAPIClient(
            base_url=settings.WAZUH_API_URL,
            username=settings.WAZUH_API_USER,
            password=settings.WAZUH_API_PASSWORD.get_secret_value(),
            verify_ssl=settings.WAZUH_VERIFY_SSL,
        )
        
        # Test authentication
        token = await client._authenticate()
        
        if token:
            print(f"   ✓ Wazuh authentication: SUCCESS")
            print(f"      - Token length: {len(token)} chars")
            
            # Test get_agents
            agents = await client.get_agents(limit=5)
            print(f"   ✓ Get agents: {len(agents)} agents")
            
            if agents:
                for agent in agents[:3]:
                    print(f"      - {agent.get('id')}: {agent.get('name')} ({agent.get('status')})")
            else:
                print("      ⚠️  No agents returned!")
        
        else:
            print(f"   ❌ Wazuh authentication: FAILED")
            print(f"      - Check credentials: {settings.WAZUH_API_USER}")
        
        await client.close()
    
    except Exception as e:
        print(f"\n   ❌ Wazuh API error: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Summary
    print("\n5️⃣  SUMMARY & RECOMMENDATIONS")
    print("-" * 80)
    
    issues = []
    
    if not alerts_file:
        issues.append("CRITICAL: WAZUH_ALERTS_FILE not configured")
    
    if alerts_file and not Path(alerts_file).exists():
        issues.append("WARNING: Alerts file does not exist")
    
    # Check DB
    async with async_session_maker() as db:
        count = await db.scalar(select(func.count(WazuhEvent.id)))
        if count == 0:
            issues.append("WARNING: Database is empty - check collector")
    
    if issues:
        print("\n   ⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"      • {issue}")
    else:
        print("\n   ✓ No critical issues found!")
    
    print("\n   📋 NEXT STEPS:")
    print("      1. Ensure WAZUH_ALERTS_FILE is configured")
    print("      2. Ensure Wazuh alerts file has data")
    print("      3. Check collector logs: docker logs <container>")
    print("      4. Query database: SELECT COUNT(*) FROM wazuh_event;")
    print("      5. Test API: curl http://localhost:8000/api/v1/alerts")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
