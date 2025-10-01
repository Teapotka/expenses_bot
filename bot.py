import os
import datetime
import openpyxl
import calendar
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
load_dotenv()


# === Config ===
DB_NAME = "expenses"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# === MongoDB connection ===
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsAllowInvalidCertificates=False
)
db = client[DB_NAME]
settings = db["settings"]
records = db["records"]
week_estimates = db["week_estimates"]


# === Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Retrieving settings...")
    settings = db.settings.find_one({"_id": "settings"})
    
    if not settings:
        # If missing, create default
        settings = {
            "_id": "settings",
            "initial_balance": 0
        }
        db.settings.insert_one(settings)
        await update.message.reply_text("No settings found. Created default settings with balance = 0.\nUse /setbalance <amount> to change it.")
    else:
        balance = settings.get("initial_balance", 0)
        await update.message.reply_text(f"Welcome! Current initial balance: {balance}.\nUse /setbalance <amount> to update.")

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
            
async def setestimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("BEGIN")
    await update.message.reply_text("Works!")

    # try:
    #     year_week = context.args[0]       # e.g. "2025-39"
    #     est_type = context.args[1]        # "income" or "expense"
    #     category = context.args[2]
    #     amount = float(context.args[3])
    # except (IndexError, ValueError):
    #     await update.message.reply_text("Usage: /setestimate <year-week> <income|expense> <category> <amount>")
    #     return

    # # Validate type
    # if est_type not in ["income", "expense"]:
    #     await update.message.reply_text("Type must be 'income' or 'expense'.")
    #     return

    # # Update Mongo
    # field = f"expected_{est_type}s.{category}"
    # db.week_estimates.update_one(
    #     {"_id": year_week, "year_week": year_week},
    #     {"$set": {field: amount}},
    #     upsert=True
    # )

    # await update.message.reply_text(f"Set {est_type} estimate for {category} = {amount} in week {year_week}")

async def setweekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year_week = context.args[0]       # e.g. "2025-39"
        est_type = context.args[1]        # "income" or "expense"
        category = context.args[2]
        amount = float(context.args[3])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setweekly <year-week> <income|expense> <category> <amount>")
        return
    
    # Validate type
    if est_type not in ["income", "expense"]:
        await update.message.reply_text("Type must be 'income' or 'expense'.")
        return
    
    # # Update Mongo
    field = f"expected_{est_type}s.{category}"
    db.week_estimates.update_one(
        {"_id": year_week, "year_week": year_week},
        {"$set": {field: amount}},
        upsert=True
    )

    await update.message.reply_text(f"Set {est_type} estimate for {category} = {amount} in week {year_week}")

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

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])   # e.g. -10 or 1200
        category = context.args[1]        # e.g. groceries, salary
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /add <amount> <category>")
        return

    today = datetime.date.today()
    year, week, _ = today.isocalendar()

    entry = {
        "user": update.effective_user.username,
        "amount": amount,
        "category": category,
        "date": datetime.datetime.utcnow(),
        "year": year,
        "week": week,
    }
    db.records.insert_one(entry)

    await update.message.reply_text(f"Added record: {amount} ({category}) for week {year}-{week:02d}")

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
        if amt >= 0:  # income
            real_incomes[cat] = real_incomes.get(cat, 0) + amt
        else:  # expense
            real_expenses[cat] = real_expenses.get(cat, 0) + amt

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
        e = est_expenses.get(cat, 0)
        r = real_expenses.get(cat, 0)
        diff = r - e
        msg += f"- {cat}: expected -{e}, real {r}, diff {diff}\n"
    if not cats:
        msg += "None\n"

    # --- Totals ---
    total_est_income = sum(est_incomes.values())
    total_real_income = sum(real_incomes.values())
    total_est_expense = -sum(est_expenses.values())
    total_real_expense = sum(real_expenses.values())
    balance_diff = (total_real_income - abs(total_real_expense)) - (total_est_income - abs(total_est_expense))

    msg += "\n📌 Totals:\n"
    msg += f"Income: expected {total_est_income}, real {total_real_income}, diff {total_real_income - total_est_income}\n"
    msg += f"Expense: expected {total_est_expense}, real {total_real_expense}, diff {total_real_expense - total_est_expense}\n"
    msg += f"Balance difference (real - expected): {balance_diff}\n"

    await update.message.reply_text(msg)



# === Main ===
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setbalance", setbalance))
    app.add_handler(CommandHandler("setestimate", setestimate))
    app.add_handler(CommandHandler("setweekly", setweekly))
    app.add_handler(CommandHandler("showweekly", showweekly))
    app.add_handler(CommandHandler("currentweek", currentweek))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("showrecords", showrecords))
    app.add_handler(CommandHandler("weekstats", weekstats))


    app.run_polling()

if __name__ == "__main__":
    main()
