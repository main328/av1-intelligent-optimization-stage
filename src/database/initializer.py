# /src/database/init_db.py
import sqlite3
from threading import Lock, local
from pathlib import Path
from typing import Optional

from src.core.config import settings
from src.core.logger import logger

class Initializer:
    _instance: Optional['Initializer'] = None
    _instance_lock: Lock = Lock()
    _instance_local: local = local()

    def __new__(cls) -> 'Initializer':
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(Initializer, cls).__new__(cls)
                cls._instance._setup()

        return cls._instance

    def _setup(self) -> None:
        self.db_file_path: Path = settings.DATA_PATH / 'aios.db'
        self._init_tables()

    def _cleanup_crashed_tasks(self, conn: sqlite3.Connection) -> None:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT output_path
                FROM media_files
                WHERE status IN ('Encoding', 'Evaluating', 'Protecting')
            """)
            crashed_tasks = cursor.fetchall()

            for task in crashed_tasks:
                if task['output_path']:
                    target_file_path = Path(task['output_path'])
                    tmp_file_path: Path = target_file_path.with_name(target_file_path.name + settings.TMP_FILE_EXT)

                    if tmp_file_path.exists():
                        try:
                            tmp_file_path.unlink()
                            logger.info(f'비정상 종료를 감지하여 임시로 생성된 파일 제거에 성공했습니다: {tmp_file_path}')

                        except OSError as error:
                            logger.error(f'비정상 종료를 감지하여 임시로 생성된 파일 제거 중 알 수 없는 오류가 발생했습니다: {tmp_file_path}: {error}')

            cursor.execute("""
                UPDATE media_files 
                SET status = 'Ready', progress = 0 
                WHERE status IN ('Encoding', 'Evaluating', 'Protecting')
            """)
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f'비정상 종료를 감지하여 {cursor.rowcount}개 작업을 대기 상태로 초기화합니다.')

        except Exception as error:
            logger.error(f'비정상 종료를 감지하여 작업을 대기 상태로 초기화 중 알 수 없는 오류가 발생했습니다: {error}')

    def get_connection(self) -> sqlite3.Connection:
        if hasattr(self._instance_local, 'conn'):
            try:
                self._instance_local.conn.execute("SELECT 1")
                return self._instance_local.conn

            except sqlite3.ProgrammingError:
                pass

        conn = sqlite3.connect(database=self.db_file_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row

        conn.execute('PRAGMA foreign_keys = ON;')
        conn.execute('PRAGMA journal_mode = WAL;')
        conn.execute('PRAGMA synchronous = NORMAL;')

        self._instance_local.conn = conn
        return conn

    def _init_tables(self) -> None:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS series (
                        id TEXT PRIMARY KEY,
                        title TEXT UNIQUE NOT NULL,
                        video_codec TEXT,
                        video_cq TEXT,
                        video_preset TEXT,
                        video_cd TEXT,
                        audio_codec TEXT,
                        audio_bitrate TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS media_files (
                        id TEXT PRIMARY KEY,
                        season INTEGER,
                        episode TEXT,
                        file_hash TEXT,
                        file_path TEXT,
                        output_path TEXT,
                        video_type TEXT,
                        media_type TEXT,
                        status TEXT,
                        progress INTEGER,
                        vmaf_scoring REAL,
                        par2_archive BOOLEAN,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        series_id TEXT NOT NULL,
                        FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE CASCADE
                    )
                """)

                conn.commit()
                logger.info(f'데이터베이스 초기화 및 테이블 생성에 성공했습니다: {self.db_file_path}')

                self._cleanup_crashed_tasks(conn)

        except Exception as error:
            logger.critical(f'데이터베이스 초기화 및 테이블 생성에 실패했습니다: {error}')
            raise

administrator = Initializer()