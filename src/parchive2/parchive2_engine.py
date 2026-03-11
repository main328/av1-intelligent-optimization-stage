# /src/parchive2/parchive2_engine.py
import re
import time
from pathlib import Path
from typing import Callable, Optional
from subprocess import Popen, PIPE, STDOUT

from src.core.config import settings
from src.core.logger import logger
from src.core.engine import Engine
from src.parchive2.parchive2_commander import Parchive2Commander
from src.model.contents import Par2Config

class Parchive2Engine(Engine):
    def __init__(self) -> None:
        super().__init__()
        self.bin_par2: Path = self._find_binary('par2', settings.PARCHIVE2_EXE)

    def engine_run(self, par2_config: Par2Config, progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        process: Optional[Popen[str]] = None

        try:
            commander: Parchive2Commander = Parchive2Commander(self.bin_par2)
            input_file_path: Path = Path(par2_config.input_path).resolve()
            output_file_path: Path = Path(par2_config.output_path).resolve()
            base_file_path: Path = input_file_path.parent

            cmd: list[str] = commander.build_create_command(
                input_file_path_str=str(input_file_path), 
                output_file_path_str=str(output_file_path), 
                redundancy=par2_config.redundancy,
                base_file_path_str=str(base_file_path)
            )

            process = Popen(
                args=cmd,
                stdout=PIPE,
                stderr=STDOUT,
                creationflags=settings.CREATE_NO_CONSOLE,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            self._link_regist_subprocess(process)

            error_buffer: list[str] = []

            while True:
                if self._cancel_event and self._cancel_event.is_set():
                    logger.info('PAR2 작업 취소 신호를 감지하여 프로세스를 중단합니다.')
                    process.kill()
                    break

                line: str = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.strip()
                    error_buffer.append(line)

                    if len(error_buffer) > 20:
                        error_buffer.pop(0)

                    match: Optional[re.Match[str]] = re.search(r'(\d+(?:\.\d+)?)%', line)

                    if match and progress_callback:
                        try:
                            percent: int = int(float(match.group(1)))
                            progress_callback(min(max(percent, 0), 100))

                        except Exception as error:
                            logger.debug(f'PAR2 진행률 파싱 중 알 수 없는 오류가 발생했습니다: {error}')

            process.wait()

            if self._cancel_event and self._cancel_event.is_set():
                time.sleep(0.5)
                tmp_file_path_cancel: Path = Path(par2_config.output_path)

                for file in tmp_file_path_cancel.parent.glob(f"{tmp_file_path_cancel.stem}*"):
                    try:
                        if file.exists():
                            file.unlink()

                    except Exception as error:
                        logger.debug(f'취소된 분할 파일 롤백 중 알 수 없는 오류가 발생했습니다: {error}')

                return False

            if process.returncode == 0:
                logger.info(f'PAR2 복구 데이터 생성에 성공했습니다: {Path(par2_config.output_path).parent}')
                return True

            else:
                logger.error(f'PAR2 복구 데이터 생성에 실패했습니다: {process.returncode}: {Path(par2_config.input_path)}: {error_buffer}')

                try:
                    tmp_file_path_error: Path = Path(par2_config.output_path)
                    time.sleep(0.5)

                    for file in tmp_file_path_error.parent.glob(f"{tmp_file_path_error.stem}*"):
                        if file.exists():
                            file.unlink()

                except PermissionError as error:
                    logger.error(f'잔여 파일의 제거 권한이 없습니다: {error}')
                return False

        except Exception as error:
            logger.error(f'PAR2 복구 데이터 생성 중 알 수 없는 오류가 발생했습니다: {error}')
            return False

        finally:
            self._safe_subprocess_kill(process)