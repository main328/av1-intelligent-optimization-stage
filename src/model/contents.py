# /src/model/contents.py
from enum import Enum
from typing import TypeVar, TypedDict, Any
from dataclasses import dataclass

ENUM_TYPE = TypeVar('ENUM_TYPE', bound=Enum)

def safe_enum(enum_class: type[ENUM_TYPE], enum_value: str, default_value: ENUM_TYPE) -> ENUM_TYPE:
    try:
        return enum_class(enum_value)
    
    except ValueError:
        return default_value

class VideoCodec(str, Enum):
    AV1_NVENC: str = 'av1_nvenc'

class VideoCQ(str, Enum):
    HIGHEST: str = '10'
    BALANCE: str = '30'
    COMPACT: str = '50'

class VideoPreset(str, Enum):
    FASTEST: str = 'p1'
    BALANCE: str = 'p3'
    SLOWEST: str = 'p5'

class VideoCD(str, Enum):
    CDBIT10: str = 'p010le'

class AudioCodec(str, Enum):
    OPUS: str = 'libopus'

class AudioBitrate(str, Enum):
    HIGHEST: str = '320k'
    BALANCE: str = '192k'
    COMPACT: str = '128k'

class ParityPercent(int, Enum):
    COMPACT: int = 5
    BALANCE: int = 10
    ARCHIVE: int = 15

class MediaFormat(TypedDict, total=False):
    duration: str
    bitrate: str
    format: str
    size: str

class MediaInfo(TypedDict, total=False):
    format: MediaFormat
    streams: list[dict[str, Any]]
    
@dataclass
class GPUstatus:
    index: int
    name: str
    tmp: int
    load: int
    vram: int
    vram_total: float
    vram_used: float
    vram_free: float

    @property
    def is_safe(self) -> bool:
        return self.tmp < 80 and self.load < 90

@dataclass
class TaskConfig:
    index: int
    input_path: str
    output_path: str
    video_codec: str
    video_cq: str
    video_preset: str
    video_cd: str
    audio_codec: str
    audio_bit: str
    video_stream: int
    audio_stream: int
    verify_vmaf: bool
    create_par2: bool

@dataclass
class WorkPayload:
    media_id: str
    input_path: str
    output_path: str
    video_codec: str = VideoCodec.AV1_NVENC.value
    video_cq: str = VideoCQ.BALANCE.value
    video_preset: str = VideoPreset.BALANCE.value
    video_cd: str = VideoCD.CDBIT10.value
    audio_codec: str = AudioCodec.OPUS.value
    audio_bit: str = AudioBitrate.BALANCE.value
    video_stream: int = 0
    audio_stream: int = 0
    redundancy: int = ParityPercent.COMPACT.value
    verify_vmaf: bool = True
    create_par2: bool = True

@dataclass
class Par2Config:
    input_path: str
    output_path: str
    redundancy: int