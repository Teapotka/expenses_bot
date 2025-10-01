from config import db
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setbalance <amount>")
        return
    
    db.settings.update_one(
        {"_id": "settings"},
        {"$set": {"initial_balance": amount}},
        upsert=True
    )
    
    await update.message.reply_text(f"Initial balance set to {amount}")
    keyboard = [[InlineKeyboardButton("🔙 Return to menu", callback_data="return_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⬇️ What next?", reply_markup=reply_markup)