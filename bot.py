import os
import sys
import time
import glob
import json
import html
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

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
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────
def get_user_settings(chat_id: int) -> Dict[str, Any]:
    if chat_id not in user_states:
        user_states[chat_id] = {
            "referral": config.DEFAULT_REFERRAL_LINK,
            "min_offer": config.DEFAULT_MIN_OFFER,
            "manual_flow": None
        }
    return user_states[chat_id]


def build_main_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ Create 1 Account", callback_data="cb_create_1")
    b2 = types.InlineKeyboardButton("🚀 Create 3 Accounts", callback_data="cb_create_3")
    b3 = types.InlineKeyboardButton("📱 Manual OTP Login", callback_data="cb_manual_start")
    b4 = types.InlineKeyboardButton("💰 Check SMS Balances", callback_data="cb_balance")
    b5 = types.InlineKeyboardButton("⚙️ Current Settings", callback_data="cb_settings")
    b6 = types.InlineKeyboardButton("📁 View Recent Sessions", callback_data="cb_sessions")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b5, b6)
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
        "referral link attribution, and get <code>session_*.json</code> files instantly.\n\n"
        "⚙️ <b>Active Configuration:</b>\n"
        f"• <b>Target Min Discount:</b> ≥ ₹{esc(settings['min_offer'])} OFF\n"
        f"• <b>Referral Code:</b> <code>{esc(via_code)}</code>\n"
        f"• <b>Hosting Status:</b> 24/7 Cloud Active ✅\n\n"
        "📌 <b>Available Commands:</b>\n"
        "• <code>/create [count] [min_offer] [ref_code]</code> — Auto generate accounts\n"
        "• <code>/manual [phone]</code> — Step-by-step OTP login for your number\n"
        "• <code>/balance</code> — Check all SMS provider balances\n"
        "• <code>/referral &lt;code/url&gt;</code> — Change referral link/code\n"
        "• <code>/minoffer &lt;amount&gt;</code> — Set min discount (e.g. 180, 150, 200)\n"
        "• <code>/sessions</code> — List recent session files\n"
        "• <code>/status</code> — Check server uptime and worker status\n"
        "• <code>/cancel</code> — Cancel active manual OTP flow\n\n"
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
    total_sessions = len(glob.glob("session_*_meesho.json") + glob.glob("session_*.json"))

    text = (
        "📊 <b>Bot & Server Status:</b>\n\n"
        f"• <b>Uptime:</b> {hours}h {minutes}m {seconds}s\n"
        f"• <b>Active Tasks:</b> {active_tasks_count}\n"
        f"• <b>Total Stored Sessions:</b> {total_sessions} accounts\n"
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


@bot.message_handler(commands=["sessions"])
def cmd_sessions(message: types.Message):
    chat_id = message.chat.id
    files = sorted(
        glob.glob("session_*_meesho.json") + glob.glob("session_*.json"),
        key=os.path.getmtime,
        reverse=True
    )
    if not files:
        bot.reply_to(message, "📂 No generated session files found on the server yet.")
        return

    seen = set()
    unique_files = []
    for f in files:
        base = os.path.basename(f)
        if base not in seen:
            seen.add(base)
            unique_files.append(f)

    recent = unique_files[:10]
    lines = [f"📁 <b>Recent Session JSONs ({len(unique_files)} total):</b>\n"]

    for idx, fpath in enumerate(recent, 1):
        fname = os.path.basename(fpath)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%d/%m %H:%M")
        size_kb = os.path.getsize(fpath) / 1024
        lines.append(f"{idx}. <code>{esc(fname)}</code> ({size_kb:.1f} KB, {mtime})")

    lines.append("\n<i>To download any session, use the button or create new accounts.</i>")
    bot.reply_to(message, "\n".join(lines))


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
def _run_account_creation_worker(chat_id: int, count: int, min_offer: int, ref_link: str):
    global active_tasks_count
    with active_tasks_lock:
        active_tasks_count += 1

    settings = get_user_settings(chat_id)
    settings["stop_requested"] = False
    settings["is_generating"] = True

    try:
        ref_meta = meesho_engine.parse_referral_link(ref_link)
        status_msg = bot.send_message(
            chat_id,
            f"🚀 <b>Starting Continuous Meesho Account Generation</b>\n\n"
            f"• <b>Target Accounts:</b> {count}\n"
            f"• <b>Min FOD Discount:</b> ≥ ₹{esc(min_offer)} OFF\n"
            f"• <b>Referral Code:</b> <code>{esc(ref_meta.get('via') or 'None')}</code>\n"
            f"• <b>Mode:</b> <i>Continuous retry until JSON is generated ✅</i>\n\n"
            f"⏳ <i>Searching active SMS providers and hunting devices...</i>\n"
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

        for i in range(1, count + 1):
            if settings.get("stop_requested"):
                bot.send_message(chat_id, "🛑 <b>Generation stopped by user request.</b>", reply_markup=build_main_keyboard())
                break

            def log_progress(text: str):
                try:
                    bot.send_chat_action(chat_id, "typing")
                    bot.edit_message_text(
                        f"🚀 <b>Generating Account {i}/{count}</b>\n\n"
                        f"• <b>Status:</b> {esc(text)}\n"
                        f"• <b>Target Offer:</b> ≥ ₹{esc(min_offer)} OFF\n"
                        f"• <b>Referral:</b> <code>{esc(ref_meta.get('via') or 'None')}</code>\n\n"
                        f"<i>Retrying numbers automatically until JSON is delivered...</i>",
                        chat_id,
                        status_msg.message_id
                    )
                except Exception:
                    pass

            acc_data, session_file, err = meesho_engine.create_single_account_auto(
                min_offer=min_offer,
                ref_meta=ref_meta,
                active_providers=providers,
                log_cb=log_progress,
                stop_check=lambda: settings.get("stop_requested", False)
            )

            if settings.get("stop_requested"):
                bot.send_message(chat_id, "🛑 <b>Generation stopped by user request.</b>", reply_markup=build_main_keyboard())
                break

            if acc_data and session_file and os.path.exists(session_file):
                success_count += 1
                phone = acc_data.get("mobile") or acc_data.get("created_phone")
                user_id = acc_data.get("user_id")
                offer = acc_data.get("harvested_offer", {})
                offer_txt = offer.get("offer_text") or f"₹{offer.get('offer_value')} OFF"
                dev = acc_data.get("device_profile", {})
                dev_str = f"{dev.get('brand')} {dev.get('model')}"

                summary = (
                    f"🎉 <b>[Success {i}/{count}] Account Generated!</b>\n\n"
                    f"📱 <b>Phone:</b> <code>+91{esc(phone)}</code>\n"
                    f"🆔 <b>User ID:</b> <code>{esc(user_id)}</code>\n"
                    f"🎁 <b>FOD Offer:</b> <b>{esc(offer_txt)}</b>\n"
                    f"🔗 <b>Referral Code:</b> <code>{esc(ref_meta.get('via') or 'Organic')}</code>\n"
                    f"📱 <b>Device Bound:</b> {esc(dev_str)}\n"
                    f"📁 <b>Session File:</b> <code>{esc(os.path.basename(session_file))}</code>"
                )

                with open(session_file, "rb") as doc:
                    bot.send_document(
                        chat_id,
                        doc,
                        caption=summary,
                        visible_file_name=os.path.basename(session_file)
                    )
            else:
                if not settings.get("stop_requested"):
                    bot.send_message(
                        chat_id,
                        f"⚠️ <b>Account {i}/{count} Note:</b> {esc(err or 'Retry stopped')}"
                    )

            time.sleep(1)

        if not settings.get("stop_requested") and success_count > 0:
            bot.send_message(
                chat_id,
                f"🏆 <b>All {success_count}/{count} Meesho Accounts & JSONs Successfully Delivered!</b>",
                reply_markup=build_main_keyboard()
            )

    except Exception as e:
        logger.exception("Error in account creation worker")
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

    if len(args) >= 1 and args[0].isdigit():
        count = max(1, min(int(args[0]), 20))

    if len(args) >= 2 and args[1].isdigit():
        min_offer = int(args[1])

    if len(args) >= 3:
        ref_link = args[2]

    t = threading.Thread(
        target=_run_account_creation_worker,
        args=(chat_id, count, min_offer, ref_link),
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
                phone = acc_data.get("mobile")
                user_id = acc_data.get("user_id")
                offer = acc_data.get("harvested_offer", {})
                offer_txt = offer.get("offer_text") or f"₹{offer.get('offer_value')} OFF"
                ref_applied = acc_data.get("referral_applied", {})

                summary = (
                    f"🎉 <b>Manual Account Successfully Generated!</b>\n\n"
                    f"📱 <b>Phone:</b> <code>+91{esc(phone)}</code>\n"
                    f"🆔 <b>User ID:</b> <code>{esc(user_id)}</code>\n"
                    f"🎁 <b>FOD Discount:</b> <b>{esc(offer_txt)}</b>\n"
                    f"🔗 <b>Referral:</b> <code>{esc(ref_applied.get('via') or 'None')}</code>\n"
                    f"📁 <b>Session File:</b> <code>{esc(os.path.basename(session_file))}</code>"
                )

                with open(session_file, "rb") as doc:
                    bot.send_document(
                        chat_id,
                        doc,
                        caption=summary,
                        visible_file_name=os.path.basename(session_file)
                    )
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
            "💡 Type <code>/help</code> or use the menu below to start generating accounts.",
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
        bot.answer_callback_query(call.id, "Starting 3 Accounts Creation...")
        t = threading.Thread(
            target=_run_account_creation_worker,
            args=(chat_id, 3, settings["min_offer"], settings["referral"]),
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
        bot.answer_callback_query(call.id)
        files = sorted(
            glob.glob("session_*_meesho.json") + glob.glob("session_*.json"),
            key=os.path.getmtime,
            reverse=True
        )
        seen = set()
        unique = []
        for f in files:
            b = os.path.basename(f)
            if b not in seen:
                seen.add(b)
                unique.append(f)

        if not unique:
            bot.send_message(chat_id, "📂 No session files created yet.")
        else:
            lines = [f"📁 <b>Recent Sessions ({len(unique)} total):</b>\n"]
            for idx, fpath in enumerate(unique[:8], 1):
                fname = os.path.basename(fpath)
                lines.append(f"{idx}. <code>{esc(fname)}</code>")
            bot.send_message(chat_id, "\n".join(lines))


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
