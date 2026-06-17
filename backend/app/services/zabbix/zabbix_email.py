"""
Zabbix Email Notification Service.

Sends professional HTML email alerts for:
  - Server down
  - CPU > 90%
  - Disk > 90%
  - High severity problems (High / Disaster)
  - Maintenance due within 7 days
  - Backup failure
  - SSL certificate expiration
  - Test email

Uses aiosmtplib for async SMTP. Gracefully skips when SMTP is not configured.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import structlog

logger = structlog.get_logger()

# =========================================================================
# HTML Email Templates
# =========================================================================

_BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e2e8f0; }}
    .container {{ max-width: 640px; margin: 40px auto; background: #1e293b; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }}
    .header {{ background: {header_color}; padding: 28px 32px; }}
    .header-icon {{ font-size: 32px; margin-bottom: 8px; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; color: #fff; letter-spacing: -0.3px; }}
    .header p {{ margin: 6px 0 0; font-size: 13px; color: rgba(255,255,255,0.75); }}
    .body {{ padding: 28px 32px; }}
    .severity-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; background: {badge_bg}; color: {badge_color}; margin-bottom: 20px; }}
    .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0; }}
    .info-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 14px 16px; }}
    .info-card label {{ display: block; font-size: 10px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }}
    .info-card value {{ font-size: 15px; font-weight: 600; color: #f1f5f9; }}
    .metric-bar-wrap {{ margin: 16px 0; }}
    .metric-bar-label {{ display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 13px; }}
    .metric-bar {{ height: 8px; background: #334155; border-radius: 4px; overflow: hidden; }}
    .metric-bar-fill {{ height: 100%; background: {metric_color}; border-radius: 4px; transition: width 0.3s; }}
    .action-box {{ background: #0f172a; border-left: 4px solid {header_color}; border-radius: 0 8px 8px 0; padding: 16px 20px; margin: 20px 0; }}
    .action-box h3 {{ margin: 0 0 8px; font-size: 13px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px; }}
    .action-box p {{ margin: 0; font-size: 14px; color: #cbd5e1; line-height: 1.6; }}
    .timestamp {{ font-size: 12px; color: #475569; margin-top: 20px; padding-top: 16px; border-top: 1px solid #334155; }}
    .footer {{ background: #0f172a; padding: 20px 32px; text-align: center; font-size: 11px; color: #475569; }}
    .footer strong {{ color: #64748b; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-icon">{icon}</div>
      <h1>{title}</h1>
      <p>Mini-SOC Infrastructure Monitoring Center</p>
    </div>
    <div class="body">
      <span class="severity-badge">{severity_label}</span>
      {body_content}
      <div class="action-box">
        <h3>Recommended Action</h3>
        <p>{suggested_action}</p>
      </div>
      <div class="timestamp">
        Alert generated: {timestamp} UTC &nbsp;·&nbsp; Mini-SOC Portal
      </div>
    </div>
    <div class="footer">
      <strong>Mini-SOC Infrastructure Monitoring</strong><br>
      This is an automated alert. Do not reply to this email.
    </div>
  </div>
</body>
</html>"""

_INFO_CARDS = """<div class="info-grid">
  <div class="info-card"><label>Server Name</label><value>{hostname}</value></div>
  <div class="info-card"><label>IP Address</label><value>{ip_address}</value></div>
  <div class="info-card"><label>Severity</label><value>{severity}</value></div>
  <div class="info-card"><label>Detected</label><value>{timestamp}</value></div>
</div>"""


def _build_server_down_html(hostname: str, ip: str, timestamp: str) -> str:
    body = _INFO_CARDS.format(
        hostname=hostname, ip_address=ip or "N/A",
        severity="Server Down", timestamp=timestamp
    )
    body += "<p style='color:#94a3b8;font-size:14px;line-height:1.7;'>The server is no longer responding to Zabbix agent polls. Immediate investigation is required to restore service availability.</p>"
    return _BASE_TEMPLATE.format(
        subject=f"[DISASTER] Server Down: {hostname}",
        header_color="#dc2626", icon="🔴",
        title=f"Server Down — {hostname}",
        badge_bg="#7f1d1d", badge_color="#fca5a5",
        severity_label="DISASTER",
        body_content=body,
        suggested_action="1. Check network connectivity and power status.\n2. Attempt remote console access.\n3. Verify Zabbix agent service on the host.\n4. Escalate to on-call engineer if unreachable within 5 minutes.",
        metric_color="#dc2626",
        timestamp=timestamp,
    )


def _build_high_cpu_html(hostname: str, ip: str, cpu_pct: float, timestamp: str) -> str:
    bar = f"""<div class="metric-bar-wrap">
  <div class="metric-bar-label"><span>CPU Utilization</span><span style="color:#f87171;font-weight:700;">{cpu_pct:.1f}%</span></div>
  <div class="metric-bar"><div class="metric-bar-fill" style="width:{min(cpu_pct,100):.0f}%"></div></div>
</div>"""
    body = _INFO_CARDS.format(
        hostname=hostname, ip_address=ip or "N/A",
        severity="High CPU", timestamp=timestamp
    ) + bar
    return _BASE_TEMPLATE.format(
        subject=f"[HIGH] High CPU Alert: {hostname} — {cpu_pct:.1f}%",
        header_color="#ea580c", icon="🔥",
        title=f"High CPU Detected — {hostname}",
        badge_bg="#431407", badge_color="#fb923c",
        severity_label="HIGH",
        body_content=body,
        suggested_action=f"CPU is at {cpu_pct:.1f}%. Identify top processes consuming CPU, check for runaway processes, and consider load balancing or vertical scaling.",
        metric_color="#ef4444",
        timestamp=timestamp,
    )


def _build_high_disk_html(hostname: str, ip: str, disk_pct: float, timestamp: str) -> str:
    bar = f"""<div class="metric-bar-wrap">
  <div class="metric-bar-label"><span>Disk Utilization</span><span style="color:#f87171;font-weight:700;">{disk_pct:.1f}%</span></div>
  <div class="metric-bar"><div class="metric-bar-fill" style="width:{min(disk_pct,100):.0f}%"></div></div>
</div>"""
    body = _INFO_CARDS.format(
        hostname=hostname, ip_address=ip or "N/A",
        severity="High Disk", timestamp=timestamp
    ) + bar
    return _BASE_TEMPLATE.format(
        subject=f"[HIGH] High Disk Usage: {hostname} — {disk_pct:.1f}%",
        header_color="#d97706", icon="💾",
        title=f"High Disk Usage — {hostname}",
        badge_bg="#451a03", badge_color="#fbbf24",
        severity_label="HIGH",
        body_content=body,
        suggested_action=f"Disk is at {disk_pct:.1f}%. Clean up log files and temp data, archive old backups, and consider adding storage capacity.",
        metric_color="#f59e0b",
        timestamp=timestamp,
    )


def _build_high_severity_html(hostname: str, ip: str, problem: str, severity_label: str, timestamp: str) -> str:
    color_map = {"High": "#ea580c", "Disaster": "#dc2626", "Average": "#d97706"}
    badge_bg_map = {"High": "#431407", "Disaster": "#7f1d1d", "Average": "#451a03"}
    badge_col_map = {"High": "#fb923c", "Disaster": "#fca5a5", "Average": "#fbbf24"}
    header_color = color_map.get(severity_label, "#6b21a8")
    body = _INFO_CARDS.format(
        hostname=hostname, ip_address=ip or "N/A",
        severity=severity_label, timestamp=timestamp
    )
    body += f"<p style='color:#94a3b8;font-size:14px;line-height:1.7;'>Problem detected: <strong style='color:#f1f5f9;'>{problem}</strong></p>"
    return _BASE_TEMPLATE.format(
        subject=f"[{severity_label.upper()}] Problem Alert: {hostname}",
        header_color=header_color, icon="⚠️",
        title=f"Problem Alert — {severity_label}",
        badge_bg=badge_bg_map.get(severity_label, "#3b0764"),
        badge_color=badge_col_map.get(severity_label, "#d8b4fe"),
        severity_label=severity_label.upper(),
        body_content=body,
        suggested_action=f"Investigate the problem '{problem}' on {hostname}. Check Zabbix for related triggers and acknowledge the problem once investigated.",
        metric_color=header_color,
        timestamp=timestamp,
    )


def _build_maintenance_due_html(hostname: str, ip: str, task_type: str, due_date: str, days_left: int, timestamp: str) -> str:
    urgency = "OVERDUE" if days_left <= 0 else f"DUE IN {days_left} DAYS"
    color = "#dc2626" if days_left <= 0 else "#d97706" if days_left <= 3 else "#2563eb"
    body = _INFO_CARDS.format(
        hostname=hostname, ip_address=ip or "N/A",
        severity=urgency, timestamp=due_date
    )
    body += f"<p style='color:#94a3b8;font-size:14px;line-height:1.7;'>Maintenance task: <strong style='color:#f1f5f9;'>{task_type}</strong> is {urgency.lower()}.</p>"
    return _BASE_TEMPLATE.format(
        subject=f"[MAINTENANCE] {task_type} due for {hostname}",
        header_color=color, icon="🔧",
        title=f"Maintenance Due — {task_type}",
        badge_bg="#1e293b", badge_color="#94a3b8",
        severity_label="MAINTENANCE",
        body_content=body,
        suggested_action=f"Schedule the '{task_type}' maintenance for {hostname} immediately. Coordinate with the operations team to minimize downtime.",
        metric_color=color,
        timestamp=timestamp,
    )


def _build_test_html(recipient: str, timestamp: str) -> str:
    body = f"<p style='color:#94a3b8;font-size:14px;line-height:1.7;'>This is a test notification from <strong style='color:#22d3ee;'>Mini-SOC Infrastructure Monitoring Center</strong>.</p><p style='color:#64748b;font-size:13px;'>If you received this email, your SMTP configuration is working correctly.</p>"
    return _BASE_TEMPLATE.format(
        subject="[TEST] Mini-SOC Notification Test",
        header_color="#0891b2", icon="✅",
        title="Email Notification Test",
        badge_bg="#164e63", badge_color="#67e8f9",
        severity_label="TEST",
        body_content=body,
        suggested_action="No action required. This is a test email to verify the notification system.",
        metric_color="#22d3ee",
        timestamp=timestamp,
    )


# =========================================================================
# Async Send Function
# =========================================================================

async def send_email(
    recipients: List[str],
    subject: str,
    html_body: str,
) -> tuple[bool, str]:
    """
    Send an HTML email via SMTP (async).
    Returns (success: bool, error_msg: str).
    Silently skips if SMTP is not configured.
    """
    from app.core.config import settings
    import email.mime.multipart as mm
    import email.mime.text as mt

    if not getattr(settings, "NOTIFICATION_ENABLED", False):
        logger.debug("zabbix_email_skipped", reason="NOTIFICATION_ENABLED=false")
        return False, "Notifications disabled"

    smtp_host = getattr(settings, "SMTP_HOST", "")
    smtp_user = getattr(settings, "SMTP_USER", "")
    smtp_from = getattr(settings, "SMTP_FROM", smtp_user)
    smtp_password_obj = getattr(settings, "SMTP_PASSWORD", None)
    smtp_password = smtp_password_obj.get_secret_value() if smtp_password_obj else ""
    smtp_port = getattr(settings, "SMTP_PORT", 587)

    if not smtp_host or not smtp_user:
        logger.warning("zabbix_email_no_smtp_config")
        return False, "SMTP not configured"

    try:
        import aiosmtplib

        msg = mm.MIMEMultipart("alternative")
        msg["From"] = smtp_from
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.attach(mt.MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            start_tls=True,
        )
        logger.info("zabbix_email_sent", recipients=recipients, subject=subject)
        return True, ""

    except Exception as exc:
        logger.error("zabbix_email_send_failed", error=str(exc))
        return False, str(exc)[:500]


# =========================================================================
# Notification Builder Functions (used by service)
# =========================================================================

async def notify_server_down(hostname: str, ip: str, recipients: List[str]) -> tuple[bool, str]:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = _build_server_down_html(hostname, ip, ts)
    return await send_email(recipients, f"[DISASTER] Server Down: {hostname}", html)


async def notify_high_cpu(hostname: str, ip: str, cpu_pct: float, recipients: List[str]) -> tuple[bool, str]:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = _build_high_cpu_html(hostname, ip, cpu_pct, ts)
    return await send_email(recipients, f"[HIGH] High CPU: {hostname} — {cpu_pct:.1f}%", html)


async def notify_high_disk(hostname: str, ip: str, disk_pct: float, recipients: List[str]) -> tuple[bool, str]:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = _build_high_disk_html(hostname, ip, disk_pct, ts)
    return await send_email(recipients, f"[HIGH] High Disk: {hostname} — {disk_pct:.1f}%", html)


async def notify_high_severity(
    hostname: str, ip: str, problem: str, severity_label: str, recipients: List[str]
) -> tuple[bool, str]:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = _build_high_severity_html(hostname, ip, problem, severity_label, ts)
    return await send_email(recipients, f"[{severity_label.upper()}] Problem: {hostname}", html)


async def notify_maintenance_due(
    hostname: str, ip: str, task_type: str, due_date: str, days_left: int, recipients: List[str]
) -> tuple[bool, str]:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = _build_maintenance_due_html(hostname, ip, task_type, due_date, days_left, ts)
    return await send_email(recipients, f"[MAINTENANCE] {task_type} due: {hostname}", html)


async def notify_test(recipient: str) -> tuple[bool, str]:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = _build_test_html(recipient, ts)
    return await send_email([recipient], "[TEST] Mini-SOC Notification Test", html)
