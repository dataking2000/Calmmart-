import os
import sqlite3
import logging
import threading
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- 1. CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN', '8748428989:AAEIPiInJiBnPoxZ_lNY0X345uLgLKWxX1E')
REG_FEE = 10000
# 5 Generations: 15%, 10%, 5%, 2%, 1%
COMMISSIONS = [0.15, 0.10, 0.05, 0.02, 0.01]
# Path for Render Persistent Disk
DB_PATH = '/data/calmmart.db' if os.path.exists('/data') else 'calmmart.db'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 2. DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, referrer_id INTEGER, 
                  balance REAL DEFAULT 0, total_earned REAL DEFAULT 0, is_paid BOOLEAN DEFAULT FALSE)''')
    conn.commit()
    conn.close()

def distribute_commissions(paid_user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Mark user as paid
    conn.execute("UPDATE users SET is_paid = TRUE WHERE user_id = ?", (paid_user_id,))
    
    current_child = paid_user_id
    for pct in COMMISSIONS:
        row = conn.execute("SELECT referrer_id FROM users WHERE user_id = ?", (current_child,)).fetchone()
        if not row or not row['referrer_id']:
            break
        
        referrer = row['referrer_id']
        amount = REG_FEE * pct
        conn.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?", 
                     (amount, amount, referrer))
        current_child = referrer
        
    conn.commit()
    conn.close()

# --- 3. TELEGRAM BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id == user_id: ref_id = None
        except: pass

    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, ref_id))
    conn.commit()
    conn.close()

    # Automating Paystack Link: We pass the UserID in the 'memo' or as a URL param
    # Replace 'YOUR_PAYSTACK_URL' with your actual Paystack Payment Page link
    pay_url = f"https://paystack.com/pay/calmmart?email={user_id}@calmmart.com"
    ref_link = f"https://t.me/CalmMartBot?start={user_id}"

    await update.message.reply_text(
        f"🏆 *Welcome to CalmMart Ltd!*\n\n"
        f"To join and start earning:\n"
        f"1️⃣ Pay ₦10,000 here: {pay_url}\n"
        f"2️⃣ Your Referral Link: `{ref_link}`\n\n"
        f"Use /wallet to check earnings.", parse_mode='Markdown'
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (update.effective_user.id,)).fetchone()
    conn.close()
    
    if user:
        status = "✅ Active" if user['is_paid'] else "❌ Unpaid"
        text = (f"💳 *Wallet Summary*\nStatus: {status}\n\n"
                f"💰 Balance: ₦{user['balance']:,}\n"
                f"📈 Total Earned: ₦{user['total_earned']:,}")
    else:
        text = "Please type /start first."
    await update.message.reply_text(text, parse_mode='Markdown')

# --- 4. PAYSTACK WEBHOOK SERVER ---
flask_app = Flask(__name__)

@flask_app.route('/webhook', methods=['POST'])
def paystack_webhook():
    data = request.json
    if data['event'] == 'transaction.success':
        # Extract user ID from the email we formatted: user_id@calmmart.com
        customer_email = data['data']['customer']['email']
        try:
            paid_user_id = int(customer_email.split('@')[0])
            distribute_commissions(paid_user_id)
        except:
            pass
    return jsonify(status='success'), 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=5000)

# --- 5. MAIN EXECUTION ---
if __name__ == '__main__':
    init_db()
    # Start Webhook listener in background
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Start Telegram Bot
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("wallet", wallet))
    
    print("CalmMart Bot & Webhook Server are LIVE!")
    bot_app.run_polling()

