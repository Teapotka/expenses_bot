from config import db
from telegram import Update
from telegram.ext import ContextTypes
import datetime
import calendar
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
import datetime
from config import db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# states
WEEK, TYPE, CATEGORY, AMOUNT, CONTINUE = range(5)

INCOME_CATEGORIES = ["salary", "tips", "bonus"]
EXPENSE_CATEGORIES = ["groceries", "rent", "travels", "supplies", "subscription", "party", "other"]


async def setweekly_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use 'current' week or enter year-week (e.g. 2025-39):"
    )
    return WEEK

async def setweekly_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    if text == "current":
        today = datetime.date.today()
        year, week, _ = today.isocalendar()
        context.user_data["year_week"] = f"{year}-{week:02d}"
    else:
        try:
            year, week = text.split("-")
            year, week = int(year), int(week)
            context.user_data["year_week"] = f"{year}-{week:02d}"
        except Exception:
            await update.message.reply_text("❌ Invalid format. Use 'current' or 'YYYY-WW'.")
            return WEEK

    # ask income/expense
    keyboard = [["income"], ["expense"]]
    await update.message.reply_text(
        "Is this for income or expense?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return TYPE

async def setweekly_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    est_type = update.message.text.strip().lower()
    if est_type not in ["income", "expense"]:
        await update.message.reply_text("❌ Please choose 'income' or 'expense'.")
        return TYPE

    context.user_data["type"] = est_type

    # categories based on type
    categories = INCOME_CATEGORIES if est_type == "income" else EXPENSE_CATEGORIES
    keyboard = [[c] for c in categories]
    await update.message.reply_text(
        f"Choose a category for {est_type}:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CATEGORY

async def setweekly_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip().lower()
    est_type = context.user_data["type"]

    valid_categories = INCOME_CATEGORIES if est_type == "income" else EXPENSE_CATEGORIES
    if category not in valid_categories:
        await update.message.reply_text("❌ Invalid category, choose from the list.")
        return CATEGORY

    context.user_data["category"] = category
    await update.message.reply_text("Enter amount (use + for income, - for expense):")
    return AMOUNT

async def setweekly_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return AMOUNT

    est_type = context.user_data["type"]

    # enforce sign rules
    if est_type == "income" and amount < 0:
        await update.message.reply_text("❌ Income cannot be negative.")
        return AMOUNT
    if est_type == "expense" and amount > 0:
        await update.message.reply_text("❌ Expense must be negative.")
        return AMOUNT

    context.user_data["amount"] = amount

    # save in DB
    year_week = context.user_data["year_week"]
    field = f"expected_{est_type}s.{context.user_data['category']}"
    db.week_estimates.update_one(
        {"_id": year_week, "year_week": year_week},
        {"$set": {field: amount}},
        upsert=True
    )

    await update.message.reply_text(
        f"✅ Set {est_type} estimate for {context.user_data['category']} = {amount} in {year_week}\nAdd more or finish?",
        reply_markup=ReplyKeyboardMarkup([["add more"], ["done"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return CONTINUE

async def setweekly_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    if choice == "add more":
        # restart at TYPE
        keyboard = [["income"], ["expense"]]
        await update.message.reply_text(
            "Income or expense?",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return TYPE
    else:
        await update.message.reply_text("✅ Weekly estimates updated. Finished.")
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Canceled.")
    context.user_data.clear()
    return ConversationHandler.END

async def showweekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year_week = context.args[0]
    except IndexError:
        await update.message.reply_text("Usage: /showweekly <year-week>")
        return

    doc = db.week_estimates.find_one({"_id": year_week})
    if not doc:
        await update.message.reply_text(f"No estimates found for week {year_week}")
        return

    incomes = doc.get("expected_incomes", {})
    expenses = doc.get("expected_expenses", {})

    msg = f"Estimates for {year_week}:\n\n"
    msg += "💰 Incomes:\n"
    for k, v in incomes.items():
        msg += f"- {k}: {v}\n"
    msg += "\n💸 Expenses:\n"
    for k, v in expenses.items():
        msg += f"- {k}: {v}\n"

    await update.message.reply_text(msg)
    keyboard = [[InlineKeyboardButton("🔙 Return to menu", callback_data="return_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⬇️ What next?", reply_markup=reply_markup)

async def currentweek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    year, week_num, _ = today.isocalendar()
    await update.message.reply_text(f"Current week is {year}-{week_num:02d}")

    # Current month
    month = today.month
    cal = calendar.Calendar(firstweekday=0)  # Monday = 0
    
    # Collect weekly ranges
    weeks = []
    month_days = [d for d in cal.itermonthdates(year, month) if d.month == month]
    
    start = None
    for d in month_days:
        if start is None:
            start = d
        if d.weekday() == 6:  # Sunday closes the week
            end = d
            w_year, w_num, _ = d.isocalendar()
            weeks.append((start, end, f"{w_year}-{w_num:02d}"))
            start = None
    
    # If last week spills over into next month
    if start is not None:
        last_day = month_days[-1]
        w_year, w_num, _ = last_day.isocalendar()
        weeks.append((start, last_day, f"{w_year}-{w_num:02d}"))
    
    # Format output
    msg = f"Current week is {year}-{week_num:02d}\n\n"
    for start, end, wn in weeks:
        msg += f"{start.day:02d}.{start.month:02d} - {end.day:02d}.{end.month:02d}    {wn}\n"
    
    await update.message.reply_text(msg)
    keyboard = [[InlineKeyboardButton("🔙 Return to menu", callback_data="return_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⬇️ What next?", reply_markup=reply_markup)

async def weekstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year_week = context.args[0]  # e.g. "2025-39"
        year, week = year_week.split("-")
        year, week = int(year), int(week)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /weekstats <year-week>")
        return

    # --- Fetch expected ---
    est_doc = db.week_estimates.find_one({"_id": year_week})
    est_incomes = est_doc.get("expected_incomes", {}) if est_doc else {}
    est_expenses = est_doc.get("expected_expenses", {}) if est_doc else {}

    # --- Fetch real ---
    records = list(db.records.find({"year": year, "week": week}))
    real_incomes, real_expenses = {}, {}
    for r in records:
        cat = r["category"]
        amt = r["amount"]
        if amt >= 0:
            real_incomes[cat] = real_incomes.get(cat, 0) + amt
        else:
            real_expenses[cat] = real_expenses.get(cat, 0) + amt  # keep negative

    # --- Build report ---
    msg = f"📊 Stats for {year_week}\n\n"

    msg += "💰 Incomes:\n"
    cats = set(est_incomes) | set(real_incomes)
    for cat in cats:
        e = est_incomes.get(cat, 0)
        r = real_incomes.get(cat, 0)
        diff = r - e
        msg += f"- {cat}: expected {e}, real {r}, diff {diff}\n"
    if not cats:
        msg += "None\n"

    msg += "\n💸 Expenses:\n"
    cats = set(est_expenses) | set(real_expenses)
    for cat in cats:
        e = est_expenses.get(cat, 0)  # already negative
        r = real_expenses.get(cat, 0)  # also negative
        diff = r - e
        msg += f"- {cat}: expected {e}, real {r}, diff {diff}\n"
    if not cats:
        msg += "None\n"

    # --- Totals ---
    total_est_income = sum(est_incomes.values())            # positive
    total_real_income = sum(real_incomes.values())          # positive
    total_est_expense = sum(est_expenses.values())          # negative
    total_real_expense = sum(real_expenses.values())        # negative

    expected_balance = total_est_income + total_est_expense
    real_balance = total_real_income + total_real_expense
    balance_diff = real_balance - expected_balance

    msg += "\n📌 Totals:\n"
    msg += f"Income: expected {total_est_income}, real {total_real_income}, diff {total_real_income - total_est_income}\n"
    msg += f"Expense: expected {total_est_expense}, real {total_real_expense}, diff {total_real_expense - total_est_expense}\n"
    msg += f"Balance difference (real - expected): {balance_diff}\n"

    await update.message.reply_text(msg)
    keyboard = [[InlineKeyboardButton("🔙 Return to menu", callback_data="return_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⬇️ What next?", reply_markup=reply_markup)

