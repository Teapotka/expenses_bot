from config import db
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import datetime

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

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:   # normal command
        target = update.message
    elif update.callback_query:  # from button
        target = update.callback_query.message
    else:
        return
    
    settings = db.settings.find_one({"_id": "settings"})
    if not settings:
        await target.reply_text("⚠️ No initial balance set. Use /setbalance <amount> first.")
        return
    
    initial_balance = settings.get("initial_balance", 0)
    today = datetime.date.today()
    year, week, _ = today.isocalendar()
    current_year_week = f"{year}-{week:02d}"

    # --- Step 1: sum all real records up to today
    real_records = list(db.records.find())
    real_total = sum(r["amount"] for r in real_records)
    current_balance = initial_balance + real_total

    msg = f"💵 Current balance: {current_balance}\n\n"

    # --- Step 2: projection for next 4 weeks
    weeks_to_show = 4
    projected_balance = current_balance
    for i in range(weeks_to_show):
        future_date = today + datetime.timedelta(weeks=i)
        y, w, _ = future_date.isocalendar()
        yw = f"{y}-{w:02d}"

        est_doc = db.week_estimates.find_one({"_id": yw})
        expected_incomes = sum(est_doc.get("expected_incomes", {}).values()) if est_doc else 0
        expected_expenses = sum(est_doc.get("expected_expenses", {}).values()) if est_doc else 0
        expected_net = expected_incomes - expected_expenses

        # real records for that week (if already added)
        real_week_records = list(db.records.find({"year": y, "week": w}))
        real_net = sum(r["amount"] for r in real_week_records)

        # use real if available, else estimates
        if real_week_records:
            delta = real_net
            note = "real"
        else:
            delta = expected_net
            note = "est"
        
        projected_balance += delta
        msg += f"Week {yw}: change {delta} ({note}), balance → {projected_balance}\n"

    await target.reply_text(msg)
