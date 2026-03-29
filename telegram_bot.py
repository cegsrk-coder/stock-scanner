"""
Telegram integration: sends scan reports to your Telegram chat.
Uses the Telegram Bot API directly (no extra dependencies needed).
"""

import urllib.request
import urllib.parse
import json
import os
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def is_telegram_configured():
    """Check if Telegram credentials are set."""
    return bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID)


def send_telegram_message(text):
    """Send a text message via Telegram Bot API. Splits long messages automatically."""
    if not is_telegram_configured():
        print("  Telegram: Not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in config/settings.py")
        return False

    # Telegram max message length is 4096 chars
    MAX_LEN = 4000
    chunks = _split_message(text, MAX_LEN)

    success = True
    for chunk in chunks:
        if not _send_chunk(chunk):
            success = False

    if success:
        print(f"  Telegram: Report sent ({len(chunks)} message{'s' if len(chunks) > 1 else ''})")
    return success


def send_telegram_file(filepath):
    """Send a file (the saved report .txt) via Telegram Bot API."""
    if not is_telegram_configured():
        print("  Telegram: Not configured.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"

    filename = os.path.basename(filepath)

    # Build multipart form data manually (no requests dependency)
    boundary = "----PythonFormBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{TELEGRAM_CHAT_ID}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"Stock Scanner Report\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    ).encode("utf-8")

    with open(filepath, "rb") as f:
        file_data = f.read()

    body += file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"  Telegram: Report file sent ({filename})")
                return True
            else:
                print(f"  Telegram: Failed — {result.get('description', 'unknown error')}")
                return False
    except Exception as e:
        print(f"  Telegram: Error sending file — {e}")
        return False


def send_report_to_telegram(report_text, report_filepath=None):
    """
    Send scan report to Telegram.
    Sends a summary message + the full report as a file attachment.
    """
    if not is_telegram_configured():
        return False

    # Build a compact summary for the chat message
    summary = _extract_summary(report_text)
    _send_chunk(summary)

    # Send full report as file attachment
    if report_filepath and os.path.exists(report_filepath):
        send_telegram_file(report_filepath)

    return True


def _send_chunk(text):
    """Send a single message chunk."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"  Telegram: Error — {e}")
        return False


def _split_message(text, max_len):
    """Split a long message into chunks at line boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    lines = text.split("\n")
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line

    if current:
        chunks.append(current)

    return chunks


def _extract_summary(report_text):
    """Extract a compact summary from the full report for the Telegram message."""
    lines = report_text.split("\n")
    summary_parts = []

    section = None
    stock_count = 0
    MAX_STOCKS_PER_SECTION = 5  # Show top 5 per section to keep it short

    for line in lines:
        stripped = line.strip()

        # Grab title lines
        if "SCAN REPORT" in stripped or "TIER 1:" in stripped or "TIER 2:" in stripped:
            summary_parts.append(stripped)

        # Section headers
        if "BUY ZONE" in stripped:
            summary_parts.append(f"\n>> {stripped}")
            section = "active"
            stock_count = 0
        elif "PROFIT BOOKING" in stripped:
            summary_parts.append(f"\n>> {stripped}")
            section = "active"
            stock_count = 0
        elif "DEEP VALUE" in stripped:
            summary_parts.append(f"\n>> {stripped}")
            section = "active"
            stock_count = 0
        elif "FALLING KNIFE" in stripped:
            summary_parts.append(f"\n>> {stripped}")
            section = "active"
            stock_count = 0
        elif "SUMMARY:" in stripped:
            summary_parts.append(f"\n{stripped}")
            section = None
        elif "SECTOR STRENGTH" in stripped or "FUNDAMENTAL" in stripped or "---" in stripped or "===" in stripped:
            section = None if "SECTOR" in stripped else section

        # Grab stock lines — symbol + price + verdict only
        elif section == "active" and stripped and stock_count < MAX_STOCKS_PER_SECTION:
            parts = stripped.split()
            if len(parts) >= 2 and parts[0].isalpha() and parts[0] == parts[0].upper() and len(parts[0]) >= 2:
                if parts[0] in ("Stock", "Sector", "No"):
                    continue
                # Extract: symbol, price, verdict (last column)
                symbol = parts[0]
                price = parts[1] if len(parts) > 1 else ""
                verdict = parts[-1] if parts[-1] in ("STRONG", "OK", "WEAK") else ""
                summary_parts.append(f"  {symbol:12s} {price:14s} {verdict}")
                stock_count += 1
                if stock_count == MAX_STOCKS_PER_SECTION:
                    summary_parts.append("  ... (see full report)")

    if not summary_parts:
        return report_text[:4000]

    summary_parts.append("\n(Full report attached below)")
    return "\n".join(summary_parts)
