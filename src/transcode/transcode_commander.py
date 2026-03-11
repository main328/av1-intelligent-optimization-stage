# /src/transcode/transcode_commander.py
from pathlib import Path

from src.model.contents import (
    VideoCodec, VideoCQ, VideoPreset, VideoCD,
    AudioCodec, AudioBitrate
)

class TranscodeCommander:
    def __init__(self, bin_file_path: Path) -> None:
        self._bin_file_path_str: str = str(bin_file_path)
        self._global_args: list[str] = []
        self._track_maps: list[str] = []
        self._video_args: list[str] = []
        self._audio_args: list[str] = []

    def setup_global_args(self, select_gpu: int) -> 'TranscodeCommander':
        self._global_args.extend([
            "-y",
            "-hide_banner",
            "-loglevel", "info",
            "-hwaccel", "cuda",
            "-hwaccel_device", str(select_gpu)
        ])

        return self

    def setup_media_track(self, media_index: int, stream_type: str, stream_index: int) -> 'TranscodeCommander':
        self._track_maps.extend([
            "-map", f"{media_index}:{stream_type}:{stream_index}"
        ])

        return self

    def exclude_subtitles(self) -> 'TranscodeCommander':
        self._track_maps.append("-sn")

        return self

    def setup_video_encoder(self, select_gpu: int, select_codec: VideoCodec, select_cq: VideoCQ, select_preset: VideoPreset, select_cd: VideoCD) -> 'TranscodeCommander':
        self._video_args.extend([
            "-c:v", select_codec.value,
            "-gpu", str(select_gpu),
            "-cq", select_cq.value,
            "-preset", select_preset.value,
            "-pix_fmt", select_cd.value
        ])

        return self

    def setup_audio_encoder(self, select_codec: AudioCodec, select_bitrate: AudioBitrate) -> 'TranscodeCommander':
        self._audio_args.extend([
            "-c:a", select_codec.value,
            "-b:a", select_bitrate.value
        ])

        return self

    def build_extract_command(self, input_file_path_str: str) -> list[str]:
        if not input_file_path_str:
            raise ValueError('입력 파일의 경로는 필수입니다.')

        cmd: list[str] = []
        cmd.append(self._bin_file_path_str)
        cmd.extend(["-v", "quiet"])
        cmd.extend(["-print_format", "json"])
        cmd.append("-show_format")
        cmd.append("-show_streams")
        cmd.append(input_file_path_str)

        return cmd

    def build_convert_command(self, input_file_path_str: str, output_file_path_str: str) -> list[str]:
        if not input_file_path_str:
            raise ValueError('입력 파일의 경로는 필수입니다.')

        if not output_file_path_str:
            raise ValueError('출력 파일의 경로는 필수입니다.')

        cmd: list[str] = []
        cmd.append(self._bin_file_path_str)
        cmd.extend(self._global_args)
        cmd.extend(["-i", input_file_path_str])
        cmd.extend(self._track_maps)
        cmd.extend(self._video_args)
        cmd.extend(self._audio_args)
        cmd.append(output_file_path_str)

        return cmd

    def build_vmaf_command(self, original_file_path_str: str, transcoded_file_path_str: str) -> list[str]:
        if not original_file_path_str:
            raise ValueError('원본 파일의 경로는 필수입니다.')

        if not transcoded_file_path_str:
            raise ValueError('변환 파일의 경로는 필수입니다.')

        cmd: list[str] = []
        cmd.append(self._bin_file_path_str)
        cmd.extend(["-i", original_file_path_str])
        cmd.extend(["-i", transcoded_file_path_str])
        cmd.extend(["-lavfi", "[1:v:0]setpts=PTS-STARTPTS[dist];[0:v:0]setpts=PTS-STARTPTS[ref];[dist][ref]libvmaf"])
        cmd.extend(["-f", "null", "-"])

        return  cmd