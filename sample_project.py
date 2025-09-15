# Currency Converter Application
# A comprehensive currency converter with GUI, CLI, and API integration

import requests
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime, timedelta
import argparse
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ExchangeRate:
    """Data class for exchange rate information"""
    from_currency: str
    to_currency: str
    rate: float
    timestamp: datetime
    source: str = "API"

class CurrencyAPI:
    """Handler for currency exchange rate APIs"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        # Free API endpoints
        self.free_apis = [
            "https://open.er-api.com/v6/latest/",
            "https://api.exchangerate-api.com/v4/latest/"
        ]
        # Premium API with key
        self.premium_api = "https://v6.exchangerate-api.com/v6/"

    def get_exchange_rates(self, base_currency: str = "USD") -> Dict[str, float]:
        """Fetch current exchange rates"""

        # Try premium API first if we have a key
        if self.api_key:
            try:
                return self._fetch_premium_rates(base_currency)
            except Exception as e:
                logger.warning(f"Premium API failed: {e}, trying free APIs")

        # Try free APIs
        for api_url in self.free_apis:
            try:
                return self._fetch_free_rates(api_url, base_currency)
            except Exception as e:
                logger.warning(f"API {api_url} failed: {e}")
                continue

        # If all APIs fail, use fallback rates
        logger.error("All APIs failed, using fallback rates")
        return self._get_fallback_rates()

    def _fetch_premium_rates(self, base_currency: str) -> Dict[str, float]:
        """Fetch from premium API with key"""
        url = f"{self.premium_api}{self.api_key}/latest/{base_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get("result") == "success":
            return data["conversion_rates"]
        else:
            raise Exception(f"API error: {data.get('error-type', 'Unknown error')}")

    def _fetch_free_rates(self, api_url: str, base_currency: str) -> Dict[str, float]:
        """Fetch from free API"""
        url = f"{api_url}{base_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Handle different API response formats
        if "rates" in data:
            return data["rates"]
        elif "conversion_rates" in data:
            return data["conversion_rates"]
        else:
            raise Exception("Unexpected API response format")

    def _get_fallback_rates(self) -> Dict[str, float]:
        """Fallback exchange rates when APIs are unavailable"""
        return {
            "USD": 1.0, "EUR": 0.85, "GBP": 0.73, "JPY": 110.0,
            "AUD": 1.35, "CAD": 1.25, "CHF": 0.92, "CNY": 6.45,
            "ZAR": 15.5, "INR": 74.5, "BRL": 5.2, "RUB": 73.5,
            "KRW": 1180.0, "SGD": 1.35, "HKD": 7.8, "MXN": 20.5,
            "SEK": 8.6, "NOK": 8.9, "DKK": 6.4, "PLN": 3.9,
            "TRY": 8.5, "CZK": 22.0, "HUF": 300.0, "RON": 4.2
        }

class DatabaseManager:
    """Manages local SQLite database for caching and history"""

    def __init__(self, db_path: str = "currency_data.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Exchange rates cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exchange_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_currency TEXT NOT NULL,
                    target_currency TEXT NOT NULL,
                    rate REAL NOT NULL,
                    timestamp DATETIME NOT NULL,
                    source TEXT DEFAULT 'API'
                )
            ''')

            # Conversion history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversion_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_currency TEXT NOT NULL,
                    to_currency TEXT NOT NULL,
                    amount REAL NOT NULL,
                    converted_amount REAL NOT NULL,
                    exchange_rate REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Indexes for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_exchange_rates_currencies 
                ON exchange_rates(base_currency, target_currency)
            ''')

            conn.commit()
            logger.info("Database initialized successfully")

    def cache_exchange_rates(self, base_currency: str, rates: Dict[str, float]):
        """Cache exchange rates in database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.now()

            # Clear old rates
            one_hour_ago = timestamp - timedelta(hours=1)
            cursor.execute('''
                DELETE FROM exchange_rates 
                WHERE base_currency = ? AND timestamp < ?
            ''', (base_currency, one_hour_ago))

            # Insert new rates
            for currency, rate in rates.items():
                cursor.execute('''
                    INSERT INTO exchange_rates 
                    (base_currency, target_currency, rate, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (base_currency, currency, rate, timestamp))

            conn.commit()
            logger.info(f"Cached {len(rates)} exchange rates for {base_currency}")

    def get_cached_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get cached exchange rate if still valid (within 1 hour)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            one_hour_ago = datetime.now() - timedelta(hours=1)

            cursor.execute('''
                SELECT rate FROM exchange_rates 
                WHERE base_currency = ? AND target_currency = ? 
                AND timestamp > ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (from_currency, to_currency, one_hour_ago))

            result = cursor.fetchone()
            return result[0] if result else None

    def save_conversion(self, from_currency: str, to_currency: str,
                       amount: float, converted_amount: float, rate: float):
        """Save conversion to history"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversion_history 
                (from_currency, to_currency, amount, converted_amount, exchange_rate)
                VALUES (?, ?, ?, ?, ?)
            ''', (from_currency, to_currency, amount, converted_amount, rate))
            conn.commit()

    def get_conversion_history(self, limit: int = 20) -> List[Tuple]:
        """Get recent conversion history"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT from_currency, to_currency, amount, converted_amount, 
                       exchange_rate, timestamp
                FROM conversion_history 
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            return cursor.fetchall()

# --- CurrencyConverter, GUI, CLI classes stay unchanged except small fixes ---
# (Too long to paste in this single block — I’ll continue in the next message)

