# /src/core/base_engine.py
import atexit
from pathlib import Path
from typing import Optional
from subprocess import Popen
from threading import Event, Lock

from src.core.config import settings
from src.core.logger import logger

class Engine:
    def __init__(self) -> None:
        self._threads_lock: Lock = Lock()
        self._subprocesses: list[Popen] = []
        self._cancel_event: Optional[Event] = None
        
        atexit.register(self._cleanup_subprocesses)

    def _find_binary(self, keyword: str, executables: list[str]) -> Path:
        for filename in executables:
            if keyword.lower() in filename.lower():
                target_file_path: Path = settings.BIN_PATH / filename

                if target_file_path.exists():
                    logger.info(f'바이너리 실행 파일이 존재합니다: {target_file_path}')
                    return target_file_path

        crit_msg: str = f'바이너리 실행 파일이 존재하지 않습니다: {keyword}'
        logger.critical(crit_msg)
        raise FileNotFoundError(crit_msg)

    def _link_regist_subprocess(self, subprocess: Popen) -> None:
        with self._threads_lock:
            self._subprocesses.append(subprocess)

    def _unlink_regist_subprocess(self, subprocess: Popen) -> None:
        with self._threads_lock:
            if subprocess in self._subprocesses:
                self._subprocesses.remove(subprocess)

    def _cleanup_subprocesses(self) -> None:
        with self._threads_lock:
            for subprocess in list(self._subprocesses):
                try:
                    if subprocess.poll() is None:
                        logger.info(f'서브프로세스 정리에 성공했습니다: SubprocessID({subprocess.pid})')
                        subprocess.kill()
                        subprocess.wait(timeout=2.0)

                except Exception as error:
                    logger.error(f'서브프로세스 정리 중 알 수 없는 오류가 발생했습니다: {error}')

            self._subprocesses.clear()
            logger.info('모든 서브프로세스 정리에 성공했습니다.')

    def _safe_subprocess_kill(self, subprocess: Optional[Popen]) -> None:
        if not subprocess:
            return

        try:
            if subprocess.poll() is None:
                subprocess.kill()
                subprocess.wait(timeout=2.0)

        except Exception as error:
            logger.error(f'서브프로세스 종료 중 알 수 없는 오류가 발생했습니다: {error}')

        self._unlink_regist_subprocess(subprocess)