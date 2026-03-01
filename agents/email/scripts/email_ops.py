#!/usr/bin/env python3
"""
email_ops.py — Yahoo Mail CLI tool for OpenClaw Email Agent
Usage: python email_ops.py <command> [options]

Credentials read from environment variables:
  EMAIL_ADDRESS, EMAIL_APP_PASSWORD, IMAP_HOST, IMAP_PORT, SMTP_HOST, SMTP_PORT
"""
import os, sys, imaplib, smtplib, email, argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from datetime import datetime

# ── Credentials ────────────────────────────────────────────────────────────
# Auto-load .env from the same directory as this script
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

EMAIL_ADDR  = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_PASS  = os.environ.get("EMAIL_APP_PASSWORD", "")
IMAP_HOST   = os.environ.get("IMAP_HOST", "imap.mail.yahoo.com")
IMAP_PORT   = int(os.environ.get("IMAP_PORT", "993"))
SMTP_HOST   = os.environ.get("SMTP_HOST", "smtp.mail.yahoo.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", "587"))


def decode_str(s):
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    if isinstance(s, str):
        parts = decode_header(s)
        result = []
        for part, enc in parts:
            if isinstance(part, bytes):
                result.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                result.append(part)
        return "".join(result)
    return str(s or "")


def imap_connect():
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    imap.login(EMAIL_ADDR, EMAIL_PASS)
    return imap


def fetch_envelopes(imap, uid_list, max_body=200):
    """Fetch subject/from/date for a list of UIDs."""
    results = []
    uid_str = ",".join(str(u) for u in uid_list)
    _, data = imap.uid("FETCH", uid_str, "(ENVELOPE BODY[TEXT]<0.500>)")
    # Parse in pairs (some servers send extra lines)
    i = 0
    while i < len(data):
        raw = data[i]
        if isinstance(raw, tuple):
            msg_data = b""
            # Collect all parts for this message
            for part in data[i:]:
                if isinstance(part, tuple):
                    msg_data += part[1] if len(part) > 1 else b""
                else:
                    break
            msg = email.message_from_bytes(b"Content-Type: text/plain\r\n\r\n" + msg_data)
            # Try to parse envelope from raw bytes
            raw_str = raw[0].decode("utf-8", errors="replace") if isinstance(raw[0], bytes) else str(raw[0])
            # Extract UID from the response
            uid_match = None
            import re
            uid_m = re.search(r'UID (\d+)', raw_str)
            uid_val = uid_m.group(1) if uid_m else "?"
            # Extract subject from raw (envelope)
            subj_m = re.search(r'ENVELOPE \(.*?"(.*?)"', raw_str)
            subj = decode_str(subj_m.group(1)) if subj_m else "(no subject)"
            results.append({"uid": uid_val, "subject": subj})
        i += 1
    return results


def cmd_list(args):
    imap = imap_connect()
    folder = args.folder or "INBOX"
    imap.select(f'"{folder}"', readonly=True)
    _, data = imap.uid("SEARCH", None, "ALL")
    uids = data[0].split()
    uids = uids[-args.limit:]  # most recent N

    if not uids:
        print(f"📭 {folder} 没有邮件")
        imap.logout()
        return

    uid_str = b",".join(uids)
    _, msgs = imap.uid("FETCH", uid_str, "(RFC822.HEADER)")

    print(f"📬 {folder} 最新 {len(uids)} 封邮件:\n")
    for i, item in enumerate(msgs):
        if not isinstance(item, tuple):
            continue
        raw_uid = uids[i] if i < len(uids) else b"?"
        msg = email.message_from_bytes(item[1])
        subj = decode_str(msg.get("Subject", "(no subject)"))
        sender = decode_str(msg.get("From", ""))
        date = msg.get("Date", "")
        print(f"  [{raw_uid.decode()}] {subj}")
        print(f"         From: {sender}")
        print(f"         Date: {date}\n")

    imap.logout()


def cmd_search(args):
    imap = imap_connect()
    imap.select('"INBOX"', readonly=True)
    query = args.query

    # Search in subject and body
    criteria = f'(OR SUBJECT "{query}" BODY "{query}")'
    _, data = imap.uid("SEARCH", None, criteria)
    uids = data[0].split()

    if not uids:
        print(f"🔍 没有找到包含 '{query}' 的邮件")
        imap.logout()
        return

    print(f"🔍 找到 {len(uids)} 封匹配邮件:\n")
    uid_str = b",".join(uids[-20:])  # limit to 20
    _, msgs = imap.uid("FETCH", uid_str, "(RFC822.HEADER)")

    uid_list = uids[-20:]
    for i, item in enumerate(msgs):
        if not isinstance(item, tuple):
            continue
        raw_uid = uid_list[i] if i < len(uid_list) else b"?"
        msg = email.message_from_bytes(item[1])
        subj = decode_str(msg.get("Subject", "(no subject)"))
        sender = decode_str(msg.get("From", ""))
        print(f"  [{raw_uid.decode()}] {subj}  |  {sender}")

    imap.logout()


def cmd_send(args):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDR
    msg["To"] = args.to
    msg["Subject"] = args.subject
    msg.attach(MIMEText(args.body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(EMAIL_ADDR, EMAIL_PASS)
        smtp.sendmail(EMAIL_ADDR, [args.to], msg.as_string())

    print(f"✅ 已发送邮件给 {args.to}，主题：{args.subject}")


def cmd_move(args):
    """Search for emails matching a keyword and move them to a target folder."""
    imap = imap_connect()
    imap.select('"INBOX"')

    query = args.search
    folder = args.folder

    # Search
    _, data = imap.uid("SEARCH", None, f'(OR SUBJECT "{query}" BODY "{query}")')
    uids = data[0].split()

    if not uids:
        print(f"📭 没有找到包含 '{query}' 的邮件，无需移动")
        imap.logout()
        return

    print(f"找到 {len(uids)} 封匹配邮件，移动到 {folder}...")

    # Ensure target folder exists
    result, _ = imap.create(f'"{folder}"')
    # Ignore error if folder already exists

    # COPY all UIDs at once, then delete from INBOX
    uid_str = b",".join(uids)
    copy_status, copy_result = imap.uid("COPY", uid_str, f'"{folder}"')

    if copy_status == "OK":
        # Mark as deleted in INBOX
        imap.uid("STORE", uid_str, "+FLAGS", "\\Deleted")
        imap.expunge()
        print(f"✅ 已将 {len(uids)} 封邮件移动到 {folder}")
    else:
        print(f"❌ 移动失败: {copy_result}")

    imap.logout()


def cmd_flag(args):
    imap = imap_connect()
    imap.select('"INBOX"')

    flag_map = {"seen": "\\Seen", "unseen": "-\\Seen"}
    imap_flag = flag_map.get(args.flag.lower())
    if not imap_flag:
        print(f"❌ 未知 flag: {args.flag}，支持: seen, unseen")
        imap.logout()
        return

    action = "+FLAGS" if not imap_flag.startswith("-") else "-FLAGS"
    clean_flag = imap_flag.lstrip("-")
    imap.uid("STORE", str(args.uid).encode(), action, clean_flag)
    print(f"✅ UID {args.uid} 已标记为 {args.flag}")
    imap.logout()


def main():
    if not EMAIL_ADDR or not EMAIL_PASS:
        print("❌ 缺少邮箱凭据，请设置环境变量：EMAIL_ADDRESS, EMAIL_APP_PASSWORD")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Yahoo Mail CLI")
    sub = parser.add_subparsers(dest="cmd")

    # list
    p_list = sub.add_parser("list", help="列出邮件")
    p_list.add_argument("--limit", type=int, default=10)
    p_list.add_argument("--folder", default="INBOX")

    # search
    p_search = sub.add_parser("search", help="搜索邮件")
    p_search.add_argument("query")

    # send
    p_send = sub.add_parser("send", help="发送邮件")
    p_send.add_argument("--to", required=True)
    p_send.add_argument("--subject", required=True)
    p_send.add_argument("--body", required=True)

    # move
    p_move = sub.add_parser("move", help="批量移动邮件")
    p_move.add_argument("--search", required=True, help="搜索关键词")
    p_move.add_argument("--folder", required=True, help="目标文件夹")

    # flag
    p_flag = sub.add_parser("flag", help="标记邮件")
    p_flag.add_argument("--uid", required=True, type=int)
    p_flag.add_argument("--flag", required=True, choices=["seen", "unseen"])

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    cmds = {"list": cmd_list, "search": cmd_search, "send": cmd_send,
            "move": cmd_move, "flag": cmd_flag}
    cmds[args.cmd](args)


if __name__ == "__main__":
    main()
