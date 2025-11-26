"""
Database storage layer for UXR CUJ Analysis
Handles persistent storage of CUJs, videos, and analysis results
"""

import sqlite3
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from config import DATABASE_PATH, EXPORT_STORAGE_PATH


class DatabaseManager:
    """Manages SQLite database operations"""

    def __init__(self, db_path: str = DATABASE_PATH):
        """Initialize database manager"""
        self.db_path = db_path
        self._ensure_database_directory()
        self._init_database()

    def _ensure_database_directory(self):
        """Create database directory if it doesn't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def _init_database(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)

        # CUJs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cujs (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                expectation TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                file_path TEXT,
                drive_id TEXT,
                drive_file_id TEXT,
                drive_web_link TEXT,
                source TEXT DEFAULT 'local',
                status TEXT DEFAULT 'ready',
                description TEXT,
                duration_seconds REAL,
                file_size_mb REAL,
                resolution TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Analysis Results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cuj_id TEXT NOT NULL,
                video_id INTEGER NOT NULL,
                model_used TEXT NOT NULL,
                status TEXT,
                friction_score INTEGER,
                confidence_score INTEGER,
                observation TEXT,
                recommendation TEXT,
                key_moments TEXT,
                cost REAL,
                raw_response TEXT,
                human_verified BOOLEAN DEFAULT 0,
                human_override_status TEXT,
                human_override_friction INTEGER,
                human_notes TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP,
                FOREIGN KEY (cuj_id) REFERENCES cujs(id),
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        """)

        # Analysis Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                total_cost REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Settings table for app configuration (per-user settings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Migration: Add new columns to existing databases
        self._migrate_analysis_results_table(cursor)
        self._migrate_to_multiuser(cursor)

        conn.commit()
        conn.close()

    def _migrate_analysis_results_table(self, cursor):
        """Add new columns to analysis_results table if they don't exist"""
        # Get existing columns
        cursor.execute("PRAGMA table_info(analysis_results)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Add missing columns
        migrations = [
            ("confidence_score", "ALTER TABLE analysis_results ADD COLUMN confidence_score INTEGER"),
            ("key_moments", "ALTER TABLE analysis_results ADD COLUMN key_moments TEXT"),
            ("human_verified", "ALTER TABLE analysis_results ADD COLUMN human_verified BOOLEAN DEFAULT 0"),
            ("human_override_status", "ALTER TABLE analysis_results ADD COLUMN human_override_status TEXT"),
            ("human_override_friction", "ALTER TABLE analysis_results ADD COLUMN human_override_friction INTEGER"),
            ("human_notes", "ALTER TABLE analysis_results ADD COLUMN human_notes TEXT"),
            ("verified_at", "ALTER TABLE analysis_results ADD COLUMN verified_at TIMESTAMP")
        ]

        for column_name, migration_sql in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(migration_sql)
                    print(f"Added column: {column_name}")
                except Exception as e:
                    print(f"Migration warning for {column_name}: {e}")

    def _migrate_to_multiuser(self, cursor):
        """Migrate existing single-user database to multi-user structure"""
        # Check if users table has any users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()[0]

        # Check if cujs table has user_id column
        cursor.execute("PRAGMA table_info(cujs)")
        cujs_columns = {row[1] for row in cursor.fetchall()}

        if 'user_id' not in cujs_columns:
            print("Migrating cujs table to multi-user...")
            # Add user_id column
            cursor.execute("ALTER TABLE cujs ADD COLUMN user_id INTEGER")

            # Only assign existing data to default user if there are users
            if user_count > 0:
                cursor.execute("SELECT id FROM users LIMIT 1")
                default_user_id = cursor.fetchone()[0]
                cursor.execute("UPDATE cujs SET user_id = ? WHERE user_id IS NULL", (default_user_id,))

        # Check if videos table has user_id column
        cursor.execute("PRAGMA table_info(videos)")
        videos_columns = {row[1] for row in cursor.fetchall()}

        if 'user_id' not in videos_columns:
            print("Migrating videos table to multi-user...")
            cursor.execute("ALTER TABLE videos ADD COLUMN user_id INTEGER")

            # Only assign existing data to default user if there are users
            if user_count > 0:
                cursor.execute("SELECT id FROM users LIMIT 1")
                default_user_id = cursor.fetchone()[0]
                cursor.execute("UPDATE videos SET user_id = ? WHERE user_id IS NULL", (default_user_id,))

        # Migrate settings table to per-user settings
        cursor.execute("PRAGMA table_info(settings)")
        settings_columns = {row[1] for row in cursor.fetchall()}

        if 'user_id' not in settings_columns and 'id' not in settings_columns:
            print("Migrating settings table to multi-user...")

            # Get existing settings before dropping table
            cursor.execute("SELECT key, value FROM settings")
            old_settings = cursor.fetchall()

            # Drop and recreate settings table with new schema
            cursor.execute("DROP TABLE settings")
            cursor.execute("""
                CREATE TABLE settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Restore settings for default user if there are users
            if user_count > 0 and old_settings:
                cursor.execute("SELECT id FROM users LIMIT 1")
                default_user_id = cursor.fetchone()[0]

                for key, value in old_settings:
                    cursor.execute("""
                        INSERT INTO settings (user_id, key, value)
                        VALUES (?, ?, ?)
                    """, (default_user_id, key, value))

    # === User Management ===

    def create_user(self, email: str, username: str, password_hash: str, full_name: str = "") -> Optional[int]:
        """Create a new user and return user ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO users (email, username, password_hash, full_name)
                VALUES (?, ?, ?, ?)
            """, (email, username, password_hash, full_name))

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except sqlite3.IntegrityError as e:
            print(f"User creation failed: {e}")
            return None
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, email, username, password_hash, full_name, created_at, last_login
                FROM users
                WHERE username = ?
            """, (username,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'id': row['id'],
                    'email': row['email'],
                    'username': row['username'],
                    'password_hash': row['password_hash'],
                    'full_name': row['full_name'],
                    'created_at': row['created_at'],
                    'last_login': row['last_login']
                }
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, email, username, password_hash, full_name, created_at, last_login
                FROM users
                WHERE email = ?
            """, (email,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'id': row['id'],
                    'email': row['email'],
                    'username': row['username'],
                    'password_hash': row['password_hash'],
                    'full_name': row['full_name'],
                    'created_at': row['created_at'],
                    'last_login': row['last_login']
                }
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating last login: {e}")
            return False

    def get_all_users(self) -> List[Dict]:
        """Get all users (admin function)"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, email, username, full_name, created_at, last_login
                FROM users
                ORDER BY created_at DESC
            """)

            users = []
            for row in cursor.fetchall():
                users.append({
                    'id': row['id'],
                    'email': row['email'],
                    'username': row['username'],
                    'full_name': row['full_name'],
                    'created_at': row['created_at'],
                    'last_login': row['last_login']
                })

            conn.close()
            return users
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []

    # === CUJ Operations ===

    def save_cuj(self, user_id: int, cuj_id: str, task: str, expectation: str) -> bool:
        """Save or update a CUJ for a specific user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO cujs (id, user_id, task, expectation, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    task = excluded.task,
                    expectation = excluded.expectation,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (cuj_id, user_id, task, expectation, user_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving CUJ: {e}")
            return False

    def get_cujs(self, user_id: int) -> pd.DataFrame:
        """Get all CUJs for a specific user as DataFrame"""
        conn = self._get_connection()
        df = pd.read_sql_query(
            "SELECT id, task, expectation FROM cujs WHERE user_id = ? ORDER BY created_at",
            conn,
            params=(user_id,)
        )
        conn.close()
        return df

    def delete_cuj(self, user_id: int, cuj_id: str) -> bool:
        """Delete a CUJ for a specific user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cujs WHERE id = ? AND user_id = ?", (cuj_id, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting CUJ: {e}")
            return False

    def bulk_save_cujs(self, user_id: int, cujs_df: pd.DataFrame) -> bool:
        """Bulk save CUJs from DataFrame for a specific user"""
        try:
            saved_count = 0
            skipped_count = 0

            for _, row in cujs_df.iterrows():
                # Validate required fields are not None, NaN, or empty
                cuj_id = row.get('id')
                task = row.get('task')
                expectation = row.get('expectation')

                # Check if any required field is None, NaN, or empty string
                if pd.isna(cuj_id) or pd.isna(task) or pd.isna(expectation):
                    skipped_count += 1
                    continue

                if not str(cuj_id).strip() or not str(task).strip() or not str(expectation).strip():
                    skipped_count += 1
                    continue

                self.save_cuj(user_id, str(cuj_id).strip(), str(task).strip(), str(expectation).strip())
                saved_count += 1

            if skipped_count > 0:
                print(f"Skipped {skipped_count} CUJ(s) with missing required fields (id, task, or expectation)")

            return True
        except Exception as e:
            print(f"Error bulk saving CUJs: {e}")
            return False

    # === Video Operations ===

    def save_video(self, user_id: int, name: str, file_path: str, duration_seconds: float,
                   file_size_mb: float, resolution: str = "", description: str = "") -> int:
        """Save video metadata for a specific user and return video ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO videos (user_id, name, file_path, status, description,
                                  duration_seconds, file_size_mb, resolution, source)
                VALUES (?, ?, ?, 'ready', ?, ?, ?, ?, 'local')
            """, (user_id, name, file_path, description, duration_seconds, file_size_mb, resolution))

            video_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return video_id
        except Exception as e:
            print(f"Error saving video: {e}")
            return -1

    def save_drive_video(self, user_id: int, name: str, drive_file_id: str, drive_web_link: str,
                        file_path: str, duration_seconds: float, file_size_mb: float,
                        resolution: str = "", description: str = "") -> int:
        """Save Drive video metadata for a specific user and return video ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO videos (user_id, name, file_path, drive_file_id, drive_web_link,
                                  source, status, description, duration_seconds,
                                  file_size_mb, resolution)
                VALUES (?, ?, ?, ?, ?, 'drive', 'ready', ?, ?, ?, ?)
            """, (user_id, name, file_path, drive_file_id, drive_web_link, description,
                  duration_seconds, file_size_mb, resolution))

            video_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return video_id
        except Exception as e:
            print(f"Error saving Drive video: {e}")
            return -1

    def get_videos(self, user_id: int) -> pd.DataFrame:
        """Get all videos for a specific user as DataFrame"""
        conn = self._get_connection()
        df = pd.read_sql_query("""
            SELECT id, name, file_path, status, description,
                   duration_seconds as duration, file_size_mb as size_mb,
                   resolution, uploaded_at
            FROM videos
            WHERE user_id = ?
            ORDER BY uploaded_at DESC
        """, conn, params=(user_id,))
        conn.close()
        return df

    def delete_video(self, user_id: int, video_id: int) -> bool:
        """Delete a video for a specific user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM videos WHERE id = ? AND user_id = ?", (video_id, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting video: {e}")
            return False

    def bulk_save_videos(self, videos_df: pd.DataFrame) -> bool:
        """Bulk save videos from DataFrame"""
        try:
            for _, row in videos_df.iterrows():
                if row.get('file_path') and pd.notna(row.get('file_path')):
                    self.save_video(
                        row['name'],
                        row['file_path'],
                        row.get('duration', 0),
                        row.get('size_mb', 0),
                        row.get('description', ''),
                        row.get('description', '')
                    )
            return True
        except Exception as e:
            print(f"Error bulk saving videos: {e}")
            return False

    # === Analysis Results Operations ===

    def save_analysis(self, cuj_id: str, video_id: int, model_used: str,
                     status: str, friction_score: int, observation: str,
                     recommendation: str, cost: float = 0.0,
                     raw_response: str = "", confidence_score: int = None,
                     key_moments: str = None) -> int:
        """Save analysis result and return analysis ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO analysis_results
                (cuj_id, video_id, model_used, status, friction_score, confidence_score,
                 observation, recommendation, key_moments, cost, raw_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cuj_id, video_id, model_used, status, friction_score, confidence_score,
                  observation, recommendation, key_moments, cost, raw_response))

            analysis_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return analysis_id
        except Exception as e:
            print(f"Error saving analysis: {e}")
            return -1

    def get_analysis_results(self, user_id: int, limit: Optional[int] = None) -> pd.DataFrame:
        """Get analysis results for a specific user as DataFrame"""
        conn = self._get_connection()

        query = """
            SELECT
                ar.id,
                ar.cuj_id,
                c.task as cuj_task,
                ar.video_id,
                v.name as video_name,
                ar.model_used,
                ar.status,
                ar.friction_score,
                ar.confidence_score,
                ar.observation,
                ar.recommendation,
                ar.key_moments,
                ar.cost,
                ar.human_verified,
                ar.human_override_status,
                ar.human_override_friction,
                ar.human_notes,
                ar.analyzed_at,
                ar.verified_at
            FROM analysis_results ar
            JOIN cujs c ON ar.cuj_id = c.id
            JOIN videos v ON ar.video_id = v.id
            WHERE c.user_id = ?
            ORDER BY ar.analyzed_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        df = pd.read_sql_query(query, conn, params=(user_id,))
        conn.close()
        return df

    def get_latest_results(self, user_id: int) -> Dict:
        """Get latest analysis results for a specific user as dictionary keyed by CUJ ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get most recent analysis for each CUJ belonging to the user
        cursor.execute("""
            SELECT
                ar.id,
                ar.cuj_id,
                ar.video_id,
                v.name as video_name,
                v.file_path as video_path,
                ar.model_used,
                ar.status,
                ar.friction_score,
                ar.confidence_score,
                ar.observation,
                ar.recommendation,
                ar.key_moments,
                ar.cost,
                ar.human_verified,
                ar.human_override_status,
                ar.human_override_friction,
                ar.human_notes
            FROM analysis_results ar
            JOIN videos v ON ar.video_id = v.id
            JOIN cujs c ON ar.cuj_id = c.id
            WHERE c.user_id = ? AND ar.id IN (
                SELECT MAX(ar2.id)
                FROM analysis_results ar2
                JOIN cujs c2 ON ar2.cuj_id = c2.id
                WHERE c2.user_id = ?
                GROUP BY ar2.cuj_id
            )
        """, (user_id, user_id))

        results = {}
        for row in cursor.fetchall():
            results[row['cuj_id']] = {
                'analysis_id': row['id'],
                'video_used': row['video_name'],
                'video_id': row['video_id'],
                'video_path': row['video_path'],
                'model_used': row['model_used'],
                'status': row['status'],
                'friction_score': row['friction_score'],
                'confidence_score': row['confidence_score'],
                'observation': row['observation'],
                'recommendation': row['recommendation'],
                'key_moments': row['key_moments'],
                'cost': row['cost'],
                'human_verified': row['human_verified'],
                'human_override_status': row['human_override_status'],
                'human_override_friction': row['human_override_friction'],
                'human_notes': row['human_notes']
            }

        conn.close()
        return results

    def delete_analysis_results(self, cuj_id: str = None, video_id: int = None) -> bool:
        """Delete analysis results by CUJ or video"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if cuj_id:
                cursor.execute("DELETE FROM analysis_results WHERE cuj_id = ?", (cuj_id,))
            elif video_id:
                cursor.execute("DELETE FROM analysis_results WHERE video_id = ?", (video_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting analysis results: {e}")
            return False

    def verify_analysis(self, analysis_id: int, override_status: str = None,
                       override_friction: int = None, notes: str = "") -> bool:
        """
        Mark an analysis as human-verified with optional overrides

        Args:
            analysis_id: ID of the analysis to verify
            override_status: Optional human override for status (Pass/Fail/Partial)
            override_friction: Optional human override for friction score (1-5)
            notes: Human notes about the verification

        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE analysis_results
                SET human_verified = 1,
                    human_override_status = ?,
                    human_override_friction = ?,
                    human_notes = ?,
                    verified_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (override_status, override_friction, notes, analysis_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error verifying analysis: {e}")
            return False

    # === Export Operations ===

    def export_results_to_csv(self, filename: str = None) -> str:
        """Export analysis results to CSV"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_results_{timestamp}.csv"

        Path(EXPORT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
        filepath = Path(EXPORT_STORAGE_PATH) / filename

        df = self.get_analysis_results()
        df.to_csv(filepath, index=False)

        return str(filepath)

    def export_results_to_json(self, filename: str = None) -> str:
        """Export analysis results to JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_results_{timestamp}.json"

        Path(EXPORT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
        filepath = Path(EXPORT_STORAGE_PATH) / filename

        df = self.get_analysis_results()
        df.to_json(filepath, orient='records', indent=2, date_format='iso')

        return str(filepath)

    # === Session Management ===

    def create_session(self, name: str = None) -> int:
        """Create a new analysis session"""
        if not name:
            name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("INSERT INTO sessions (name) VALUES (?)", (name,))
            session_id = cursor.lastrowid

            conn.commit()
            conn.close()
            return session_id
        except Exception as e:
            print(f"Error creating session: {e}")
            return -1

    def complete_session(self, session_id: int, total_cost: float):
        """Mark session as completed"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE sessions
                SET total_cost = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (total_cost, session_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error completing session: {e}")
            return False

    # === Settings Management ===

    def save_setting(self, user_id: int, key: str, value: str) -> bool:
        """Save a setting for a specific user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO settings (user_id, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, key, value))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving setting: {e}")
            return False

    def get_setting(self, user_id: int, key: str, default: str = None) -> Optional[str]:
        """Get a setting value for a specific user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM settings WHERE user_id = ? AND key = ?", (user_id, key))
            row = cursor.fetchone()

            conn.close()
            return row['value'] if row else default
        except Exception as e:
            print(f"Error getting setting: {e}")
            return default

    # === Statistics ===

    def get_statistics(self, user_id: int) -> Dict:
        """Get statistics for a specific user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total counts for this user
        cursor.execute("SELECT COUNT(*) as count FROM cujs WHERE user_id = ?", (user_id,))
        total_cujs = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM videos WHERE user_id = ?", (user_id,))
        total_videos = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count
            FROM analysis_results ar
            JOIN cujs c ON ar.cuj_id = c.id
            JOIN videos v ON ar.video_id = v.id
            WHERE c.user_id = ?
        """, (user_id,))
        total_analyses = cursor.fetchone()['count']

        # Total cost (only for this user's analyses)
        cursor.execute("""
            SELECT SUM(ar.cost) as total
            FROM analysis_results ar
            JOIN cujs c ON ar.cuj_id = c.id
            JOIN videos v ON ar.video_id = v.id
            WHERE c.user_id = ?
        """, (user_id,))
        total_cost = cursor.fetchone()['total'] or 0.0

        # Average friction score (only for this user)
        cursor.execute("""
            SELECT AVG(ar.friction_score) as avg
            FROM analysis_results ar
            JOIN cujs c ON ar.cuj_id = c.id
            JOIN videos v ON ar.video_id = v.id
            WHERE c.user_id = ?
        """, (user_id,))
        avg_friction = cursor.fetchone()['avg'] or 0.0

        # Pass/Fail/Partial counts (only for this user)
        cursor.execute("""
            SELECT ar.status, COUNT(*) as count
            FROM analysis_results ar
            JOIN cujs c ON ar.cuj_id = c.id
            JOIN videos v ON ar.video_id = v.id
            WHERE c.user_id = ?
            GROUP BY ar.status
        """, (user_id,))
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}

        conn.close()

        return {
            'total_cujs': total_cujs,
            'total_videos': total_videos,
            'total_analyses': total_analyses,
            'total_cost': total_cost,
            'avg_friction_score': avg_friction,
            'status_counts': status_counts
        }

    def get_cost_history(self, user_id: int, days: int = 30) -> List[Dict]:
        """Get daily cost aggregations for a specific user for charting

        Args:
            user_id: User ID to filter by
            days: Number of days to look back (default 30)

        Returns:
            List of dicts with 'date' and 'cost' keys, ordered chronologically
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                DATE(ar.analyzed_at) as date,
                SUM(ar.cost) as daily_cost
            FROM analysis_results ar
            JOIN cujs c ON ar.cuj_id = c.id
            WHERE c.user_id = ? AND ar.analyzed_at >= DATE('now', '-' || ? || ' days')
            GROUP BY DATE(ar.analyzed_at)
            ORDER BY date ASC
        """, (user_id, days))

        results = cursor.fetchall()
        conn.close()

        # Convert to list of dicts
        cost_history = [
            {'date': row['date'], 'cost': row['daily_cost'] or 0.0}
            for row in results
        ]

        return cost_history


# Singleton instance
_db_instance = None


def get_db() -> DatabaseManager:
    """Get singleton database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
