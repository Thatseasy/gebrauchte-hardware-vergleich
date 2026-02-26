import sqlite3
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "products.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Products table (Verified Listings)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS verified_listings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        price REAL,
                        link TEXT UNIQUE NOT NULL,
                        source TEXT,
                        canonical_name TEXT,
                        verification_status TEXT,
                        confidence_score REAL,
                        risk_flags TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Reference Hardware (Passmark/Spec Data)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reference_hardware (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        type TEXT NOT NULL,
                        score INTEGER,
                        socket TEXT,
                        memory_type TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")

    def add_listing(self, listing: Dict[str, Any]) -> bool:
        """Add a verified listing to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO verified_listings 
                    (title, price, link, source, canonical_name, verification_status, confidence_score, risk_flags, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    listing.get("title"),
                    listing.get("price"),
                    listing.get("link"),
                    listing.get("source"),
                    listing.get("canonical_name"),
                    listing.get("verification_status"),
                    listing.get("confidence_score"),
                    str(listing.get("risk_flags")), # Store list as string representation
                    datetime.now().isoformat()
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding listing: {e}")
            return False

    def check_listing_exists(self, link: str) -> bool:
        """Check if a listing already exists by link."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM verified_listings WHERE link = ?", (link,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking listing: {e}")
            return False

    def get_all_listings(self) -> List[Dict[str, Any]]:
        """Retrieve all verified listings."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM verified_listings ORDER BY timestamp DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error retrieving listings: {e}")
            return []

    # --- Reference Hardware Methods ---

    def save_reference_hardware(self, product: Dict[str, Any]) -> bool:
        """Save/Update reference hardware data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO reference_hardware 
                    (id, name, type, score, socket, memory_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    product.get("id"),
                    product.get("name"),
                    product.get("type"),
                    product.get("score"),
                    product.get("socket"),
                    product.get("memory_type"),
                    datetime.now().isoformat()
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error saving reference hardware: {e}")
            return False

    def get_reference_hardware(self, name_query: str) -> List[Dict[str, Any]]:
        """Find reference hardware by name."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Simple wildcard search
                cursor.execute("SELECT * FROM reference_hardware WHERE name LIKE ? ORDER BY score DESC", (f"%{name_query}%",))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error retrieving reference hardware: {e}")
            return []

    def get_similar_hardware(self, score: int, type_str: str, threshold_percent: float = 0.10) -> List[Dict[str, Any]]:
        """Find hardware with similar performance score (+/- threshold)."""
        try:
            min_score = score * (1 - threshold_percent)
            max_score = score * (1 + threshold_percent)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM reference_hardware 
                    WHERE type = ? AND score BETWEEN ? AND ?
                    ORDER BY score DESC
                """, (type_str, min_score, max_score))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error finding similar hardware: {e}")
            return []
