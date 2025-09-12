from sqlalchemy import Column, String, Integer, text, create_engine
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from loguru import logger

from utils.db_api.db import DB

db = DB("sqlite:///files/wallets.db")
db.add_column_to_table("wallets", "top", "Integer", 0)
db.add_column_to_table("wallets", "discord_token", "String", None)
db.add_column_to_table("wallets", "discord_proxy", "String", None)
db.add_column_to_table("wallets", "discord_status", "String", "OK")
db.add_column_to_table("wallets", "discord_connected", "BOOL", False)
