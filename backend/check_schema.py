"""
Kiểm tra schema của cả 2 DB:
- mini_soc  (backend/.env - local dev)
- mini-soc  (docker .env.development)
Chạy: python check_schema.py
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Tất cả bảng + cột cần thiết theo models hiện tại
REQUIRED = {
    "roles":                ["id","name","description","created_at"],
    "users":                ["id","email","hashed_password","full_name","is_active","must_change_password","created_at"],
    "user_roles":           ["user_id","role_id"],
    "sessions":             ["id","user_id","token_jti","refresh_jti","expires_at","is_revoked","created_at"],
    "assets": [
        "id","agent_id","hostname","ip_address","mac_address","fqdn","domain",
        "asset_type","os_name","os_version","department","owner","location",
        "criticality","status","risk_score","source","last_seen",
        "created_at","updated_at","deleted_at",
    ],
    "portal_audit_logs":    ["id","user_id","action","details","ip_address","user_agent","created_at"],
    "wazuh_events": [
        "id","event_id","event_timestamp","agent_id","agent_name","manager",
        "source_ip","source_port","source_user","dest_ip","dest_port","dest_user",
        "severity","rule_id","rule_description","rule_group","rule_level",
        "message","category","source_country","source_city","dest_country",
        "risk_score","is_suppressed","wazuh_data","created_at","updated_at",
    ],
    "alert_suppressions": [
        "id","event_id","suppression_type","group_key","agent_id","rule_id",
        "source_ip","dest_ip","suppression_starts_at","suppression_expires_at",
        "alert_count","display_alert_count","status","acknowledged_at",
        "acknowledged_by_id","created_at","updated_at",
    ],
    "event_risks": [
        "id","event_id","agent_id","source_ip","source_user",
        "base_risk_score","severity_factor","frequency_factor","recency_factor",
        "event_risk_score","endpoint_risk_score","user_risk_score",
        "is_critical","is_anomalous","created_at","updated_at",
    ],
    "endpoint_inventory": [
        "id","agent_id","agent_name","status","last_keepalive",
        "os_platform","os_name","os_version","hostname","ip_address",
        "wazuh_agent_version","node_name","metadata",
        "current_risk_score","critical_alert_count","created_at","updated_at",
    ],
    "incidents": [
        "id","title","description","status","severity",
        "correlation_key","correlation_type","source_ip","agent_id",
        "rule_id","category","mitre_tactic","mitre_technique",
        "alert_count","risk_score","assigned_to_id","acknowledged_at",
        "acknowledged_by_id","resolved_at","metadata_json","created_at","updated_at",
    ],
    "incident_comments":    ["id","incident_id","user_id","body","created_at"],
    "alert_assignments":    ["id","incident_id","event_id","created_at"],
    "incident_timeline":    ["id","incident_id","action","actor_id","details","created_at"],
}

REQUIRED_ROLES = {"Super Admin","SOC Analyst","IT Admin","Manager","Auditor"}

DATABASES = {
    "LOCAL  (mini_soc  @ localhost:5434)":
        "postgresql+asyncpg://postgres:SocSecurePass123!@localhost:5434/mini_soc",
    "DOCKER (mini-soc  @ localhost:5434)":
        "postgresql+asyncpg://postgres:SocSecurePass123!@localhost:5434/mini-soc",
}

async def check_db(label: str, url: str):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    try:
        engine = create_async_engine(url, echo=False)
        async with engine.connect() as conn:
            # Alembic version
            try:
                r = await conn.execute(text(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='alembic_version')"
                ))
                has_alembic = r.scalar()
                if has_alembic:
                    r2 = await conn.execute(text("SELECT version_num FROM alembic_version"))
                    versions = [row[0] for row in r2.fetchall()]
                    print(f"  Alembic version : {versions}")
                else:
                    print(f"  Alembic version : CHƯA CÓ")
            except Exception as e:
                print(f"  Alembic check   : ERROR {e}")

            # Existing tables
            r = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"
            ))
            existing_tables = {row[0] for row in r.fetchall()}
            print(f"  Bảng hiện có    : {sorted(existing_tables)}")

            missing_tables = []
            missing_cols   = {}

            for table, req_cols in REQUIRED.items():
                if table not in existing_tables:
                    missing_tables.append(table)
                    continue
                r = await conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_schema='public' AND table_name='{table}'"
                ))
                existing_cols = {row[0] for row in r.fetchall()}
                missing = [c for c in req_cols if c not in existing_cols]
                if missing:
                    missing_cols[table] = missing

            # Roles
            roles_missing = set()
            if "roles" in existing_tables:
                try:
                    r = await conn.execute(text("SELECT name FROM roles"))
                    existing_roles = {row[0] for row in r.fetchall()}
                    roles_missing = REQUIRED_ROLES - existing_roles
                    print(f"  Roles hiện có   : {sorted(existing_roles)}")
                    if roles_missing:
                        print(f"  ⚠ Thiếu roles  : {sorted(roles_missing)}")
                    else:
                        print(f"  ✅ Roles đủ")
                except Exception as e:
                    print(f"  Roles check     : ERROR {e}")

            # Users
            if "users" in existing_tables:
                try:
                    r = await conn.execute(text("SELECT email FROM users LIMIT 5"))
                    users = [row[0] for row in r.fetchall()]
                    print(f"  Users           : {users}")
                except Exception as e:
                    print(f"  Users check     : ERROR {e}")

            print()
            if not missing_tables and not missing_cols:
                print("  ✅ Schema đầy đủ!")
            else:
                if missing_tables:
                    print(f"  ❌ Thiếu bảng   : {missing_tables}")
                for t, cols in missing_cols.items():
                    print(f"  ⚠ '{t}' thiếu cột: {cols}")

        await engine.dispose()
        return missing_tables, missing_cols

    except Exception as e:
        print(f"  ❌ Không kết nối được: {e}")
        return None, None

async def main():
    results = {}
    for label, url in DATABASES.items():
        mt, mc = await check_db(label, url)
        results[label] = (mt, mc)

    print(f"\n{'='*60}")
    print("  TÓM TẮT")
    print(f"{'='*60}")
    for label, (mt, mc) in results.items():
        if mt is None:
            print(f"  {label}: KHÔNG KẾT NỐI ĐƯỢC")
        elif not mt and not mc:
            print(f"  {label}: ✅ ĐẦY ĐỦ")
        else:
            total = len(mt or []) + sum(len(v) for v in (mc or {}).values())
            print(f"  {label}: ⚠ CẦN BỔ SUNG {total} mục")

if __name__ == "__main__":
    asyncio.run(main())
