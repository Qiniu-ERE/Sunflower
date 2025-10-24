"""
Audio Processing Service
音频处理服务 - 提取音频元数据和处理音频文件
"""

from pathlib import Path
from typing import Dict, Any, Optional
import logging
import subprocess
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioMetadata:
    """音频元数据"""
    
    def __init__(self, file_path: Path, duration: float, sample_rate: int,
                 channels: int, codec: str, bitrate: Optional[int] = None):
        self.file_path = file_path
        self.duration = duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.codec = codec
        self.bitrate = bitrate
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'file_path': str(self.file_path),
            'filename': self.file_path.name,
            'duration': self.duration,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'codec': self.codec,
            'bitrate': self.bitrate
        }
    
    def __repr__(self):
        return f"AudioMetadata(file={self.file_path.name}, duration={self.duration:.2f}s, codec={self.codec})"


class AudioService:
    """音频处理服务"""
    
    @staticmethod
    def get_metadata(audio_file: Path) -> AudioMetadata:
        """
        提取音频元数据
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            AudioMetadata对象
            
        Raises:
            FileNotFoundError: 文件不存在
            RuntimeError: 无法提取元数据
        """
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        
        logger.info(f"Extracting metadata from: {audio_file.name}")
        
        try:
            # 使用 ffprobe 提取元数据
            metadata = AudioService._extract_with_ffprobe(audio_file)
            return metadata
        except Exception as e:
            logger.warning(f"ffprobe failed, trying fallback method: {e}")
            # 如果 ffprobe 失败，尝试使用 Python 库
            try:
                metadata = AudioService._extract_with_python(audio_file)
                return metadata
            except Exception as e2:
                raise RuntimeError(f"Failed to extract audio metadata: {e2}") from e2
    
    @staticmethod
    def _extract_with_ffprobe(audio_file: Path) -> AudioMetadata:
        """
        使用 ffprobe 提取元数据（推荐方法）
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            AudioMetadata对象
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(audio_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # 提取音频流信息
        audio_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_stream = stream
                break
        
        if not audio_stream:
            raise RuntimeError("No audio stream found in file")
        
        # 提取格式信息
        format_info = data.get('format', {})
        
        metadata = AudioMetadata(
            file_path=audio_file,
            duration=float(format_info.get('duration', 0)),
            sample_rate=int(audio_stream.get('sample_rate', 44100)),
            channels=int(audio_stream.get('channels', 2)),
            codec=audio_stream.get('codec_name', 'unknown'),
            bitrate=int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None
        )
        
        logger.info(f"Metadata extracted: {metadata}")
        return metadata
    
    @staticmethod
    def _extract_with_python(audio_file: Path) -> AudioMetadata:
        """
        使用 Python 库提取元数据（fallback方法）
        需要安装: pip install mutagen
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            AudioMetadata对象
        """
        try:
            from mutagen import File
            from mutagen.mp3 import MP3
            
            audio = File(audio_file)
            
            if audio is None:
                raise RuntimeError("Unsupported audio format")
            
            # 获取基本信息
            duration = audio.info.length if hasattr(audio.info, 'length') else 0
            sample_rate = audio.info.sample_rate if hasattr(audio.info, 'sample_rate') else 44100
            channels = audio.info.channels if hasattr(audio.info, 'channels') else 2
            
            # 尝试获取比特率
            bitrate = None
            if hasattr(audio.info, 'bitrate'):
                bitrate = audio.info.bitrate
            
            # 检测编解码器
            codec = 'unknown'
            if isinstance(audio, MP3):
                codec = 'mp3'
            elif hasattr(audio, 'mime'):
                codec = audio.mime[0].split('/')[-1]
            
            metadata = AudioMetadata(
                file_path=audio_file,
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                codec=codec,
                bitrate=bitrate
            )
            
            logger.info(f"Metadata extracted (Python): {metadata}")
            return metadata
            
        except ImportError:
            raise RuntimeError("Mutagen library not installed. Install with: pip install mutagen")
    
    @staticmethod
    def validate_audio_file(audio_file: Path) -> bool:
        """
        验证音频文件是否有效
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            文件是否有效
        """
        if not audio_file.exists():
            logger.error(f"Audio file does not exist: {audio_file}")
            return False
        
        # 检查文件扩展名
        valid_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}
        if audio_file.suffix.lower() not in valid_extensions:
            logger.warning(f"Unsupported audio format: {audio_file.suffix}")
            return False
        
        # 尝试提取元数据来验证文件
        try:
            metadata = AudioService.get_metadata(audio_file)
            if metadata.duration <= 0:
                logger.error(f"Invalid audio duration: {metadata.duration}")
                return False
            return True
        except Exception as e:
            logger.error(f"Audio validation failed: {e}")
            return False
    
    @staticmethod
    def get_duration(audio_file: Path) -> float:
        """
        获取音频持续时间（快捷方法）
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            持续时间（秒）
        """
        metadata = AudioService.get_metadata(audio_file)
        return metadata.duration
