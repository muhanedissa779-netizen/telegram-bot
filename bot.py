import telebot
from telebot import types
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from flask import Flask
import threading

TOKEN = "8910375655:AAFqjpzn21RoficAFnR70Aut9nRI35MyKN4"
ADMIN_ID = 5738022147

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
        last_p = data[uid].get("last_profit", now)
        if now - last_p >= 3600:
            hours_passed = (now - last_p) // 3600
            hourly_rate = 0.20 / 24.0
            increment = data[uid]["active_deposit"] * hourly_rate * hours_passed
            data[uid]["balance"] += increment
            data[uid]["profit"] += increment
            data[uid]["last_profit"] = now - ((now - last_p) % 3600)
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
    user_step.pop(uid, None)

    text = (
        "🏦 *Welcome to DailyRewardsVIP*\n\n"
        f"👋 Hello {message.from_user.first_name}\n\n"
        "💎 Official Investment & Mining Platform\n"
        "📌 *Terms:* Deposits & Profits are locked for 7 days before withdrawal becomes available. Profit yields 20% daily, updating automatically every hour.\n\n"
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

    text = message.text if message.text else ""

    if text in ["👤 My Profile", "💰 Deposit", "📈 Mining", "💸 Withdraw", "📜 History", "🎁 Referral", "🛠 Support"]:
        user_step.pop(uid, None)

    add_profit(uid)
    data = load()

    # --- WAITING FOR SCREENSHOT CHECK ---
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
                "Your deposit is currently in **Pending** status. Please wait **5 to 10 minutes** while our finance team reviews your transaction receipt.",
                parse_mode="Markdown",
                reply_markup=main_reply_menu()
            )

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
            
            # Dirista fariinta admin-ka oo loo hubiyay qaab sugan
            try:
                bot.send_photo(int(ADMIN_ID), screenshot, caption=admin_text, parse_mode="Markdown", reply_markup=admin_kb)
                print("Deposit receipt successfully sent to admin.")
            except Exception as e:
                print(f"Error sending photo to admin: {e}")
                # Haddii sawirku diido, wuxuu isku dayayaa inuu ugu yaraan fariin qoraal ah soo diro
                try:
                    bot.send_message(int(ADMIN_ID), f"{admin_text}\n\n⚠️ *(Sawirkii wuu cilladaysnaa ama lama soo diri karo, fadlan hubi)*", parse_mode="Markdown", reply_markup=admin_kb)
                except Exception as err:
                    print(f"Failed to send text fallback to admin: {err}")

            user_step.pop(uid, None)
            return
        else:
            bot.send_message(
                message.chat.id,
                "❌ *Invalid Submission!*\n\nYou must upload a valid transaction **Screenshot** image. Text, documents, or other media are strictly blocked until a proper receipt is provided."
            )
            return

    # --- MENU ROUTING ---
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
            "👤 *USER PROFILE*\n\n"
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
            types.InlineKeyboardButton("🔵 USDT ERC20", callback_data="net_ERC20"),
            types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_menu")
        )
        bot.send_message(message.chat.id, "💰 *Select Deposit Network below:*", parse_mode="Markdown", reply_markup=kb)

    elif text == "📈 Mining":
        bot.send_message(
            message.chat.id,
            "⛏ *Mining Dashboard*\n\nYour active deposit generates a 20% daily return distributed and updated automatically **every hour**. Earnings are securely locked for 7 days.",
            parse_mode="Markdown",
            reply_markup=main_reply_menu()
        )

    elif text == "💸 Withdraw":
        user = data[uid]
        if user['deposit_time'] == 0:
            bot.send_message(message.chat.id, "❌ *Withdrawal Notice*\n\nYou currently have no active deposit or balance available for withdrawal.", parse_mode="Markdown", reply_markup=main_reply_menu())
            return
        
        elapsed = int(time.time()) - user['deposit_time']
        if elapsed < (7 * 86400):
            days_left = ((7 * 86400) - elapsed) // 86400
            hours_left = (((7 * 86400) - elapsed) % 86400) // 3600
            bot.send_message(message.chat.id, f"❌ *Withdrawal Locked!*\n\nPer platform policy, withdrawals are strictly locked until **7 full days** have elapsed from your deposit time.\n\n⏳ Time remaining: *{days_left} days and {hours_left} hours*.", parse_mode="Markdown", reply_markup=main_reply_menu())
        else:
            bot.send_message(message.chat.id, "💸 *Withdrawal Unlocked*\n\nYour 7-day lock period has successfully completed. Processing your payout request...", parse_mode="Markdown", reply_markup=main_reply_menu())

    elif text == "📜 History":
        history = data[uid].get("history", [])
        if not history:
            bot.send_message(message.chat.id, "📜 *Transaction History*\n\nNo deposit records found on your account yet.", parse_mode="Markdown", reply_markup=main_reply_menu())
        else:
            hist_text = "📜 *Deposit History Records*\n\n"
            for i in history:
                hist_text += f"💵 Amount: ${i['amount']} | Network: {i['network']} | Status: *{i['status']}*\n"
            bot.send_message(message.chat.id, hist_text, parse_mode="Markdown", reply_markup=main_reply_menu())

    elif text == "🎁 Referral":
        bot.send_message(
            message.chat.id,
            "🎁 *Referral Program*\n\nComing Soon! Stay tuned for our upcoming affiliate rewards system.",
            parse_mode="Markdown",
            reply_markup=main_reply_menu()
        )

    elif text == "🛠 Support":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💬 Contact Admin", url="https://t.me/Mohaned017087"))
        support_txt = (
            "🛠 *CUSTOMER SUPPORT*\n\n"
            "If you experience any transaction delays or account inquiries, please click the button below to reach out to our official support administration."
        )
        bot.send_message(message.chat.id, support_txt, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def callback_back_menu(call):
    uid = str(call.from_user.id)
    user_step.pop(uid, None)
    bot.answer_callback_query(call.id, "Cancelled deposit process.")
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ *Deposit Cancelled.*\n\nYou have returned to the main menu. Choose an option below:",
            parse_mode="Markdown"
        )
    except Exception:
        pass

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
    kb.add(types.InlineKeyboardButton("🔙 Back to Networks", callback_data="back_to_networks"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"💰 Network Selected: *{network}*\n\nPlease choose your preferred investment plan amount below:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_networks")
def callback_back_networks(call):
    bot.answer_callback_query(call.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🟢 USDT TRC20", callback_data="net_TRC20"),
        types.InlineKeyboardButton("🟡 USDT BEP20", callback_data="net_BEP20"),
        types.InlineKeyboardButton("🔵 USDT ERC20", callback_data="net_ERC20"),
        types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_menu")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="💰 *Select Deposit Network below:*",
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

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✅ Confirm Payment", callback_data="confirm_pay"),
        types.InlineKeyboardButton("🔙 Back to Plans", callback_data=f"back_to_plans_{network}")
    )

    wallet_address = WALLETS.get(network, WALLETS["TRC20"])

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📌 *Investment Deposit Summary*\n💳 Network: *{network}*\n💵 Amount: *${amount}*\n\n📬 *Deposit Wallet Address:*\n`{wallet_address}`\n\n*Instructions:* After transferring the exact amount from your personal wallet, click the button below to submit your payment proof.",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_plans_"))
def callback_back_plans(call):
    network = call.data.split("_")[3]
    bot.answer_callback_query(call.id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    for amount in INVESTMENT_PLANS:
        kb.add(types.InlineKeyboardButton(f"💵 ${amount} (20% Daily)", callback_data=f"plan_{amount}"))
    kb.add(types.InlineKeyboardButton("🔙 Back to Networks", callback_data="back_to_networks"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"💰 Network Selected: *{network}*\n\nPlease choose your preferred investment plan amount below:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_pay")
def callback_confirm(call):
    uid = str(call.from_user.id)
    bot.answer_callback_query(call.id)

    if uid not in user_step or "amount" not in user_step[uid]:
        user_step[uid] = {"amount": 50, "network": "TRC20"}

    user_step[uid]["state"] = "waiting_for_screenshot"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Cancel & Return", callback_data="back_to_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📸 *Payment Verification Step*\n\nPlease upload and send a clear **Transaction Screenshot** image right here in the chat. Unrelated images or text messages are strictly restricted until a valid receipt is submitted.",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_actions(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Unauthorized Action!", show_alert=True)
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
        data[uid]["last_profit"] = int(time.time())
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
                f"🎉 *Deposit Approved Successfully!* 🚀\n\n"
                f"Your deposit of ${amount} has been verified and processed by our finance team. Your balance and active deposit have been updated.",
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
                "❌ *Deposit Request Rejected*\n\nYour transaction receipt was flagged as invalid, blurry, or fake. Please submit a genuine and clear payment screenshot.",
                parse_mode="Markdown",
                reply_markup=main_reply_menu()
            )
        except Exception:
            pass

if __name__ == "__main__":
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
