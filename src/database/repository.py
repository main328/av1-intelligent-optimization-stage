# /src/database/repository.py
import sqlite3
import uuid
from typing import Optional, Any, List, Dict

from src.core.logger import logger
from src.database.initializer import administrator
from src.core.router import Router

from src.model.contents import (
    VideoCodec, VideoCQ, VideoPreset, VideoCD, 
    AudioCodec, AudioBitrate,
    WorkPayload
)

class SeriesRepository:
    @classmethod
    def create_series(cls, title: str, video_codec: VideoCodec, video_cq: VideoCQ, video_preset: VideoPreset, video_cd: VideoCD, audio_codec: AudioCodec, audio_bitrate: AudioBitrate) -> Optional[str]:
        series_id: str = str(uuid.uuid4())
        try:
            with administrator.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO series (id, title, video_codec, video_cq, video_preset, video_cd, audio_codec, audio_bitrate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (series_id, title, video_codec.value, video_cq.value, video_preset.value, video_cd.value, audio_codec.value, audio_bitrate.value)
                )
                conn.commit()

                logger.info(f'새로운 미디어 시리즈 생성에 성공했습니다: {series_id}')
                return series_id

        except sqlite3.IntegrityError:
            logger.error(f'이미 존재하는 미디어 시리즈를 생성할 수 없습니다.: {title}')
            return None

        except Exception as error:
            logger.error(f'새로운 미디어 시리즈 생성 중 알 수 없는 오류가 발생했습니다: {error}')
            return None

    @classmethod
    def read_all_series(cls) -> List[Dict[str, Any]]:
        with administrator.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM series ORDER BY created_at DESC")

            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def update_series(cls, series_id: str, title: str, video_codec: VideoCodec, video_cq: VideoCQ, video_preset: VideoPreset, video_cd: VideoCD, audio_codec: AudioCodec, audio_bitrate: AudioBitrate) -> bool:
        try:
            with administrator.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE series
                    SET title = ?, video_codec = ?, video_cq = ?, video_preset = ?, video_cd = ?, audio_codec = ?, audio_bitrate = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (title, video_codec.value, video_cq.value, video_preset.value, video_cd.value, audio_codec.value, audio_bitrate.value, series_id)
                )
                conn.commit()

                logger.info(f'기존 미디어 시리즈 수정에 성공했습니다: {series_id}')
                return cursor.rowcount > 0

        except sqlite3.IntegrityError:
            logger.error(f'이미 존재하는 미디어 시리즈로 수정할 수 없습니다: {title}')
            return False

        except Exception as error:
            logger.error(f'기존 미디어 시리즈 수정 중 알 수 없는 오류가 발생했습니다: {error}')
            return False

    @classmethod
    def delete_series(cls, series_id: str) -> bool:
        try:
            with administrator.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM series WHERE id = ?", (series_id,))
                conn.commit()

                logger.info(f'기존 미디어 시리즈 삭제에 성공했습니다: {series_id}')
                return cursor.rowcount > 0

        except Exception as error:
            logger.error(f'기존 미디어 시리즈 삭제 중 알 수 없는 오류가 발생했습니다: {series_id}: {error}')
            return False


class MediaRepository:
    @classmethod
    def create_media_file(cls, series_id: str, season: int, episode: str, file_path: str, file_hash: str, output_path: str, video_type: str, media_type: str) -> Optional[str]:
        media_id: str = str(uuid.uuid4())

        try:
            with administrator.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO media_files (
                        id, season, episode, video_type, media_type, file_path, file_hash, output_path, status, progress, vmaf_scoring, par2_archive, series_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Ready', 0, 0.0, 0)
                """, (media_id, season, episode, video_type, media_type, file_path, file_hash, output_path, series_id)
                )
                conn.commit()

                logger.info(f'새로운 미디어 데이터 생성에 성공했습니다: {media_id}')
                return media_id

        except Exception as error:
            logger.error(f'새로운 미디어 데이터 생성 중 알 수 없는 오류가 발생했습니다: {error}')
            return None

    @classmethod
    def get_next_work_payload(cls) -> Optional[tuple[str, WorkPayload]]:
        with administrator.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    m.id as media_id, m.file_path, m.output_path, m.season, m.episode, m.video_type, m.media_type,
                    s.title, s.video_codec, s.video_cq, s.video_preset, s.video_cd, s.audio_codec, s.audio_bitrate
                FROM media_files m
                JOIN series s ON m.series_id = s.id
                WHERE m.status = 'Ready'
                ORDER BY m.created_at ASC
                LIMIT 1
            """)
            row = cursor.fetchone()

            if not row:
                return None

            payload = WorkPayload(
                input_path=row['file_path'],
                output_path=row['output_path'],
                video_codec=row['video_codec'],
                video_cq=row['video_cq'],
                video_preset=row['video_preset'],
                video_cd=row['video_cd'],
                audio_codec=row['audio_codec'],
                audio_bit=row['audio_bitrate'],
            )

            return row['media_id'], payload

    @classmethod
    def update_pipeline_status(cls, media_id: str, status: str, progress: int = 0) -> None:
        with administrator.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE media_files 
                SET status = ?, progress = ?
                WHERE id = ?
            """, (status, progress, media_id))
            conn.commit()

    @classmethod
    def complete_evaluation(cls, media_id: str, vmaf_score: float) -> None:
        with administrator.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE media_files 
                SET vmaf_scoring = ?
                WHERE id = ?
            """, (vmaf_score, media_id))
            conn.commit()

    @classmethod
    def complete_protection(cls, media_id: str) -> None:
        with administrator.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE media_files 
                SET par2_archive = 1, status = 'Completed', progress = 100
                WHERE id = ?
            """, (media_id,))
            conn.commit()

    @classmethod
    def get_dashboard_tasks(cls) -> List[Dict[str, Any]]:
        with administrator.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    m.id, m.season, m.episode, m.video_type, m.media_type, m.status, m.progress, m.vmaf_scoring, m.par2_archive, m.file_path, m.output_path,
                    s.title as series_title, s.video_codec, s.video_cq, s.video_preset, s.video_cd, s.audio_codec, s.audio_bitrate
                FROM media_files m
                JOIN series s ON m.series_id = s.id
                ORDER BY m.created_at DESC
            """)

            return [dict(row) for row in cursor.fetchall()]