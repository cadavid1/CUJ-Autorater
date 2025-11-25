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

        # CUJs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cujs (
                id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                expectation TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                observation TEXT,
                recommendation TEXT,
                cost REAL,
                raw_response TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

        # Settings table for app configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    # === CUJ Operations ===

    def save_cuj(self, cuj_id: str, task: str, expectation: str) -> bool:
        """Save or update a CUJ"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO cujs (id, task, expectation, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    task = excluded.task,
                    expectation = excluded.expectation,
                    updated_at = CURRENT_TIMESTAMP
            """, (cuj_id, task, expectation))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving CUJ: {e}")
            return False

    def get_cujs(self) -> pd.DataFrame:
        """Get all CUJs as DataFrame"""
        conn = self._get_connection()
        df = pd.read_sql_query("SELECT id, task, expectation FROM cujs ORDER BY created_at", conn)
        conn.close()
        return df

    def delete_cuj(self, cuj_id: str) -> bool:
        """Delete a CUJ"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cujs WHERE id = ?", (cuj_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting CUJ: {e}")
            return False

    def bulk_save_cujs(self, cujs_df: pd.DataFrame) -> bool:
        """Bulk save CUJs from DataFrame"""
        try:
            for _, row in cujs_df.iterrows():
                self.save_cuj(row['id'], row['task'], row['expectation'])
            return True
        except Exception as e:
            print(f"Error bulk saving CUJs: {e}")
            return False

    # === Video Operations ===

    def save_video(self, name: str, file_path: str, duration_seconds: float,
                   file_size_mb: float, resolution: str = "", description: str = "") -> int:
        """Save video metadata and return video ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO videos (name, file_path, status, description,
                                  duration_seconds, file_size_mb, resolution, source)
                VALUES (?, ?, 'ready', ?, ?, ?, ?, 'local')
            """, (name, file_path, description, duration_seconds, file_size_mb, resolution))

            video_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return video_id
        except Exception as e:
            print(f"Error saving video: {e}")
            return -1

    def save_drive_video(self, name: str, drive_file_id: str, drive_web_link: str,
                        file_path: str, duration_seconds: float, file_size_mb: float,
                        resolution: str = "", description: str = "") -> int:
        """Save Drive video metadata and return video ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO videos (name, file_path, drive_file_id, drive_web_link,
                                  source, status, description, duration_seconds,
                                  file_size_mb, resolution)
                VALUES (?, ?, ?, ?, 'drive', 'ready', ?, ?, ?, ?)
            """, (name, file_path, drive_file_id, drive_web_link, description,
                  duration_seconds, file_size_mb, resolution))

            video_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return video_id
        except Exception as e:
            print(f"Error saving Drive video: {e}")
            return -1

    def get_videos(self) -> pd.DataFrame:
        """Get all videos as DataFrame"""
        conn = self._get_connection()
        df = pd.read_sql_query("""
            SELECT id, name, file_path, status, description,
                   duration_seconds as duration, file_size_mb as size_mb,
                   resolution, uploaded_at
            FROM videos
            ORDER BY uploaded_at DESC
        """, conn)
        conn.close()
        return df

    def delete_video(self, video_id: int) -> bool:
        """Delete a video"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
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
                     raw_response: str = "") -> int:
        """Save analysis result and return analysis ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO analysis_results
                (cuj_id, video_id, model_used, status, friction_score,
                 observation, recommendation, cost, raw_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cuj_id, video_id, model_used, status, friction_score,
                  observation, recommendation, cost, raw_response))

            analysis_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return analysis_id
        except Exception as e:
            print(f"Error saving analysis: {e}")
            return -1

    def get_analysis_results(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Get analysis results as DataFrame"""
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
                ar.observation,
                ar.recommendation,
                ar.cost,
                ar.analyzed_at
            FROM analysis_results ar
            JOIN cujs c ON ar.cuj_id = c.id
            JOIN videos v ON ar.video_id = v.id
            ORDER BY ar.analyzed_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_latest_results(self) -> Dict:
        """Get latest analysis results as dictionary keyed by CUJ ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get most recent analysis for each CUJ
        cursor.execute("""
            SELECT
                ar.cuj_id,
                ar.video_id,
                v.name as video_name,
                ar.model_used,
                ar.status,
                ar.friction_score,
                ar.observation,
                ar.recommendation,
                ar.cost
            FROM analysis_results ar
            JOIN videos v ON ar.video_id = v.id
            WHERE ar.id IN (
                SELECT MAX(id)
                FROM analysis_results
                GROUP BY cuj_id
            )
        """)

        results = {}
        for row in cursor.fetchall():
            results[row['cuj_id']] = {
                'video_used': row['video_name'],
                'video_id': row['video_id'],
                'model_used': row['model_used'],
                'status': row['status'],
                'friction_score': row['friction_score'],
                'observation': row['observation'],
                'recommendation': row['recommendation'],
                'cost': row['cost']
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

    def save_setting(self, key: str, value: str) -> bool:
        """Save a setting"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving setting: {e}")
            return False

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting value"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()

            conn.close()
            return row['value'] if row else default
        except Exception as e:
            print(f"Error getting setting: {e}")
            return default

    # === Statistics ===

    def get_statistics(self) -> Dict:
        """Get overall statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total counts
        cursor.execute("SELECT COUNT(*) as count FROM cujs")
        total_cujs = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM videos")
        total_videos = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM analysis_results")
        total_analyses = cursor.fetchone()['count']

        # Total cost
        cursor.execute("SELECT SUM(cost) as total FROM analysis_results")
        total_cost = cursor.fetchone()['total'] or 0.0

        # Average friction score
        cursor.execute("SELECT AVG(friction_score) as avg FROM analysis_results")
        avg_friction = cursor.fetchone()['avg'] or 0.0

        # Pass/Fail/Partial counts
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM analysis_results
            GROUP BY status
        """)
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


# Singleton instance
_db_instance = None


def get_db() -> DatabaseManager:
    """Get singleton database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
