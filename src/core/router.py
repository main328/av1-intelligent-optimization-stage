# /src/core/path_router.py
import os
import json
import uuid
from pathlib import Path
from typing import Optional, Any

from src.core.config import settings
from src.core.logger import logger

class Router:
    @classmethod
    def create_media_uuid(cls, series_id: str, season: int, video_type: str, media_type: str) -> str:
        media_uuid: str = f'{series_id}_{season}_{video_type}_{media_type}'.lower()

        return str(uuid.uuid5(uuid.NAMESPACE_OID, media_uuid))

    @classmethod
    def create_media_directory(cls, media_root_path: Path, series_id: str, season: int, video_type: str, media_type: str, media_id: str, extension: str) -> Path:
        media_uuid: str = cls.create_media_uuid(series_id, season, video_type, media_type)

        media_path: Path = media_root_path / media_uuid
        media_path.mkdir(parents=True, exist_ok=True)

        return media_path / f'{media_id}{extension}'

    @classmethod
    def create_recovery_directory(cls, series_id: str, season: int, video_type: str, media_type: str, media_id: str) -> Path:
        media_uuid: str = cls.create_media_uuid(series_id, season, video_type, media_type)
        
        recovery_path: Path = settings.ARCHIVE_PATH / media_uuid / media_id
        recovery_path.mkdir(parents=True, exist_ok=True)

        return recovery_path

    @classmethod
    def create_recovery_metadata(cls, series_id: str, season: int, video_type: str, media_type: str, media_id: str, metadata: dict[str, Any]) -> None:
        recovery_path: Path = cls.create_recovery_directory(series_id, season, video_type, media_type, media_id)
        metadata_file_path: Path = recovery_path / f'{media_id}.json'

        try:
            with open(metadata_file_path, 'w', encoding='utf-8') as file:
                json.dump(metadata, file, ensure_ascii=False, indent=4)

            logger.info(f'미디어 파일 복구를 위한 메타 데이터 생성에 성공했습니다: {metadata_file_path}')

        except Exception as error:
            logger.error(f'미디어 파일 복구를 위한 메타 데이터 생성 중 알 수 없는 오류가 발생했습니다: {metadata_file_path}: {error}')

    @classmethod
    def create_media_network(cls, media_file_path: Path, media_link_path: Path) -> Optional[Path]:
        media_link_path.parent.mkdir(parents=True, exist_ok=True)

        if media_link_path.exists():
            media_link_path.unlink()

        try:
            os.link(media_file_path, media_link_path)
            logger.info(f'미디어 라이브러리의 하드 링크 생성에 성공했습니다: {media_link_path}')
            return media_link_path

        except Exception as error:
            logger.error(f'미디어 라이브러리의 하드 링크 생성 중 알 수 없는 오류가 발생했습니다: {media_file_path}: {error}')
            return None

    @classmethod
    def recover_media_metadata(cls) -> list[dict[str, Any]]:
        recover_metadatas: list[dict[str, Any]] = []

        if not settings.ARCHIVE_PATH.exists():
            return recover_metadatas

        for metadata in settings.ARCHIVE_PATH.rglob('*.json'):
            try:
                with open(metadata, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    data['media_id'] = metadata.stem
                    recover_metadatas.append(data)

            except Exception as error:
                logger.error(f'미디어의 메타 데이터 탐색 중 알 수 없는 오류가 발생했습니다: {metadata}: {error}')
                continue
        
        logger.info(f'미디어의 메타 데이터 {len(recover_metadatas)}개 탐색에 성공했습니다.')
        return recover_metadatas