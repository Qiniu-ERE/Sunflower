"""
Lecture Video Composer - Main Orchestrator
演讲视频合成器 - 主控制器，整合所有核心功能
"""

import sys
from pathlib import Path
from typing import List, Optional
import logging

# 添加项目路径到系统路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from core.timeline.timeline_sync import TimelineSync, Timeline
from services.audio.audio_service import AudioService, AudioMetadata
from services.image.image_service import ImageService, ImageMetadata
from services.metadata.metadata_service import MetadataService, ProjectMetadata
from services.video.video_exporter import VideoExporter, VideoExportConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LectureComposer:
    """演讲视频合成器主类"""
    
    def __init__(self, audio_file: Path, photo_files: List[Path], 
                 output_dir: Optional[Path] = None):
        """
        初始化合成器
        
        Args:
            audio_file: 音频文件路径
            photo_files: 照片文件路径列表
            output_dir: 输出目录（可选）
        """
        self.audio_file = audio_file
        self.photo_files = sorted(photo_files)  # 按文件名排序
        self.output_dir = output_dir or Path.cwd() / "output"
        
        self.audio_metadata: Optional[AudioMetadata] = None
        self.photo_metadata: List[ImageMetadata] = []
        self.timeline: Optional[Timeline] = None
        self.project_metadata: Optional[ProjectMetadata] = None
        
        logger.info(f"Initialized LectureComposer with {len(photo_files)} photos")
    
    def validate_inputs(self) -> bool:
        """
        验证输入文件
        
        Returns:
            是否所有文件都有效
        """
        logger.info("Validating input files...")
        
        # 验证音频文件
        if not AudioService.validate_audio_file(self.audio_file):
            logger.error(f"Invalid audio file: {self.audio_file}")
            return False
        
        # 验证照片文件
        invalid_photos = []
        for photo in self.photo_files:
            if not ImageService.validate_image_file(photo):
                invalid_photos.append(photo)
        
        if invalid_photos:
            logger.error(f"Invalid photo files: {invalid_photos}")
            return False
        
        # 验证文件名格式
        if not TimelineSync.validate_files(self.audio_file, self.photo_files):
            logger.error("File naming format validation failed")
            return False
        
        logger.info("All input files validated successfully")
        return True
    
    def extract_metadata(self):
        """提取所有文件的元数据"""
        logger.info("Extracting metadata from files...")
        
        # 提取音频元数据
        self.audio_metadata = AudioService.get_metadata(self.audio_file)
        logger.info(f"Audio metadata: {self.audio_metadata}")
        
        # 提取照片元数据
        self.photo_metadata = []
        for photo in self.photo_files:
            metadata = ImageService.get_metadata(photo)
            self.photo_metadata.append(metadata)
            logger.info(f"Photo metadata: {metadata}")
        
        logger.info(f"Extracted metadata from {len(self.photo_metadata)} photos")
    
    def build_timeline(self) -> Timeline:
        """
        构建时间轴
        
        Returns:
            Timeline对象
        """
        logger.info("Building timeline...")
        
        if self.audio_metadata is None:
            raise RuntimeError("Audio metadata not extracted. Call extract_metadata() first.")
        
        # 构建时间轴
        self.timeline = TimelineSync.build_timeline(
            audio_file=self.audio_file,
            photo_files=self.photo_files,
            audio_duration=self.audio_metadata.duration
        )
        
        # 打印时间轴详情
        logger.info(f"Timeline: {self.timeline}")
        for item in self.timeline.items:
            logger.info(f"  {item}")
        
        return self.timeline
    
    def create_project_metadata(self, title: Optional[str] = None) -> ProjectMetadata:
        """
        创建项目元数据
        
        Args:
            title: 项目标题（可选）
            
        Returns:
            ProjectMetadata对象
        """
        logger.info("Creating project metadata...")
        
        if self.timeline is None:
            raise RuntimeError("Timeline not built. Call build_timeline() first.")
        
        # 转换时间轴项为字典格式
        timeline_items = []
        for item in self.timeline.items:
            timeline_items.append({
                'timestamp': item.timestamp.isoformat(),
                'offset': item.offset_seconds,
                'photo': item.file_path.name,
                'duration': item.duration
            })
        
        # 创建项目元数据
        self.project_metadata = MetadataService.create_project_metadata(
            audio_file=self.audio_file,
            timeline_items=timeline_items,
            audio_duration=self.audio_metadata.duration,
            title=title
        )
        
        logger.info(f"Project metadata created: {self.project_metadata}")
        return self.project_metadata
    
    def save_project(self):
        """保存项目文件和元数据"""
        logger.info(f"Saving project to: {self.output_dir}")
        
        if self.project_metadata is None:
            raise RuntimeError("Project metadata not created. Call create_project_metadata() first.")
        
        # 创建输出目录结构
        audio_dir = self.output_dir / "audio"
        photos_dir = self.output_dir / "photos"
        audio_dir.mkdir(parents=True, exist_ok=True)
        photos_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制音频文件
        import shutil
        audio_dest = audio_dir / self.audio_file.name
        shutil.copy2(self.audio_file, audio_dest)
        logger.info(f"Copied audio file to: {audio_dest}")
        
        # 复制照片文件
        for photo in self.photo_files:
            photo_dest = photos_dir / photo.name
            shutil.copy2(photo, photo_dest)
            logger.info(f"Copied photo file to: {photo_dest}")
        
        # 保存元数据
        MetadataService.save_metadata(self.project_metadata, self.output_dir)
        
        logger.info("Project saved successfully")
    
    def process(self, title: Optional[str] = None, save: bool = True) -> ProjectMetadata:
        """
        完整处理流程
        
        Args:
            title: 项目标题（可选）
            save: 是否保存项目文件
            
        Returns:
            ProjectMetadata对象
        """
        logger.info("=" * 60)
        logger.info("Starting lecture composition process...")
        logger.info("=" * 60)
        
        # 1. 验证输入
        if not self.validate_inputs():
            raise RuntimeError("Input validation failed")
        
        # 2. 提取元数据
        self.extract_metadata()
        
        # 3. 构建时间轴
        self.build_timeline()
        
        # 4. 创建项目元数据
        self.create_project_metadata(title=title)
        
        # 5. 保存项目（可选）
        if save:
            self.save_project()
        
        logger.info("=" * 60)
        logger.info("Lecture composition completed successfully!")
        logger.info("=" * 60)
        
        return self.project_metadata
    
    def export_video(self, output_file: Optional[Path] = None, 
                    config: Optional[VideoExportConfig] = None) -> Path:
        """
        导出视频文件
        
        Args:
            output_file: 输出视频文件路径（可选，默认为output_dir/video.mp4）
            config: 视频导出配置（可选，使用默认配置）
            
        Returns:
            生成的视频文件路径
        """
        logger.info("Starting video export...")
        
        if self.timeline is None:
            raise RuntimeError("Timeline not built. Call process() first.")
        
        if self.audio_metadata is None:
            raise RuntimeError("Audio metadata not extracted. Call process() first.")
        
        # 确定输出文件路径
        if output_file is None:
            output_file = self.output_dir / "video.mp4"
        
        # 创建视频导出器
        exporter = VideoExporter(config)
        
        # 准备时间轴数据
        timeline_items = []
        for item in self.timeline.items:
            timeline_items.append({
                'photo': item.file_path.name,
                'duration': item.duration,
                'offset': item.offset_seconds
            })
        
        # 导出视频
        video_file = exporter.export_video(
            audio_file=self.output_dir / "audio" / self.audio_file.name,
            timeline_items=timeline_items,
            photos_dir=self.output_dir / "photos",
            output_file=output_file,
            audio_duration=self.audio_metadata.duration
        )
        
        logger.info(f"Video exported successfully: {video_file}")
        
        # 获取视频信息
        video_info = exporter.get_video_info(video_file)
        logger.info(f"Video info: {video_info}")
        
        return video_file
    
    def get_summary(self) -> str:
        """
        获取处理摘要
        
        Returns:
            摘要字符串
        """
        if self.timeline is None:
            return "No timeline built yet"
        
        summary = f"""
========================================
Lecture Composition Summary
========================================
Audio File: {self.audio_file.name}
Audio Duration: {self.audio_metadata.duration:.2f} seconds ({self.audio_metadata.duration/60:.1f} minutes)
Total Photos: {len(self.photo_files)}
Timeline Items: {len(self.timeline.items)}

Timeline Details:
"""
        for i, item in enumerate(self.timeline.items, 1):
            summary += f"\n  {i}. {item.file_path.name}"
            summary += f"\n     Time: {item.offset_seconds:.2f}s - {item.offset_seconds + item.duration:.2f}s"
            summary += f"\n     Duration: {item.duration:.2f}s"
        
        summary += f"\n\nOutput Directory: {self.output_dir}\n"
        summary += "=" * 40
        
        return summary


def main():
    """主函数示例"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Lecture Video Composer - MVP Core')
    parser.add_argument('audio_file', type=Path, help='Audio file path')
    parser.add_argument('photo_dir', type=Path, help='Directory containing photos')
    parser.add_argument('-o', '--output', type=Path, help='Output directory', default=None)
    parser.add_argument('-t', '--title', type=str, help='Project title', default=None)
    parser.add_argument('--no-save', action='store_true', help='Do not save project files')
    parser.add_argument('--export-video', action='store_true', help='Export video file')
    parser.add_argument('--video-file', type=Path, help='Video output file path', default=None)
    parser.add_argument('--resolution', type=str, help='Video resolution (e.g., 1920x1080)', default='1920x1080')
    parser.add_argument('--fps', type=int, help='Video frame rate', default=30)
    parser.add_argument('--bitrate', type=str, help='Video bitrate (e.g., 5000k)', default='5000k')
    
    args = parser.parse_args()
    
    # 查找照片文件
    photo_files = sorted(args.photo_dir.glob('*.jpg')) + sorted(args.photo_dir.glob('*.jpeg'))
    
    if not photo_files:
        logger.error(f"No photo files found in: {args.photo_dir}")
        return 1
    
    # 创建合成器
    composer = LectureComposer(
        audio_file=args.audio_file,
        photo_files=photo_files,
        output_dir=args.output
    )
    
    try:
        # 执行处理
        metadata = composer.process(title=args.title, save=not args.no_save)
        
        # 打印摘要
        print(composer.get_summary())
        
        # 打印元数据JSON
        print("\nProject Metadata JSON:")
        print(metadata.to_json())
        
        # 导出视频（如果需要）
        if args.export_video:
            logger.info("\n" + "=" * 60)
            logger.info("Exporting video...")
            logger.info("=" * 60)
            
            config = VideoExportConfig(
                resolution=args.resolution,
                fps=args.fps,
                video_bitrate=args.bitrate
            )
            
            video_file = composer.export_video(
                output_file=args.video_file,
                config=config
            )
            
            print(f"\n✅ Video exported successfully: {video_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
