# /src/core/logger.py
import sys
import logging
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler

from src.core.config import settings

class Logger:
    def __init__(self) -> None:
        if sys.platform == 'win32':
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')

        self._logger: logging.Logger = logging.getLogger('app')
        self._filename: str = 'aios.log'
        self._level: int = logging.INFO
        self._date_fmt: str = '%Y-%m-%d %H:%M:%S'
        self._log_fmt: str = '[%(asctime)s : %(levelname)s] [%(threadName)s : %(filename)s] (Line: %(lineno)d): %(message)s'

        self._logger.setLevel(self._level)
        self._logger.propagate = False

        self._formatter: Formatter = Formatter(
            fmt=self._log_fmt,
            datefmt=self._date_fmt,
        )

        if not self._logger.hasHandlers():
            self._add_stream_handler()
            self._add_file_handler()

    def _add_stream_handler(self) -> None:
        stream_handler: StreamHandler = StreamHandler(sys.stdout)
        stream_handler.setLevel(self._level)
        stream_handler.setFormatter(self._formatter)

        self._logger.addHandler(stream_handler)

    def _add_file_handler(self) -> None:
        file_handler: RotatingFileHandler = RotatingFileHandler(
            filename=settings.LOG_PATH / self._filename,
            maxBytes=settings.LOG_MAX_BYTE,
            backupCount=settings.BACKUP_FILES,
            encoding='utf-8'
        )
        file_handler.setLevel(self._level)
        file_handler.setFormatter(self._formatter)

        self._logger.addHandler(file_handler)

logger = Logger()._logger