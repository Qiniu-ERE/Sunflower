"""
Timeline Synchronization Engine
根据文件创建时间，建立音频和照片的时间轴映射关系
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimelineItem:
    """时间轴项"""
    
    def __init__(self, timestamp: datetime, offset_seconds: float, 
                 file_path: Path, duration: float = 0.0):
        self.timestamp = timestamp
        self.offset_seconds = offset_seconds
        self.file_path = file_path
        self.duration = duration
        
    def __repr__(self):
        return f"TimelineItem(offset={self.offset_seconds:.2f}s, duration={self.duration:.2f}s, file={self.file_path.name})"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'offset_seconds': self.offset_seconds,
            'file_path': str(self.file_path),
            'duration': self.duration
        }


class Timeline:
    """时间轴管理器"""
    
    def __init__(self, audio_start_time: datetime, audio_duration: float):
        self.audio_start_time = audio_start_time
        self.audio_duration = audio_duration
        self.items: List[TimelineItem] = []
        
    def add_item(self, item: TimelineItem):
        """添加时间轴项"""
        self.items.append(item)
        
    def sort_items(self):
        """按时间排序"""
        self.items.sort(key=lambda x: x.offset_seconds)
        
    def calculate_durations(self):
        """计算每个项的持续时间"""
        for i in range(len(self.items) - 1):
            self.items[i].duration = self.items[i + 1].offset_seconds - self.items[i].offset_seconds
        
        # 最后一个项持续到音频结束
        if self.items:
            self.items[-1].duration = self.audio_duration - self.items[-1].offset_seconds
            
    def get_current_item(self, current_time: float) -> Optional[TimelineItem]:
        """
        获取当前时间对应的时间轴项
        
        Args:
            current_time: 当前播放时间（秒）
            
        Returns:
            对应的TimelineItem或None
        """
        # 二分查找优化
        if not self.items:
            return None
            
        # 如果在第一张照片之前，返回None
        if current_time < self.items[0].offset_seconds:
            return None
            
        # 反向遍历查找（通常查找最近的）
        for item in reversed(self.items):
            if current_time >= item.offset_seconds:
                return item
                
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于JSON序列化"""
        return {
            'audio_start_time': self.audio_start_time.isoformat(),
            'audio_duration': self.audio_duration,
            'items': [item.to_dict() for item in self.items]
        }
    
    def __repr__(self):
        return f"Timeline(start={self.audio_start_time}, duration={self.audio_duration:.2f}s, items={len(self.items)})"


class TimelineSync:
    """时间轴同步引擎"""
    
    TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    @classmethod
    def parse_timestamp(cls, filename: str) -> datetime:
        """
        从文件名解析时间戳
        
        Args:
            filename: 文件名，格式为 "YYYY-MM-DD hh:mm:ss.ext"
            
        Returns:
            datetime对象
            
        Raises:
            ValueError: 如果文件名格式不正确
        """
        try:
            # 移除文件扩展名
            name_without_ext = Path(filename).stem
            # 解析时间戳
            timestamp = datetime.strptime(name_without_ext, cls.TIMESTAMP_FORMAT)
            return timestamp
        except ValueError as e:
            raise ValueError(f"Invalid filename format: {filename}. Expected format: YYYY-MM-DD hh:mm:ss.ext") from e
    
    @classmethod
    def build_timeline(cls, audio_file: Path, photo_files: List[Path], 
                       audio_duration: float) -> Timeline:
        """
        构建时间轴
        
        Args:
            audio_file: 音频文件路径
            photo_files: 照片文件路径列表
            audio_duration: 音频持续时间（秒）
            
        Returns:
            Timeline对象
        """
        logger.info(f"Building timeline for audio: {audio_file.name}")
        
        # 解析音频开始时间
        audio_start_time = cls.parse_timestamp(audio_file.name)
        
        # 创建时间轴
        timeline = Timeline(audio_start_time, audio_duration)
        
        # 处理每张照片
        for photo_file in photo_files:
            try:
                # 解析照片时间戳
                photo_time = cls.parse_timestamp(photo_file.name)
                
                # 计算相对偏移（秒）
                offset_seconds = (photo_time - audio_start_time).total_seconds()
                
                # 创建时间轴项
                item = TimelineItem(
                    timestamp=photo_time,
                    offset_seconds=offset_seconds,
                    file_path=photo_file
                )
                
                # 只添加在音频时间范围内的照片
                if 0 <= offset_seconds <= audio_duration:
                    timeline.add_item(item)
                    logger.info(f"Added photo: {photo_file.name} at offset {offset_seconds:.2f}s")
                else:
                    logger.warning(f"Photo {photo_file.name} is outside audio timeline (offset: {offset_seconds:.2f}s)")
                    
            except ValueError as e:
                logger.error(f"Skipping invalid photo file: {photo_file.name} - {e}")
                continue
        
        # 排序并计算持续时间
        timeline.sort_items()
        timeline.calculate_durations()
        
        logger.info(f"Timeline built successfully: {len(timeline.items)} photos")
        
        return timeline
    
    @classmethod
    def validate_files(cls, audio_file: Path, photo_files: List[Path]) -> bool:
        """
        验证文件名格式
        
        Args:
            audio_file: 音频文件路径
            photo_files: 照片文件路径列表
            
        Returns:
            是否所有文件名格式正确
        """
        try:
            # 验证音频文件
            cls.parse_timestamp(audio_file.name)
            
            # 验证照片文件
            for photo_file in photo_files:
                cls.parse_timestamp(photo_file.name)
                
            return True
        except ValueError:
            return False
