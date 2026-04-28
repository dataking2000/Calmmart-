import os
import threading
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

# --- 1. CONFIGURATION ---
TOKEN = os.getenv('8748428989:AAEIPiInJiBnPoxZ_lNY0X345uLgLKWxX1E')
SUPABASE_URL = os.getenv('https://ookitehmadvastflwbum.supabase.co/rest/v1/')
SUPABASE_KEY = os.getenv('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9va2l0ZWhtYWR2YXN0Zmx3YnVtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzczNzg1ODMsImV4cCI6MjA5Mjk1NDU4M30.1T24zLQYe3F4QA-8Nj4fiuL9GgZhvp94C4kzW4Q2ZTM')
REG_FEE = 10000
COMMISSIONS = [0.15, 0.10, 0.05, 0.02, 0.01] # 5 Generations

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. DATABASE LOGIC ---
def distribute_commissions(paid_user_id):
    # Mark user as paid in Supabase
    supabase.table("users").update({"is_paid": True}).eq("user_id", paid_user_id).execute()
    
    current_child = paid_user_id
    for pct in COMMISSIONS:
        # Find referrer
        response = supabase.table("users").select("referrer_id").eq("user_id", current_child).execute()
        if not response.data or not response.data[0]['referrer_id']:
            break
        
        ref_id = response.data[0]['referrer_id']
        amt = REG_FEE * pct
        
        # Update Referrer Balance
        ref_data = supabase.table("users").select("balance", "total_earned").eq("user_id", ref_id).execute()
        if ref_data.data:
            new_bal = ref_data.data[0]['balance'] + amt
            new_total = ref_data.data[0]['total_earned'] + amt
            supabase.table("users").update({"balance": new_bal, "total_earned": new_total}).eq("user_id", ref_id).execute()
        
        current_child = ref_id

# --- 3. TELEGRAM COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_id = int(context.args[0]) if context.args else None
    
    # Save to Supabase
    supabase.table("users").upsert({"user_id": user_id, "referrer_id": ref_id}).execute()
    
    pay_url = f"https://paystack.com/pay/calmmart?email={user_id}@calmmart.com"
    await update.message.reply_text(
        f"🏆 *Welcome to CalmMart Ltd!*\n\n"
        f"Pay ₦10k: {pay_url}\n"
        f"Your Link: `https://t.me/YourBotName?start={user_id}`", 
        parse_mode='Markdown'
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = supabase.table("users").select("*").eq("user_id", update.effective_user.id).execute()
    if res.data:
        u = res.data[0]
        await update.message.reply_text(f"💰 Balance: ₦{u['balance']:,}\n📈 Total: ₦{u['total_earned']:,}")

# --- 4. WEBHOOK & RUNNER ---
flask_app = Flask(__name__)

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data['event'] == 'transaction.success':
        email = data['data']['customer']['email']
        uid = int(email.split('@')[0])
        distribute_commissions(uid)
    return jsonify(status='success'), 200

if __name__ == '__main__':
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=5000), daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallet", wallet))
    app.run_polling()
