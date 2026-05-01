import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

# --- 1. CONFIGURATION (Use Environment Variables!) ---
TOKEN = os.getenv('TELEGRAM_TOKEN') 
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Get the referral ID from the /start link
    ref_id = context.args[0] if context.args else None
    
    try:
        # Save to Supabase
        supabase.table("users").upsert({"user_id": user_id, "referrer_id": ref_id}).execute()
        
        pay_url = f"https://paystack.com/pay/calmmart?email={user_id}@calmmart.com"
        await update.message.reply_text(
            f"🏆 *Welcome to CalmMart Ltd!*\n\n"
            f"Step 1: Pay ₦10k here: {pay_url}\n"
            f"Step 2: Your referral link is:\n`https://t.me/YourBotUsername?start={user_id}`", 
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Error: {e}")

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
        await update.message.reply_text("Account not found. Use /start first!")

# --- 3. MAIN RUNNER ---
if __name__ == '__main__':
    # Initialize the Application
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("wallet", wallet))
    
    print("Bot is starting...")
    # This runs the bot until you press Ctrl-C
    application.run_polling(drop_pending_updates=True)
