from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TELEGRAM_TOKEN, db
from handlers.balance import setbalance, balance
from handlers.weekly import showweekly, currentweek, weekstats
from handlers.records import showrecords
from telegram.ext import ConversationHandler, MessageHandler, filters
from handlers.records import add_start, add_amount, add_category, add_week, cancel
from handlers.records import ADD_AMOUNT, ADD_CATEGORY, ADD_WEEK
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram import KeyboardButton
from handlers.weekly import (
    setweekly_start, setweekly_week, setweekly_type,
    setweekly_category, setweekly_amount, setweekly_continue,
    WEEK, TYPE, CATEGORY, AMOUNT, CONTINUE
)
import datetime

# === Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:   # normal command
        target = update.message
    elif update.callback_query:  # from button
        target = update.callback_query.message
    else:
        return
    
    await target.reply_text("Hello! Retrieving settings...")

    settings = db.settings.find_one({"_id": "settings"})
    keyboard = [
        [InlineKeyboardButton("➕ Add record", callback_data="add")],
        [InlineKeyboardButton("💰 Set balance", callback_data="setbalance")],
        [InlineKeyboardButton("💵 Project balance", callback_data="balance")],
        [InlineKeyboardButton("📅 Weekly estimate", callback_data="setweekly")],
        [InlineKeyboardButton("📊 Show weekly", callback_data="showweekly")],
        [InlineKeyboardButton("📈 Week stats", callback_data="weekstats")],
        [InlineKeyboardButton("📆 Current week", callback_data="currentweek")],
        [InlineKeyboardButton("📒 Show records", callback_data="showrecords")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not settings:
        # If missing, create default
        settings = {
            "_id": "settings",
            "initial_balance": 0
        }
        db.settings.insert_one(settings)
        await target.reply_text("No settings found. Created default settings with balance = 0.\nUse /setbalance <amount> to change it.")
    else:
        balance = settings.get("initial_balance", 0)
        await target.reply_text(f"Welcome! Current initial balance: {balance}.\nUse /setbalance <amount> to update.")

    await target.reply_text("Available commands:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    today = datetime.date.today()
    year, week, _ = today.isocalendar()
    currentweekstring = f"{year}-{week:02d}"

    # match callback_data
    if query.data == "add":
        keyboard = [[KeyboardButton("/add")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await query.edit_message_text("Choose the command below:")
        await query.message.reply_text("👇 Tap to send:", reply_markup=reply_markup)
    elif query.data == "setbalance":
        await query.edit_message_text("ℹ️ To set balance, use:\n`/setbalance <amount>`", parse_mode="Markdown")
    if query.data == "setweekly":
        keyboard = [[KeyboardButton("/setweekly")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await query.edit_message_text("Choose the command below:")
        await query.message.reply_text("👇 Tap to send:", reply_markup=reply_markup)
    elif query.data == "showweekly":
        await query.edit_message_text(f"ℹ️ To show weekly estimates, use:\n`/showweekly <year-week>`.\nCurrent week is {currentweekstring}", parse_mode="Markdown")
    elif query.data == "weekstats":
        await query.edit_message_text(f"ℹ️ To view weekly stats, use:\n`/weekstats <year-week>`.\nCurrent week is {currentweekstring}", parse_mode="Markdown")
    elif query.data == "currentweek":
        await query.edit_message_text("ℹ️ To show the current week, just use:\n`/currentweek`", parse_mode="Markdown")
    elif query.data == "showrecords":
        await query.edit_message_text(f"ℹ️ To show records, use:\n`/showrecords <year-week>`.\nCurrent week is {currentweekstring}", parse_mode="Markdown")
    elif query.data == "balance":
        await balance(update, context)
        return
    elif query.data == "return_start":
        await start(update, context)
        return
    else:
        await query.edit_message_text("❌ Unknown action")


# === Main ===
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("setbalance", setbalance))
    app.add_handler(CommandHandler("balance", balance))

    setweekly_conv = ConversationHandler(
    entry_points=[CommandHandler("setweekly", setweekly_start)],
    states={
        WEEK: [MessageHandler(filters.TEXT & ~filters.COMMAND, setweekly_week)],
        TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setweekly_type)],
        CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, setweekly_category)],
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, setweekly_amount)],
        CONTINUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setweekly_continue)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(setweekly_conv)

    # app.add_handler(CommandHandler("setweekly", setweekly))
    app.add_handler(CommandHandler("showweekly", showweekly))
    app.add_handler(CommandHandler("currentweek", currentweek))

    conv_handler = ConversationHandler(
    entry_points=[CommandHandler("add", add_start)],
    states={
        ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_amount)],
        ADD_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_category)],
        ADD_WEEK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_week)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
    app.add_handler(conv_handler)

    # app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("showrecords", showrecords))
    app.add_handler(CommandHandler("weekstats", weekstats))

    app.run_polling()

if __name__ == "__main__":
    main()
