"""
Metadata Management Service
元数据管理服务 - 管理项目元数据和时间轴信息
"""

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProjectMetadata:
    """项目元数据"""
    
    VERSION = "1.0"
    
    def __init__(self, title: str = "Untitled Lecture", 
                 created_at: datetime = None):
        self.version = self.VERSION
        self.title = title
        self.created_at = created_at or datetime.now()
        self.audio_info: Dict[str, Any] = {}
        self.timeline_items: List[Dict[str, Any]] = []
        self.settings: Dict[str, Any] = {
            'transition_effect': 'fade',
            'transition_duration': 300,
            'video_resolution': '1920x1080',
            'fps': 30
        }
    
    def set_audio_info(self, filename: str, duration: float, 
                      format: str, sample_rate: int):
        """设置音频信息"""
        self.audio_info = {
            'filename': filename,
            'duration': duration,
            'format': format,
            'sample_rate': sample_rate
        }
    
    def add_timeline_item(self, timestamp: str, offset: float, 
                         photo: str, duration: float):
        """添加时间轴项"""
        self.timeline_items.append({
            'timestamp': timestamp,
            'offset': offset,
            'photo': photo,
            'duration': duration
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'version': self.version,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'audio': self.audio_info,
            'timeline': self.timeline_items,
            'settings': self.settings
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectMetadata':
        """从字典创建对象"""
        metadata = cls(
            title=data.get('title', 'Untitled Lecture'),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        )
        metadata.version = data.get('version', cls.VERSION)
        metadata.audio_info = data.get('audio', {})
        metadata.timeline_items = data.get('timeline', [])
        metadata.settings = data.get('settings', metadata.settings)
        return metadata
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ProjectMetadata':
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __repr__(self):
        return f"ProjectMetadata(title='{self.title}', items={len(self.timeline_items)})"


class MetadataService:
    """元数据管理服务"""
    
    METADATA_FILENAME = "metadata.json"
    
    @staticmethod
    def create_project_metadata(audio_file: Path, timeline_items: List[Dict[str, Any]],
                               audio_duration: float, title: str = None) -> ProjectMetadata:
        """
        创建项目元数据
        
        Args:
            audio_file: 音频文件路径
            timeline_items: 时间轴项列表
            audio_duration: 音频持续时间
            title: 项目标题
            
        Returns:
            ProjectMetadata对象
        """
        # 从音频文件名提取标题
        if title is None:
            title = audio_file.stem
        
        metadata = ProjectMetadata(title=title)
        
        # 设置音频信息
        metadata.set_audio_info(
            filename=audio_file.name,
            duration=audio_duration,
            format=audio_file.suffix.lstrip('.'),
            sample_rate=44100  # 默认值，实际应从AudioService获取
        )
        
        # 添加时间轴项
        for item in timeline_items:
            metadata.add_timeline_item(
                timestamp=item['timestamp'],
                offset=item['offset'],
                photo=item['photo'],
                duration=item['duration']
            )
        
        logger.info(f"Created project metadata: {metadata}")
        return metadata
    
    @staticmethod
    def save_metadata(metadata: ProjectMetadata, output_dir: Path):
        """
        保存元数据到文件
        
        Args:
            metadata: ProjectMetadata对象
            output_dir: 输出目录
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = output_dir / MetadataService.METADATA_FILENAME
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write(metadata.to_json())
        
        logger.info(f"Metadata saved to: {metadata_file}")
    
    @staticmethod
    def load_metadata(project_dir: Path) -> ProjectMetadata:
        """
        从文件加载元数据
        
        Args:
            project_dir: 项目目录
            
        Returns:
            ProjectMetadata对象
            
        Raises:
            FileNotFoundError: 元数据文件不存在
        """
        metadata_file = project_dir / MetadataService.METADATA_FILENAME
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = ProjectMetadata.from_json(f.read())
        
        logger.info(f"Metadata loaded from: {metadata_file}")
        return metadata
    
    @staticmethod
    def validate_metadata(metadata: ProjectMetadata) -> bool:
        """
        验证元数据是否有效
        
        Args:
            metadata: ProjectMetadata对象
            
        Returns:
            是否有效
        """
        # 检查必要字段
        if not metadata.audio_info:
            logger.error("Audio info is missing")
            return False
        
        if not metadata.audio_info.get('filename'):
            logger.error("Audio filename is missing")
            return False
        
        if metadata.audio_info.get('duration', 0) <= 0:
            logger.error("Invalid audio duration")
            return False
        
        # 检查时间轴
        if not metadata.timeline_items:
            logger.warning("No timeline items found")
        
        return True
