# /src/transcode/transcode_engine.py
import re
import json
import time
from pathlib import Path
from typing import Callable, Optional
from subprocess import Popen, PIPE, DEVNULL

from src.core.config import settings
from src.core.logger import logger
from src.core.engine import Engine
from src.model.contents import (
    VideoCodec, VideoCD, VideoPreset, VideoCQ,
    AudioCodec, AudioBitrate,
    TaskConfig, MediaInfo, safe_enum
)
from src.transcode.transcode_commander import TranscodeCommander

class TranscodeEngine(Engine):
    def __init__(self) -> None:
        super().__init__()
        self.bin_ffmpeg: Path = self._find_binary('ffmpeg', settings.TRANSCODE_EXE)
        self.bin_ffplay: Path = self._find_binary('ffplay', settings.TRANSCODE_EXE)
        self.bin_ffprobe: Path = self._find_binary('ffprobe', settings.TRANSCODE_EXE)

    def _get_media_info(self, input_file_path: Path) -> MediaInfo:
        if not input_file_path.exists():
            return {}

        process: Optional[Popen[str]] = None
        try:
            commander: TranscodeCommander = TranscodeCommander(self.bin_ffprobe)
            extract_cmd: list[str] = commander.build_extract_command(str(input_file_path))

            process = Popen(
                args=extract_cmd,
                stdout=PIPE,
                stderr=PIPE,
                creationflags=settings.CREATE_NO_CONSOLE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            self._link_regist_subprocess(process)
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                return json.loads(stdout)

            return {}

        except Exception as error:
            logger.error(f'메타 데이터 추출 중 알 수 없는 오류가 발생했습니다: {error}')
            return {}

        finally:
            self._safe_subprocess_kill(process)

    def _get_media_duration(self, input_file_path: Path) -> float:
        media_info: MediaInfo = self._get_media_info(input_file_path)

        try:
            return float(media_info.get("format", {}).get('duration', 0.0))

        except (ValueError, TypeError):
            return 0.0

    def _parse_progress(self, line: str, duration_sec: float, progress_callback: Optional[Callable[[int], None]]) -> None:
        match: Optional[re.Match[str]] = re.search(r'time=(\d{2}:\d{2}:\d{2}\.\d+)', line)

        if match:
            try:
                hours, minutes, seconds = match.group(1).split(':')
                current_sec: float = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                current_percent: int = int((current_sec / duration_sec) * 100)

                if progress_callback:
                    progress_callback(min(max(current_percent, 0), 100))

            except Exception as error:
                logger.error(f'진행률 파싱 중 알 수 없는 오류가 발생했습니다: {error}')

    def verify_vmaf_process(self, original_file_path_str: str, transcoded_file_path_str: str, progress_callback: Optional[Callable[[int], None]] = None) -> float:
        process: Optional[Popen[str]] = None

        try:
            commander: TranscodeCommander = TranscodeCommander(self.bin_ffmpeg)
            cmd: list[str] = commander.build_vmaf_command(original_file_path_str, transcoded_file_path_str)

            process = Popen(
                args=cmd,
                stdout=DEVNULL,
                stderr=PIPE,
                creationflags=settings.CREATE_NO_CONSOLE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            self._link_regist_subprocess(process)

            score: float = 0.0
            duration_sec: float = self._get_media_duration(Path(original_file_path_str))

            while True:
                if self._cancel_event and self._cancel_event.is_set():
                    process.kill()
                    break

                line: str = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.strip()
                    if 'time=' in line and duration_sec > 0:
                        self._parse_progress(line, duration_sec, progress_callback)

                    elif 'vmaf score' in line.lower():
                        match: Optional[re.Match[str]] = re.search(r'vmaf score:\s*([0-9.]+)', line, re.IGNORECASE)

                        if match:
                            score = float(match.group(1))

            process.wait()
            return score

        except Exception as error:
            logger.error(f'VMAF 품질 검증 중 알 수 없는 오류가 발생했습니다: {error}')
            return 0.0

        finally:
            self._safe_subprocess_kill(process)

    def engine_run(self, task_config: TaskConfig, progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        tmp_file_path_str: str = task_config.output_path + settings.TMP_FILE_EXT
        process: Optional[Popen[str]] = None

        try:
            commander: TranscodeCommander = TranscodeCommander(self.bin_ffmpeg)

            commander.setup_global_args(task_config.index)
            commander.setup_media_track(media_index=0, stream_type='v', stream_index=task_config.video_stream)
            commander.setup_media_track(media_index=0, stream_type='a', stream_index=task_config.audio_stream)
            commander.exclude_subtitles()

            video_codec: VideoCodec = safe_enum(VideoCodec, task_config.video_codec, VideoCodec.AV1_NVENC)
            video_cq: VideoCQ = safe_enum(VideoCQ, task_config.video_cq, VideoCQ.BALANCE)
            video_preset: VideoPreset = safe_enum(VideoPreset, task_config.video_preset, VideoPreset.BALANCE)
            video_cd: VideoCD = safe_enum(VideoCD, task_config.video_cd, VideoCD.CDBIT10)

            audio_codec: AudioCodec = safe_enum(AudioCodec, task_config.audio_codec, AudioCodec.OPUS)
            audio_bitrate: AudioBitrate = safe_enum(AudioBitrate, task_config.audio_bit, AudioBitrate.BALANCE)

            commander.setup_video_encoder(task_config.index, video_codec, video_cq, video_preset, video_cd)
            commander.setup_audio_encoder(audio_codec, audio_bitrate)

            cmd: list[str] = commander.build_convert_command(
                task_config.input_path, 
                tmp_file_path_str
            )

            process = Popen(
                args=cmd,
                stdout=DEVNULL,
                stderr=PIPE,
                creationflags=settings.CREATE_NO_CONSOLE,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            self._link_regist_subprocess(process)

            error_buffer: list[str] = []
            duration_sec: float = self._get_media_duration(Path(task_config.input_path))

            while True:
                if self._cancel_event and self._cancel_event.is_set():
                    logger.info(f'GPU{task_config.index}의 작업 취소 신호를 감지하여 프로세스를 중단합니다.')
                    process.kill()
                    break

                line: str = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.strip()
                    error_buffer.append(line)
                    if len(error_buffer) > 30:
                        error_buffer.pop(0)

                    if 'time=' in line and duration_sec > 0:
                        self._parse_progress(line, duration_sec, progress_callback)

            process.wait()

            if self._cancel_event and self._cancel_event.is_set():
                time.sleep(0.5)
                tmp_file: Path = Path(tmp_file_path_str)

                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)

                return False

            if process.returncode == 0:
                tmp_file_success: Path = Path(tmp_file_path_str)
                final_file: Path = Path(task_config.output_path)

                if tmp_file_success.exists():
                    tmp_file_success.replace(final_file)

                logger.info(f'GPU{task_config.index}가 파일 변환에 성공했습니다: {final_file}')
                return True

            else:
                logger.error(f'GPU{task_config.index} 파일 변환에 실패했습니다: {process.returncode}: {error_buffer}')

                try:
                    tmp_file_path: Path = Path(tmp_file_path_str)

                    if tmp_file_path.exists():
                        time.sleep(0.5)
                        tmp_file_path.unlink()

                except PermissionError as error:
                    logger.error(f'잔여 파일의 제거 권한이 없습니다: {error}')
                return False

        except Exception as error:
            logger.error(f'GPU{task_config.index} 파일 변환 중 알 수 없는 오류가 발생했습니다: {error}')
            return False

        finally:
            self._safe_subprocess_kill(process)