from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)
from config import db
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# States
ADD_AMOUNT, ADD_CATEGORY, ADD_WEEK = range(3)


CATEGORIES = ["groceries", "salary", "rent", "transport"]

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter amount (use negative for expense, positive for income):")
    return ADD_AMOUNT

async def add_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["amount"] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return ADD_AMOUNT

    # show categories as buttons
    keyboard = [[c] for c in CATEGORIES]
    await update.message.reply_text(
        "Choose a category:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ADD_CATEGORY

async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text

    if "amount" not in context.user_data:
        await update.message.reply_text("⚠️ Something went wrong. Please restart with /add.")
        return ConversationHandler.END

    amount = context.user_data["amount"]

    if category not in CATEGORIES:
        await update.message.reply_text("Please choose a valid category.")
        return ADD_CATEGORY

    # ✅ Business rule check
    if amount < 0 and category == "salary":
        await update.message.reply_text("❌ Salary cannot be negative. Canceled.")
        context.user_data.clear()
        return ConversationHandler.END

    if amount < 0 and category != "salary":
        # normal expense → allowed
        context.user_data["category"] = category
    elif amount >= 0 and category == "salary":
        # income → allowed
        context.user_data["category"] = category
    else:
        await update.message.reply_text("❌ Invalid combination of amount and category. Canceled.")
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text("Use 'current' week or enter year-week (e.g. 2025-39):")
    return ADD_WEEK


async def add_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower().startswith("current"):
        today = datetime.date.today()
        year, week, _ = today.isocalendar()
    else:
        try:
            year, week = text.split("-")
            year, week = int(year), int(week)
        except Exception:
            await update.message.reply_text("Invalid format. Use 'current' or 'YYYY-WW'.")
            return ADD_WEEK

    entry = {
        "user": update.effective_user.username,
        "amount": context.user_data["amount"],
        "category": context.user_data["category"],
        "date": datetime.datetime.utcnow(),
        "year": year,
        "week": week,
    }
    db.records.insert_one(entry)

    await update.message.reply_text(f"✅ Added {entry['amount']} ({entry['category']}) for week {year}-{week:02d}")
    keyboard = [[InlineKeyboardButton("🔙 Return to menu", callback_data="return_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⬇️ What next?", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Canceled.")
    keyboard = [[InlineKeyboardButton("🔙 Return to menu", callback_data="return_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⬇️ What next?", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

async def showrecords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year_week = context.args[0]  # e.g. "2025-39"
        year, week = year_week.split("-")
        year, week = int(year), int(week)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /showrecords <year-week>")
        return

    records = list(db.records.find({"year": year, "week": week}))
    if not records:
        await update.message.reply_text(f"No records found for {year_week}")
        return

    # Group by day + category
    days = {}
    for r in records:
        d = r["date"].strftime("%d.%m")
        cat = r["category"]
        amt = r["amount"]
        days.setdefault(d, {}).setdefault(cat, 0)
        days[d][cat] += amt

    # Build message
    msg = f"📒 Records for {year_week}:\n\n"
    for day, cats in sorted(days.items()):
        msg += f"{day}:\n"
        for cat, total in cats.items():
            msg += f"  {cat}: {total}\n"
        msg += "\n"

    await update.message.reply_text(msg)
    keyboard = [[InlineKeyboardButton("🔙 Return to menu", callback_data="return_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⬇️ What next?", reply_markup=reply_markup)