#!/usr/bin/env python3
"""
Seed test data into the Mini-SOC database for development/testing.

Usage:
    cd backend
    python seed_dev_data.py

This script creates sample WazuhEvent and EndpointInventory records
so the dashboard displays real data without needing an actual Wazuh server.
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
os.chdir(Path(__file__).parent)


async def seed_database():
    print("\n" + "=" * 70)
    print("MINI-SOC DEVELOPMENT DATA SEEDER")
    print("=" * 70 + "\n")

    from app.core.database import async_session_maker, Base
    from app.core.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.models.event import WazuhEvent, EndpointInventory
    from sqlalchemy import select, func

    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)

    print(f"[+] Database: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

    # ── Step 1: Check existing data ────────────────────────────────────────
    async with async_session_maker() as db:
        existing_events = await db.scalar(select(func.count(WazuhEvent.id))) or 0
        existing_agents = await db.scalar(select(func.count(EndpointInventory.id))) or 0

    print(f"[+] Existing events: {existing_events}")
    print(f"[+] Existing agents: {existing_agents}")

    if existing_events > 0:
        answer = input("\n[?] Data already exists. Overwrite? (y/N): ").strip().lower()
        if answer != 'y':
            print("[!] Aborted.")
            return

    # ── Step 2: Seed EndpointInventory ─────────────────────────────────────
    print("\n[+] Seeding EndpointInventory (agents)...")

    sample_agents = [
        {"id": "001", "name": "web-server-01", "status": "active", "ip": "192.168.1.101", "os": "Ubuntu 22.04"},
        {"id": "002", "name": "db-server-01",  "status": "active", "ip": "192.168.1.102", "os": "CentOS 8"},
        {"id": "003", "name": "app-server-01", "status": "active", "ip": "192.168.1.103", "os": "Debian 11"},
        {"id": "004", "name": "fw-node-01",    "status": "active", "ip": "192.168.1.1",   "os": "pfSense 2.7"},
        {"id": "005", "name": "workstation-hr","status": "disconnected", "ip": "192.168.2.50", "os": "Windows 11"},
    ]

    async with async_session_maker() as db:
        for ag in sample_agents:
            existing = await db.scalar(
                select(EndpointInventory).where(EndpointInventory.agent_id == ag["id"])
            )
            if existing:
                existing.status = ag["status"]
                existing.ip_address = ag["ip"]
            else:
                db.add(EndpointInventory(
                    agent_id=ag["id"],
                    agent_name=ag["name"],
                    status=ag["status"],
                    ip_address=ag["ip"],
                    os_name=ag["os"],
                    current_risk_score=random.uniform(10, 85),
                    critical_alert_count=random.randint(0, 10),
                ))
        await db.commit()
        print(f"    ✓ {len(sample_agents)} agents seeded")

    # ── Step 3: Seed WazuhEvent ────────────────────────────────────────────
    print("\n[+] Seeding WazuhEvents (alerts)...")

    SEVERITY_LEVELS = ["critical", "high", "medium", "low"]
    CATEGORIES = [
        "authentication", "network_attack", "web_application_attack",
        "file_integrity_control", "malware", "system",
    ]
    RULE_DESCRIPTIONS = {
        "authentication":         "SSH brute force attack detected",
        "network_attack":         "Port scan detected from external IP",
        "web_application_attack": "SQL injection attempt in web request",
        "file_integrity_control": "Critical system file modified",
        "malware":                "Malicious process execution detected",
        "system":                 "System resource usage anomaly",
    }
    SOURCE_IPS = [
        "185.220.101.47", "45.33.32.156", "103.235.46.100",
        "192.168.99.200", "10.0.0.55", None, None,  # Some alerts have no source IP
    ]
    COUNTRIES = ["CN", "RU", "US", "KR", "DE", None, None]

    now = datetime.now(timezone.utc)
    events_to_create = []

    # Create 200 events spread over last 24 hours
    for i in range(200):
        hours_ago = random.uniform(0, 24)
        ts = now - timedelta(hours=hours_ago)
        cat = random.choice(CATEGORIES)
        sev = random.choices(
            SEVERITY_LEVELS,
            weights=[5, 15, 40, 40],  # More medium/low, fewer critical
        )[0]
        ag = random.choice(sample_agents)
        src_ip = random.choice(SOURCE_IPS)
        country = random.choice(COUNTRIES) if src_ip else None

        events_to_create.append(WazuhEvent(
            event_id=f"dev-seed-{uuid.uuid4().hex[:12]}",
            event_timestamp=ts,
            agent_id=ag["id"],
            agent_name=ag["name"],
            manager="wazuh-manager",
            source_ip=src_ip,
            source_port=random.choice([22, 80, 443, 3306, None]),
            source_user=random.choice(["root", "admin", "user1", None]),
            dest_ip=ag["ip"],
            dest_port=random.choice([22, 80, 443, 3306]),
            severity=sev,
            rule_id=str(random.randint(1000, 99999)),
            rule_description=RULE_DESCRIPTIONS[cat],
            rule_group=cat,
            rule_level={"critical": 14, "high": 10, "medium": 6, "low": 3}[sev],
            message=f"[DEV] {RULE_DESCRIPTIONS[cat]} from {src_ip or 'internal'}",
            category=cat,
            source_country=country,
            source_city=None,
            dest_country="VN",
            risk_score={"critical": 90, "high": 70, "medium": 45, "low": 20}[sev] + random.uniform(-5, 5),
            is_suppressed=False,
            wazuh_data={"dev": True, "seed_index": i},
        ))

    # Batch insert
    batch_size = 50
    async with async_session_maker() as db:
        for i in range(0, len(events_to_create), batch_size):
            batch = events_to_create[i:i + batch_size]
            db.add_all(batch)
            await db.flush()
        await db.commit()

    print(f"    ✓ {len(events_to_create)} events seeded")

    # ── Step 4: Verify ─────────────────────────────────────────────────────
    async with async_session_maker() as db:
        total_events = await db.scalar(select(func.count(WazuhEvent.id))) or 0
        total_agents = await db.scalar(select(func.count(EndpointInventory.id))) or 0
        events_today = await db.scalar(
            select(func.count(WazuhEvent.id)).where(
                WazuhEvent.event_timestamp >= now.replace(hour=0, minute=0, second=0, microsecond=0)
            )
        ) or 0

    print("\n" + "=" * 70)
    print("SEED COMPLETE")
    print("=" * 70)
    print(f"  Total events in DB : {total_events}")
    print(f"  Events today       : {events_today}")
    print(f"  Total agents in DB : {total_agents}")
    print("\n  ✓ Dashboard should now display data!")
    print("  ✓ Visit: http://localhost:5173 and login")
    print("  ✓ Or check: GET /api/v1/dashboard/summary")
    print("=" * 70 + "\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())
