import os
import threading
import http.server
import socketserver
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

# --- 1. CONFIGURATION ---
# Note: These will pull from Render's 'Environment' variables
TOKEN = os.getenv('TELEGRAM_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. DUMMY SERVER FOR RENDER ---
# This stops the "No open ports detected" error
def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Keeping Render happy on port {port}")
        httpd.serve_forever()

# --- 3. BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_id = context.args[0] if context.args else None
    
    try:
        # Save user to Supabase
        supabase.table("users").upsert({
            "user_id": user_id, 
            "referrer_id": ref_id,
            "balance": 0,
            "total_earned": 0
        }).execute()
        
        pay_url = f"https://paystack.com/pay/calmmart?email={user_id}@calmmart.com"
        await update.message.reply_text(
            f"🏆 *Welcome to CalmMart Ltd!*\n\n"
            f"Step 1: Pay ₦10,000 here:\n{pay_url}\n\n"
            f"Step 2: Share your link to earn:\n"
            f"`https://t.me/Calm_mart_bot?start={user_id}`", 
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Supabase Error: {e}")

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if res.data:
        u = res.data[0]
        await update.message.reply_text(
            f"💰 *Wallet Balance:* ₦{u.get('balance', 0):,}\n"
            f"📈 *Total Earned:* ₦{u.get('total_earned', 0):,}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("Please use /start first to register!")

# --- 4. MAIN RUNNER ---
if __name__ == '__main__':
    # 1. Start the dummy server in a background thread
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # 2. Build the Telegram Bot
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN not found in environment!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("wallet", wallet))
        
        print("Bot is polling...")
        # drop_pending_updates prevents the bot from spamming 
        # old messages when it restarts
        app.run_polling(drop_pending_updates=True)
