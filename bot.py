import os
import sys
import time
import glob
import json
import html
import zipfile
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from flask import Flask, jsonify
import telebot
from telebot import types

import config
import meesho_engine

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("MeeshoTelegramBot")


def esc(text: Any) -> str:
    """Escapes HTML special characters for Telegram HTML parse mode."""
    return html.escape(str(text or ""))


# ─────────────────────────────────────────────────────────────
# INITIALIZE TELEGRAM BOT & FLASK HEALTH SERVER
# ─────────────────────────────────────────────────────────────
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN, parse_mode="HTML", threaded=True)
app = Flask(__name__)

# State storage for users (session settings & manual OTP flows)
user_states: Dict[int, Dict[str, Any]] = {}
bot_start_time = time.time()
active_tasks_lock = threading.Lock()
active_tasks_count = 0


@app.route("/")
@app.route("/health")
def health_check():
    uptime_sec = int(time.time() - bot_start_time)
    hours, rem = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    return jsonify({
        "status": "online",
        "service": "Meesho 24x7 JSON Generator Telegram Bot",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "active_tasks": active_tasks_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


def run_flask_server():
    port = config.PORT
    try:
        logger.info(f"🌐 Starting embedded Health Server on port {port} for 24/7 Render keep-alive...")
        import werkzeug.serving
        werkzeug.serving.run_simple("0.0.0.0", port, app, threaded=True)
    except Exception as e:
        logger.warning(f"Health server exception on port {port}: {e}")


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS & SESSION RETRIEVAL
# ─────────────────────────────────────────────────────────────
def get_user_settings(chat_id: int) -> Dict[str, Any]:
    if chat_id not in user_states:
        user_states[chat_id] = {
            "referral": config.DEFAULT_REFERRAL_LINK,
            "min_offer": config.DEFAULT_MIN_OFFER,
            "manual_flow": None,
            "stop_requested": False,
            "is_generating": False
        }
    return user_states[chat_id]


def get_unique_session_files() -> List[str]:
    """Returns all unique session JSON files sorted newest first."""
    patterns = [
        "session_*_meesho.json",
        "session_*.json",
        os.path.join(os.getcwd(), "session_*_meesho.json"),
        os.path.join(os.getcwd(), "session_*.json")
    ]
    seen = set()
    unique = []
    for pat in patterns:
        for f in glob.glob(pat):
            b = os.path.basename(f)
            if b not in seen:
                seen.add(b)
                unique.append(f)
    return sorted(unique, key=os.path.getmtime, reverse=True)


def send_session_file(chat_id: int, file_path: str) -> bool:
    """Sends a session JSON file as a downloadable document with rich metadata."""
    if not os.path.exists(file_path):
        bot.send_message(chat_id, "❌ Session file not found on server.")
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    phone = data.get("mobile") or data.get("created_phone") or (data.get("user") or {}).get("phone") or "N/A"
    clean_p = "".join(filter(str.isdigit, str(phone)))
    if len(clean_p) > 10:
        clean_p = clean_p[-10:]

    user_id = data.get("user_id") or (data.get("user") or {}).get("user_id") or "N/A"
    offer = data.get("harvested_offer", {})
    offer_txt = offer.get("offer_text") or (f"₹{offer.get('offer_value')} OFF" if offer.get("offer_value") else "N/A")
    ref = data.get("referral_applied", {})
    ref_via = ref.get("via") or "None"
    dev = data.get("device_profile", {})
    dev_str = f"{dev.get('brand', '')} {dev.get('model', '')}".strip() or "Standard"
    created_at = data.get("created_at") or "Recent"

    caption = (
        f"📄 <b>Meesho Session JSON:</b> <code>{esc(os.path.basename(file_path))}</code>\n\n"
        f"📱 <b>Phone:</b> <code>+91{esc(clean_p)}</code>\n"
        f"🆔 <b>User ID:</b> <code>{esc(user_id)}</code>\n"
        f"🎁 <b>FOD Offer:</b> <b>{esc(offer_txt)}</b>\n"
        f"🔗 <b>Referral:</b> <code>{esc(ref_via)}</code>\n"
        f"📱 <b>Device:</b> {esc(dev_str)}\n"
        f"📅 <b>Created:</b> {esc(created_at)}"
    )

    with open(file_path, "rb") as doc:
        bot.send_document(
            chat_id,
            doc,
            caption=caption,
            visible_file_name=os.path.basename(file_path)
        )
    return True


def create_sessions_zip() -> Optional[str]:
    """Zips all session JSON files and returns the path to the zip file."""
    files = get_unique_session_files()
    if not files:
        return None

    zip_filename = "meesho_all_sessions.zip"
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fpath in files:
            zipf.write(fpath, arcname=os.path.basename(fpath))

    return zip_filename


def build_main_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ Create 1 Account", callback_data="cb_create_1")
    b2 = types.InlineKeyboardButton("🚀 Create 5 Accounts (5x)", callback_data="cb_create_5")
    b3 = types.InlineKeyboardButton("💥 Create 20 Accounts (20x Turbo)", callback_data="cb_create_20")
    b4 = types.InlineKeyboardButton("📱 Manual OTP Login", callback_data="cb_manual_start")
    b5 = types.InlineKeyboardButton("💰 Check SMS Balances", callback_data="cb_balance")
    b6 = types.InlineKeyboardButton("📁 Browse & Download JSONs", callback_data="cb_sessions")
    b7 = types.InlineKeyboardButton("📦 Download All (ZIP)", callback_data="cb_download_all_zip")
    b8 = types.InlineKeyboardButton("⚙️ Current Settings", callback_data="cb_settings")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b5, b6)
    markup.add(b7, b8)
    return markup


def build_sessions_keyboard(files: List[str]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for fpath in files[:12]:
        fname = os.path.basename(fpath)
        digits = "".join(filter(str.isdigit, fname))
        phone_label = digits[-10:] if len(digits) >= 10 else fname[:14]
        buttons.append(types.InlineKeyboardButton(f"📥 {phone_label}", callback_data=f"cb_dl_{phone_label}"))

    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])

    markup.add(
        types.InlineKeyboardButton("📦 Download All (ZIP)", callback_data="cb_download_all_zip"),
        types.InlineKeyboardButton("🔄 Refresh List", callback_data="cb_sessions")
    )
    return markup


# ─────────────────────────────────────────────────────────────
# BOT COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start", "help"])
def cmd_start_help(message: types.Message):
    chat_id = message.chat.id
    logger.info(f"Received /start or /help from user {chat_id} (@{message.from_user.username})")
    settings = get_user_settings(chat_id)
    ref_info = meesho_engine.parse_referral_link(settings["referral"])
    via_code = ref_info.get("via") or "Default"

    welcome_text = (
        "🤖 <b>Welcome to Meesho Account & JSON Session Generator Bot!</b>\n\n"
        "Generate fresh Meesho accounts with maximum First Order Discount (FOD ₹180+), "
        "referral link attribution, and retrieve your <code>session_*.json</code> files 24/7.\n\n"
        "⚙️ <b>Active Configuration:</b>\n"
        f"• <b>Target Min Discount:</b> ≥ ₹{esc(settings['min_offer'])} OFF\n"
        f"• <b>Referral Code:</b> <code>{esc(via_code)}</code>\n"
        f"• <b>Hosting Status:</b> 24/7 Cloud Active ✅\n\n"
        "📌 <b>Account Creation Commands:</b>\n"
        "• <code>/create [count] [parallel] [min_offer] [ref]</code> — Parallel auto generation\n"
        "• <code>/manual [phone]</code> — Step-by-step manual OTP login\n"
        "• <code>/stop</code> or <code>/cancel</code> — Stop active generation\n\n"
        "📥 <b>JSON Retrieval Commands:</b>\n"
        "• <code>/sessions</code> — Interactive browser with 1-tap download buttons\n"
        "• <code>/get &lt;phone&gt;</code> — Download JSON for specific phone number\n"
        "• <code>/last</code> — Download the latest created session JSON\n"
        "• <code>/downloadall</code> or <code>/zip</code> — Download all sessions in a single ZIP\n\n"
        "🔧 <b>Settings & Info:</b>\n"
        "• <code>/balance</code> — Check all SMS provider balances\n"
        "• <code>/referral &lt;code/url&gt;</code> — Change referral link/code\n"
        "• <code>/minoffer &lt;amount&gt;</code> — Set min discount (e.g. 180, 150, 200)\n"
        "• <code>/status</code> — Server uptime and active worker stats\n\n"
        "<i>Tap a quick button below to start:</i>"
    )
    bot.send_message(chat_id, welcome_text, reply_markup=build_main_keyboard())


@bot.message_handler(commands=["status"])
def cmd_status(message: types.Message):
    chat_id = message.chat.id
    logger.info(f"Received /status from user {chat_id}")
    uptime_sec = int(time.time() - bot_start_time)
    hours, rem = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    total_sessions = len(get_unique_session_files())
    pending_refunds = meesho_engine.refund_manager.get_pending_count()
    total_refunded = meesho_engine.refund_manager.total_refunded

    text = (
        "📊 <b>Bot & Server Status:</b>\n\n"
        f"• <b>Uptime:</b> {hours}h {minutes}m {seconds}s\n"
        f"• <b>Active Tasks:</b> {active_tasks_count}\n"
        f"• <b>Total Stored Sessions:</b> {total_sessions} accounts\n"
        f"• <b>Auto-Refunds Recovered:</b> {total_refunded} numbers ✅\n"
        f"• <b>Pending Refund Retries (3m/6m):</b> {pending_refunds} numbers\n"
        f"• <b>Render Health Port:</b> {config.PORT} (Alive 24/7 ✅)\n"
        f"• <b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    bot.reply_to(message, text)


@bot.message_handler(commands=["balance"])
def cmd_balance(message: types.Message):
    chat_id = message.chat.id
    logger.info(f"Received /balance from user {chat_id}")
    msg = bot.reply_to(message, "📡 <i>Querying SMS provider balances...</i>")

    providers = meesho_engine.get_all_sms_providers()
    lines = ["💰 <b>SMS Provider Balances:</b>\n"]
    active_count = 0

    for p in providers:
        if not p.api_key:
            lines.append(f"• <b>{esc(p.name)}:</b> <i>No API Key configured</i>")
            continue
        try:
            bal = p.get_balance()
            if bal > 0:
                active_count += 1
                lines.append(f"• <b>{esc(p.name)}:</b> <code>${bal:.2f}</code> ✅")
            else:
                lines.append(f"• <b>{esc(p.name)}:</b> <code>${bal:.2f}</code> (Empty / error)")
        except Exception:
            lines.append(f"• <b>{esc(p.name)}:</b> <i>Query failed</i>")

    lines.append(f"\n✅ <b>Active Providers Ready:</b> {active_count}/{len(providers)}")
    pending_refunds = meesho_engine.refund_manager.get_pending_count()
    total_refunded = meesho_engine.refund_manager.total_refunded
    if pending_refunds > 0 or total_refunded > 0:
        lines.append(f"🔄 <b>Wallet Protection:</b> {total_refunded} refunded, {pending_refunds} retrying at 3m/6m")

    bot.edit_message_text("\n".join(lines), chat_id, msg.message_id)


@bot.message_handler(commands=["referral"])
def cmd_referral(message: types.Message):
    chat_id = message.chat.id
    settings = get_user_settings(chat_id)
    args = message.text.split(maxsplit=1)

    if len(args) > 1:
        new_ref = args[1].strip()
        settings["referral"] = new_ref
        ref_info = meesho_engine.parse_referral_link(new_ref)
        bot.reply_to(
            message,
            f"✅ <b>Referral Updated Successfully!</b>\n\n"
            f"• <b>Via Code:</b> <code>{esc(ref_info.get('via') or 'None')}</code>\n"
            f"• <b>Full Link:</b> <code>{esc(ref_info.get('full_link'))}</code>"
        )
    else:
        ref_info = meesho_engine.parse_referral_link(settings["referral"])
        bot.reply_to(
            message,
            f"🔗 <b>Current Referral Setting:</b>\n\n"
            f"• <b>Via Code:</b> <code>{esc(ref_info.get('via') or 'None')}</code>\n"
            f"• <b>Full Link:</b> <code>{esc(ref_info.get('full_link'))}</code>\n\n"
            "<i>To change, send: <code>/referral &lt;new_code_or_url&gt;</code></i>"
        )


@bot.message_handler(commands=["minoffer"])
def cmd_minoffer(message: types.Message):
    chat_id = message.chat.id
    settings = get_user_settings(chat_id)
    args = message.text.split(maxsplit=1)

    if len(args) > 1 and args[1].strip().isdigit():
        new_min = int(args[1].strip())
        settings["min_offer"] = new_min
        bot.reply_to(message, f"✅ <b>Minimum Target Discount updated to ₹{esc(new_min)} OFF</b>")
    else:
        bot.reply_to(
            message,
            f"🎯 <b>Current Min Discount Target:</b> ₹{esc(settings['min_offer'])} OFF\n\n"
            "<i>To change, send: <code>/minoffer &lt;amount&gt;</code> (e.g. <code>/minoffer 180</code>)</i>"
        )


# ─────────────────────────────────────────────────────────────
# JSON RETRIEVAL HANDLERS (/sessions, /get, /last, /downloadall)
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["sessions"])
def cmd_sessions(message: types.Message):
    chat_id = message.chat.id
    files = get_unique_session_files()

    if not files:
        bot.reply_to(message, "📂 No generated session files found on the server yet.\nUse <code>/create 1</code> to generate your first account!")
        return

    lines = [f"📁 <b>Available Meesho Session JSONs ({len(files)} total):</b>\n"]
    for idx, fpath in enumerate(files[:10], 1):
        fname = os.path.basename(fpath)
        digits = "".join(filter(str.isdigit, fname))
        phone_label = digits[-10:] if len(digits) >= 10 else fname
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%d/%m %H:%M")
        size_kb = os.path.getsize(fpath) / 1024
        lines.append(f"{idx}. 📱 <b>+91{esc(phone_label)}</b> — {size_kb:.1f} KB ({mtime})")

    lines.append("\n👉 <i>Tap any button below to download the JSON instantly:</i>")
    bot.reply_to(message, "\n".join(lines), reply_markup=build_sessions_keyboard(files))


@bot.message_handler(commands=["get", "download", "json"])
def cmd_get_session(message: types.Message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        files = get_unique_session_files()
        if not files:
            bot.reply_to(message, "📂 No session files available yet.")
            return
        bot.reply_to(
            message,
            "📱 <b>Download Session JSON:</b>\n\n"
            "Usage: <code>/get &lt;phone_number&gt;</code> (e.g. <code>/get 9566597321</code>)\n\n"
            "<i>Or tap a recent number below:</i>",
            reply_markup=build_sessions_keyboard(files)
        )
        return

    query_phone = "".join(filter(str.isdigit, args[1]))
    if len(query_phone) > 10:
        query_phone = query_phone[-10:]

    files = get_unique_session_files()
    matched_file = None
    for fpath in files:
        if query_phone in os.path.basename(fpath):
            matched_file = fpath
            break

    if matched_file:
        bot.send_message(chat_id, f"📥 <i>Fetching session file for +91{esc(query_phone)}...</i>")
        send_session_file(chat_id, matched_file)
    else:
        bot.reply_to(
            message,
            f"❌ No session JSON found for phone <code>+91{esc(query_phone)}</code>.\n"
            "Use <code>/sessions</code> to see all available numbers."
        )


@bot.message_handler(commands=["last"])
def cmd_last_session(message: types.Message):
    chat_id = message.chat.id
    files = get_unique_session_files()
    if not files:
        bot.reply_to(message, "📂 No session files found on the server yet.")
        return

    latest_file = files[0]
    bot.send_message(chat_id, "📥 <i>Sending latest generated session JSON...</i>")
    send_session_file(chat_id, latest_file)


@bot.message_handler(commands=["downloadall", "zip"])
def cmd_download_all_zip(message: types.Message):
    chat_id = message.chat.id
    files = get_unique_session_files()
    if not files:
        bot.reply_to(message, "📂 No session files found to package.")
        return

    msg = bot.reply_to(message, f"📦 <i>Packaging all {len(files)} session JSON files into ZIP...</i>")
    zip_path = create_sessions_zip()

    if zip_path and os.path.exists(zip_path):
        size_kb = os.path.getsize(zip_path) / 1024
        caption = (
            f"📦 <b>All Meesho Session JSONs Backup</b>\n\n"
            f"• <b>Total Accounts:</b> {len(files)} sessions\n"
            f"• <b>Archive Size:</b> {size_kb:.1f} KB\n"
            f"• <b>Generated At:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        with open(zip_path, "rb") as zf:
            bot.send_document(chat_id, zf, caption=caption, visible_file_name="meesho_all_sessions.zip")
        try:
            bot.delete_message(chat_id, msg.message_id)
        except Exception:
            pass
    else:
        bot.edit_message_text("❌ Failed to create ZIP archive.", chat_id, msg.message_id)


@bot.message_handler(commands=["cancel", "stop"])
def cmd_cancel(message: types.Message):
    chat_id = message.chat.id
    settings = get_user_settings(chat_id)
    cancelled = False
    if settings.get("manual_flow"):
        settings["manual_flow"] = None
        cancelled = True
    if settings.get("is_generating"):
        settings["stop_requested"] = True
        cancelled = True

    if cancelled:
        bot.reply_to(message, "🛑 <b>Stopping active generation / flow...</b>", reply_markup=build_main_keyboard())
    else:
        bot.reply_to(message, "ℹ️ No active task to cancel.", reply_markup=build_main_keyboard())


# ─────────────────────────────────────────────────────────────
# AUTO ACCOUNT CREATION PIPELINE (BACKGROUND THREAD)
# ─────────────────────────────────────────────────────────────
def _run_account_creation_worker(chat_id: int, count: int, min_offer: int, ref_link: str, parallel: int = 0):
    global active_tasks_count
    with active_tasks_lock:
        active_tasks_count += 1

    settings = get_user_settings(chat_id)
    settings["stop_requested"] = False
    settings["is_generating"] = True

    if parallel <= 0:
        parallel = min(count, 20)

    try:
        ref_meta = meesho_engine.parse_referral_link(ref_link)
        status_msg = bot.send_message(
            chat_id,
            f"⚡ <b>Starting High-Speed Parallel Meesho Account Generation</b>\n\n"
            f"• <b>Target Accounts:</b> {count}\n"
            f"• <b>Parallel Workers:</b> {parallel} concurrent threads 🚀\n"
            f"• <b>Min FOD Discount:</b> ≥ ₹{esc(min_offer)} OFF\n"
            f"• <b>Referral Code:</b> <code>{esc(ref_meta.get('via') or 'None')}</code>\n\n"
            f"⏳ <i>All SMS providers searching numbers in parallel...</i>\n"
            f"<i>(Send <code>/stop</code> anytime to cancel)</i>"
        )

        providers = [p for p in meesho_engine.get_all_sms_providers() if p.api_key and p.get_balance() > 0]
        if not providers:
            bot.edit_message_text(
                "❌ <b>Error:</b> No SMS providers with active positive balance available.\n"
                "Please check provider balances with <code>/balance</code> or add credits.",
                chat_id,
                status_msg.message_id
            )
            return

        success_count = 0
        success_lock = threading.Lock()
        active_status = {}
        status_update_lock = threading.Lock()
        last_edit_time = [0.0]

        def update_ui_status():
            now = time.time()
            if now - last_edit_time[0] < 2.0:
                return
            last_edit_time[0] = now
            with status_update_lock:
                status_lines = []
                for wid, st in sorted(active_status.items()):
                    status_lines.append(f"• <b>Worker #{wid}:</b> {esc(st)}")

                ui_text = (
                    f"⚡ <b>Generating {count} Accounts in Parallel ({parallel} Workers)</b>\n\n"
                    f"• <b>Progress:</b> {success_count}/{count} completed\n"
                    f"• <b>Target Offer:</b> ≥ ₹{esc(min_offer)} OFF\n\n"
                    + "\n".join(status_lines[-6:])
                )
                try:
                    bot.send_chat_action(chat_id, "typing")
                    bot.edit_message_text(ui_text, chat_id, status_msg.message_id)
                except Exception:
                    pass

        def _worker_task(worker_id: int):
            nonlocal success_count
            while True:
                if settings.get("stop_requested"):
                    break
                with success_lock:
                    if success_count >= count:
                        break

                def log_progress(text: str):
                    active_status[worker_id] = text
                    update_ui_status()

                acc_data, session_file, err = meesho_engine.create_single_account_auto(
                    min_offer=min_offer,
                    ref_meta=ref_meta,
                    active_providers=providers,
                    log_cb=log_progress,
                    stop_check=lambda: settings.get("stop_requested", False)
                )

                if settings.get("stop_requested"):
                    break

                if acc_data and session_file and os.path.exists(session_file):
                    with success_lock:
                        if success_count >= count:
                            break
                        success_count += 1
                        current_num = success_count

                    send_session_file(chat_id, session_file)
                    break
                else:
                    time.sleep(1)

        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = [executor.submit(_worker_task, w_id) for w_id in range(1, count + 1)]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    logger.error(f"Worker exception: {e}")

        if not settings.get("stop_requested") and success_count > 0:
            bot.send_message(
                chat_id,
                f"🏆 <b>All {success_count}/{count} Meesho Accounts & JSONs Successfully Delivered!</b>\n\n"
                "<i>You can retrieve any file anytime with <code>/sessions</code> or <code>/get &lt;phone&gt;</code></i>",
                reply_markup=build_main_keyboard()
            )

    except Exception as e:
        logger.exception("Error in parallel account creation worker")
        bot.send_message(chat_id, f"❌ <b>Error occurred during execution:</b> {esc(str(e))}")
    finally:
        settings["is_generating"] = False
        settings["stop_requested"] = False
        with active_tasks_lock:
            active_tasks_count -= 1


@bot.message_handler(commands=["create"])
def cmd_create(message: types.Message):
    chat_id = message.chat.id
    settings = get_user_settings(chat_id)
    args = message.text.split()[1:]

    count = 1
    min_offer = settings["min_offer"]
    ref_link = settings["referral"]
    parallel = 0

    if len(args) >= 1 and args[0].isdigit():
        count = max(1, min(int(args[0]), 100))

    if len(args) >= 2 and args[1].isdigit():
        parallel = max(1, min(int(args[1]), 20))

    if len(args) >= 3 and args[2].isdigit():
        min_offer = int(args[2])

    if len(args) >= 4:
        ref_link = args[3]

    t = threading.Thread(
        target=_run_account_creation_worker,
        args=(chat_id, count, min_offer, ref_link, parallel),
        daemon=True
    )
    t.start()


# ─────────────────────────────────────────────────────────────
# MANUAL OTP FLOW
# ─────────────────────────────────────────────────────────────
def start_manual_otp_flow(chat_id: int, phone: str):
    settings = get_user_settings(chat_id)
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) > 10:
        clean_phone = clean_phone[-10:]

    if len(clean_phone) != 10:
        bot.send_message(chat_id, "❌ Invalid phone number. Please provide a 10-digit number (e.g. 9876543210).")
        return

    msg = bot.send_message(chat_id, f"⏳ <i>Hunting high offer & sending OTP to +91{esc(clean_phone)}...</i>")

    def _manual_prep_worker():
        ref_meta = meesho_engine.parse_referral_link(settings["referral"])
        creator, otp_req, harv_dev, err = meesho_engine.prepare_manual_otp(
            phone10=clean_phone,
            min_offer=settings["min_offer"],
            ref_meta=ref_meta,
            log_cb=lambda t: bot.send_chat_action(chat_id, "typing")
        )

        if not creator or not otp_req:
            bot.edit_message_text(
                f"❌ <b>Failed to dispatch OTP:</b> {esc(err or 'Unknown error')}",
                chat_id,
                msg.message_id
            )
            return

        settings["manual_flow"] = {
            "creator": creator,
            "otp_req": otp_req,
            "harv_dev": harv_dev,
            "phone": clean_phone,
            "timestamp": time.time()
        }

        offer_val = harv_dev.get("offer_value", "?")
        dev = harv_dev.get("device_profile", {})
        dev_str = f"{dev.get('brand')} {dev.get('model')}"

        bot.edit_message_text(
            f"📨 <b>OTP Dispatched Successfully!</b>\n\n"
            f"• <b>Target Phone:</b> <code>+91{esc(clean_phone)}</code>\n"
            f"• <b>FOD Offer Bound:</b> ₹{esc(offer_val)} OFF\n"
            f"• <b>Device Emulated:</b> {esc(dev_str)}\n\n"
            f"👉 <b>Please reply with the OTP code you received:</b>\n"
            f"<i>(Send <code>/cancel</code> to abort)</i>",
            chat_id,
            msg.message_id
        )

    t = threading.Thread(target=_manual_prep_worker, daemon=True)
    t.start()


@bot.message_handler(commands=["manual"])
def cmd_manual(message: types.Message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)

    if len(args) > 1:
        phone = args[1].strip()
        start_manual_otp_flow(chat_id, phone)
    else:
        msg = bot.reply_to(
            message,
            "📱 <b>Manual OTP Mode:</b>\n\nPlease enter the 10-digit Indian mobile number to receive OTP:"
        )
        bot.register_next_step_handler(msg, _handle_manual_phone_input)


def _handle_manual_phone_input(message: types.Message):
    if message.text.startswith("/"):
        return
    phone = message.text.strip()
    start_manual_otp_flow(message.chat.id, phone)


@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith("/"))
def handle_text_messages(message: types.Message):
    chat_id = message.chat.id
    settings = get_user_settings(chat_id)
    manual_data = settings.get("manual_flow")

    if manual_data:
        otp_code = message.text.strip()
        clean_otp = "".join(filter(str.isdigit, otp_code))
        if not clean_otp or len(clean_otp) < 4:
            bot.reply_to(message, "⚠️ Please enter a valid OTP code (e.g. 123456) or /cancel.")
            return

        status_msg = bot.reply_to(message, "🔐 <i>Verifying OTP and logging in to Meesho...</i>")
        creator = manual_data["creator"]
        otp_req = manual_data["otp_req"]

        def _verify_worker():
            acc_data, session_file, err = meesho_engine.complete_manual_otp(creator, otp_req, clean_otp)
            settings["manual_flow"] = None

            if acc_data and session_file and os.path.exists(session_file):
                send_session_file(chat_id, session_file)
            else:
                bot.edit_message_text(
                    f"❌ <b>OTP Verification Failed:</b> {esc(err or 'Incorrect OTP or session expired.')}\n"
                    "You can retry with <code>/manual [phone]</code>.",
                    chat_id,
                    status_msg.message_id
                )

        t = threading.Thread(target=_verify_worker, daemon=True)
        t.start()
    else:
        bot.reply_to(
            message,
            "💡 Type <code>/help</code> or use the menu below to start generating or downloading JSONs.",
            reply_markup=build_main_keyboard()
        )


# ─────────────────────────────────────────────────────────────
# INLINE KEYBOARD CALLBACK QUERY HANDLER
# ─────────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    settings = get_user_settings(chat_id)

    if call.data == "cb_create_1":
        bot.answer_callback_query(call.id, "Starting 1 Account Creation...")
        t = threading.Thread(
            target=_run_account_creation_worker,
            args=(chat_id, 1, settings["min_offer"], settings["referral"]),
            daemon=True
        )
        t.start()

    elif call.data == "cb_create_3":
        bot.answer_callback_query(call.id, "Starting 3 Accounts Parallel Creation...")
        t = threading.Thread(
            target=_run_account_creation_worker,
            args=(chat_id, 3, settings["min_offer"], settings["referral"], 3),
            daemon=True
        )
        t.start()

    elif call.data == "cb_create_5":
        bot.answer_callback_query(call.id, "Starting 5 Accounts Parallel (5x)...")
        t = threading.Thread(
            target=_run_account_creation_worker,
            args=(chat_id, 5, settings["min_offer"], settings["referral"], 5),
            daemon=True
        )
        t.start()

    elif call.data == "cb_create_20":
        bot.answer_callback_query(call.id, "Starting 20 Accounts Turbo Parallel (20x)...")
        t = threading.Thread(
            target=_run_account_creation_worker,
            args=(chat_id, 20, settings["min_offer"], settings["referral"], 20),
            daemon=True
        )
        t.start()

    elif call.data == "cb_manual_start":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "📱 <b>Manual OTP Mode:</b>\n\nPlease enter the 10-digit mobile number to receive OTP:"
        )
        bot.register_next_step_handler(msg, _handle_manual_phone_input)

    elif call.data == "cb_balance":
        bot.answer_callback_query(call.id, "Checking balances...")
        providers = meesho_engine.get_all_sms_providers()
        lines = ["💰 <b>SMS Provider Balances:</b>\n"]
        for p in providers:
            if not p.api_key:
                lines.append(f"• <b>{esc(p.name)}:</b> <i>No API Key configured</i>")
                continue
            try:
                bal = p.get_balance()
                lines.append(f"• <b>{esc(p.name)}:</b> <code>${bal:.2f}</code>")
            except Exception:
                lines.append(f"• <b>{esc(p.name)}:</b> <i>Error querying balance</i>")

        bot.send_message(chat_id, "\n".join(lines))

    elif call.data == "cb_settings":
        bot.answer_callback_query(call.id)
        ref_info = meesho_engine.parse_referral_link(settings["referral"])
        text = (
            "⚙️ <b>Current Bot Settings:</b>\n\n"
            f"• <b>Target Min Discount:</b> ₹{esc(settings['min_offer'])} OFF\n"
            f"• <b>Referral Code:</b> <code>{esc(ref_info.get('via') or 'None')}</code>\n"
            f"• <b>Referral URL:</b> <code>{esc(ref_info.get('full_link') or 'None')}</code>\n\n"
            "<i>Change with <code>/minoffer &lt;val&gt;</code> or <code>/referral &lt;code&gt;</code></i>"
        )
        bot.send_message(chat_id, text)

    elif call.data == "cb_sessions":
        bot.answer_callback_query(call.id, "Loading sessions...")
        files = get_unique_session_files()
        if not files:
            bot.send_message(chat_id, "📂 No session files created yet.")
        else:
            lines = [f"📁 <b>Available Meesho Session JSONs ({len(files)} total):</b>\n"]
            for idx, fpath in enumerate(files[:10], 1):
                fname = os.path.basename(fpath)
                digits = "".join(filter(str.isdigit, fname))
                phone_label = digits[-10:] if len(digits) >= 10 else fname
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%d/%m %H:%M")
                size_kb = os.path.getsize(fpath) / 1024
                lines.append(f"{idx}. 📱 <b>+91{esc(phone_label)}</b> — {size_kb:.1f} KB ({mtime})")

            lines.append("\n👉 <i>Tap any button below to download the JSON instantly:</i>")
            bot.send_message(chat_id, "\n".join(lines), reply_markup=build_sessions_keyboard(files))

    elif call.data == "cb_download_all_zip":
        bot.answer_callback_query(call.id, "Creating ZIP archive...")
        files = get_unique_session_files()
        if not files:
            bot.send_message(chat_id, "📂 No session files to package.")
            return

        zip_path = create_sessions_zip()
        if zip_path and os.path.exists(zip_path):
            size_kb = os.path.getsize(zip_path) / 1024
            caption = (
                f"📦 <b>All Meesho Session JSONs Backup</b>\n\n"
                f"• <b>Total Accounts:</b> {len(files)} sessions\n"
                f"• <b>Archive Size:</b> {size_kb:.1f} KB\n"
                f"• <b>Generated At:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            with open(zip_path, "rb") as zf:
                bot.send_document(chat_id, zf, caption=caption, visible_file_name="meesho_all_sessions.zip")

    elif call.data.startswith("cb_dl_"):
        phone_target = call.data.replace("cb_dl_", "").strip()
        bot.answer_callback_query(call.id, f"Sending +91{phone_target}...")
        files = get_unique_session_files()
        matched = None
        for fpath in files:
            if phone_target in os.path.basename(fpath):
                matched = fpath
                break
        if matched:
            send_session_file(chat_id, matched)
        else:
            bot.send_message(chat_id, f"❌ Session for +91{esc(phone_target)} not found.")


# ─────────────────────────────────────────────────────────────
# MAIN ENTRYPOINT
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🚀 Starting Meesho Telegram Bot & Render Keep-Alive Service...")

    # Ensure no old webhooks block polling
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        logger.warning(f"Could not remove webhook: {e}")

    # Start Flask Web Server in background daemon thread
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    # Start Telegram Bot Polling with auto-reconnection
    while True:
        try:
            logger.info("🤖 Telegram Bot polling started. Ready for commands!")
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            logger.error(f"⚠️ Bot polling exception: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)
