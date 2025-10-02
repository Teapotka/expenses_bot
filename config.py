import os
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram.ext import Application

load_dotenv()

DB_NAME = "expenses"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsAllowInvalidCertificates=False
)
db = client[DB_NAME]

# Collections
settings = db["settings"]
records = db["records"]
week_estimates = db["week_estimates"]
