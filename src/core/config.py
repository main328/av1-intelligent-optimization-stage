# /src/core/config.py
import os
import sys
from pathlib import Path
from typing import Final
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / '.env', override=True)

class Config:
    APP_NAME: Final[str] = os.getenv('APP_TITLE', 'Please enter a title.')
    APP_VERS: Final[str] = os.getenv('APP_VERSION', 'Please enter a version.')
    APP_DESC: Final[str] = os.getenv('APP_DESCRIPTION', 'Please enter a description.')

    LOG_MAX_BYTE: Final[int] = 10 * 1024 * 1024
    BACKUP_FILES: Final[int] = 10

    TRANSCODE_URL: Final[str] = os.getenv('FFMPEG_URL', 'Please check a download link.')
    TRANSCODE_EXE: Final[list[str]] = ['ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe']
    PARCHIVE2_URL: Final[str] = os.getenv('PAR2_URL', 'Please check a download link.')
    PARCHIVE2_EXE: Final[list[str]] = ['par2.exe']
    INSTALLER_TRY: Final[int] = 3

    CREATE_NO_CONSOLE: Final[int] = 0x08000000 if sys.platform == 'win32' else 0

    LOWEST_SCORE: Final[float] = 80.0
    TMP_FILE_EXT: Final[str] = '.mkv.part'

    ROOT_PATH: Final[Path] = Path(__file__).parents[2]
    LOG_PATH: Final[Path] = ROOT_PATH / 'log'
    BIN_PATH: Final[Path] = ROOT_PATH / 'bin'
    DATA_PATH: Final[Path] = ROOT_PATH / 'data'
    ARCHIVE_PATH: Final[Path] = ROOT_PATH / 'archive'

    @classmethod
    def setup_directories(cls) -> None:
        directories: list[Path] = [
            cls.BIN_PATH,
            cls.LOG_PATH,
            cls.DATA_PATH,
            cls.ARCHIVE_PATH,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

settings: Config = Config()
settings.setup_directories()