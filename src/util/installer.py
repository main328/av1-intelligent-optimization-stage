# /src/util/installer.py
import shutil
import zipfile
import requests
from pathlib import Path
from typing import Optional, Callable, Any

from src.core.config import settings
from src.core.logger import logger

class Installer:
    def __init__(self) -> None:
        self.dependencies: list[dict[str, Any]] = [
            {
                "name": "FFmpeg",
                "type": "zip",
                "link": settings.TRANSCODE_URL,
                "file": settings.TRANSCODE_EXE
            },
            {
                "name": "PAR2",
                "type": "zip",
                "link": settings.PARCHIVE2_URL,
                "file": settings.PARCHIVE2_EXE
            }
        ]

    def _organize_files(self, dependency: dict[str, Any]) -> None:
        target_files: list[str] = dependency["file"]

        for bin_file_path in settings.BIN_PATH.rglob('*'):
            if bin_file_path.exists() and bin_file_path.name in target_files:
                target_path: Path = settings.BIN_PATH / bin_file_path.name

                if bin_file_path.resolve() != target_path.resolve():
                    if target_path.exists():
                        target_path.unlink()

                    shutil.move(str(bin_file_path), str(target_path))

        for dir_path in settings.BIN_PATH.iterdir():
            if dir_path.is_dir():
                try:
                    shutil.rmtree(str(dir_path))

                except Exception as error:
                    logger.debug(f'하위 디렉토리 정리 중 알 수 없는 오류가 발생했습니다: {error}')

    def install_dependency(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        for dependency in self.dependencies:
            try:
                is_already_installed: bool = True

                for bin_file in dependency["file"]:
                    if not (settings.BIN_PATH / bin_file).exists():
                        is_already_installed = False
                        break
                
                if is_already_installed:
                    logger.info(f'{dependency["name"]} 바이너리 실행 파일은 이미 존재하여 다운로드를 제외합니다.')

                    if progress_callback:
                        progress_callback(100, f'{dependency["name"]} 준비 완료')

                    continue

                tmp_file_path: Path = settings.BIN_PATH / f'{dependency["name"]}.zip'

                if progress_callback:
                    progress_callback(0, f'{dependency["name"]} 다운로드 준비')

                retry_count: int = settings.INSTALLER_TRY

                for attmpt in range(retry_count):
                    try:
                        with requests.get(url=dependency["link"], stream=True, timeout=10) as response:
                            response.raise_for_status()
                            total_size: int = int(response.headers.get('content-length', 0))
                            wrote: int = 0
                            last_percent: int = -1

                            with open(file=tmp_file_path, mode='wb') as file:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        file.write(chunk)
                                        wrote += len(chunk)
                                        
                                        if progress_callback and total_size > 0:
                                            percent: int = int((wrote / total_size) * 100)

                                            if percent != last_percent:
                                                progress_callback(percent, f'{dependency["name"]} 다운로드 진행률: {percent}%')
                                                last_percent = percent

                        break

                    except Exception as error:
                        if attmpt == retry_count - 1:
                            raise error

                        logger.error(f'{dependency["name"]} 다운로드를 실패하여 재시도합니다 ({attmpt+1}/{retry_count}): {error}')
                
                logger.info(f'{dependency["name"]} 다운로드를 완료했습니다.')

                if progress_callback:
                    progress_callback(100, f'{dependency["name"]} 압축 해제 및 설치 중')
                
                with zipfile.ZipFile(file=tmp_file_path, mode='r') as zip_file:
                    for warn_path in zip_file.namelist():
                        bin_file_path: Path = (settings.BIN_PATH / warn_path).resolve()

                        if not str(bin_file_path).startswith(str(settings.BIN_PATH.resolve())):
                            raise Exception(f'압축 파일 내 안전하지 않은 경로를 발견했습니다: {warn_path}')
                    
                    zip_file.extractall(path=settings.BIN_PATH)
                
                self._organize_files(dependency)

                if tmp_file_path.exists():
                    tmp_file_path.unlink()
                
                logger.info(f'{dependency["name"]} 설치를 완료했습니다.')

            except Exception as error:
                logger.error(f'필수 의존성을 설치 중 알 수 없는 오류가 발생했습니다: {error}')
                
                try:
                    if 'tmp_file_path' in locals() and tmp_file_path.exists():
                        tmp_file_path.unlink()

                except Exception as inner_error:
                    logger.error(f'임시 파일 제거 중 알 수 없는 오류가 발생했습니다: {inner_error}')

                return False

        return True