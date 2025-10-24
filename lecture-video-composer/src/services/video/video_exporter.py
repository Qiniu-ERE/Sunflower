"""
Video Exporter Service
视频导出服务 - 使用FFmpeg将音频和照片序列合成为视频文件
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class VideoExportConfig:
    """视频导出配置"""
    resolution: str = "1920x1080"  # 视频分辨率
    fps: int = 30  # 帧率
    video_codec: str = "libx264"  # 视频编码器
    audio_codec: str = "aac"  # 音频编码器
    video_bitrate: str = "5000k"  # 视频比特率
    audio_bitrate: str = "192k"  # 音频比特率
    pixel_format: str = "yuv420p"  # 像素格式 (兼容性最好)
    preset: str = "medium"  # 编码速度预设 (ultrafast, fast, medium, slow, veryslow)
    crf: int = 23  # 恒定质量因子 (0-51, 越小质量越好，23是默认值)
    
    def __post_init__(self):
        """验证配置参数"""
        # 验证分辨率格式
        if 'x' not in self.resolution:
            raise ValueError(f"Invalid resolution format: {self.resolution}. Expected format: WIDTHxHEIGHT")
        
        # 验证FPS
        if self.fps <= 0:
            raise ValueError(f"Invalid fps: {self.fps}. Must be positive")
        
        # 验证CRF
        if not 0 <= self.crf <= 51:
            raise ValueError(f"Invalid CRF: {self.crf}. Must be between 0-51")


class VideoExporter:
    """视频导出器"""
    
    def __init__(self, config: Optional[VideoExportConfig] = None):
        """
        初始化视频导出器
        
        Args:
            config: 导出配置，默认使用标准配置
        """
        self.config = config or VideoExportConfig()
        self._check_ffmpeg()
        logger.info(f"VideoExporter initialized with config: {self.config}")
    
    def _check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("FFmpeg is not working properly")
            logger.info("FFmpeg is available")
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg not found. Please install FFmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Ubuntu: sudo apt-get install ffmpeg\n"
                "  Windows: Download from https://ffmpeg.org/download.html"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg check timed out")
    
    def export_video(self, 
                    audio_file: Path,
                    timeline_items: List[Dict[str, Any]],
                    photos_dir: Path,
                    output_file: Path,
                    audio_duration: float) -> Path:
        """
        导出视频文件
        
        Args:
            audio_file: 音频文件路径
            timeline_items: 时间轴项列表（包含照片路径和显示时长）
            photos_dir: 照片目录
            output_file: 输出视频文件路径
            audio_duration: 音频总时长
            
        Returns:
            生成的视频文件路径
        """
        logger.info(f"Starting video export to: {output_file}")
        logger.info(f"Timeline items: {len(timeline_items)}")
        
        # 创建输出目录
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建临时工作目录
        temp_dir = output_file.parent / f".temp_{output_file.stem}"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Step 1: 为每张照片创建视频片段
            logger.info("Step 1: Creating video segments for each photo...")
            segment_files = self._create_photo_segments(
                timeline_items, photos_dir, temp_dir
            )
            
            # Step 2: 合并视频片段
            logger.info("Step 2: Concatenating video segments...")
            video_only_file = temp_dir / "video_only.mp4"
            self._concatenate_segments(segment_files, video_only_file)
            
            # Step 3: 添加音频轨道
            logger.info("Step 3: Adding audio track...")
            self._add_audio_track(video_only_file, audio_file, output_file, audio_duration)
            
            logger.info(f"Video exported successfully: {output_file}")
            return output_file
            
        finally:
            # 清理临时文件
            logger.info("Cleaning up temporary files...")
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _create_photo_segments(self,
                              timeline_items: List[Dict[str, Any]],
                              photos_dir: Path,
                              temp_dir: Path) -> List[Path]:
        """
        为每张照片创建视频片段
        
        Args:
            timeline_items: 时间轴项列表
            photos_dir: 照片目录
            temp_dir: 临时目录
            
        Returns:
            视频片段文件路径列表
        """
        segment_files = []
        
        # 解析分辨率
        width, height = self.config.resolution.split('x')
        
        for i, item in enumerate(timeline_items):
            photo_file = photos_dir / item['photo']
            duration = item['duration']
            segment_file = temp_dir / f"segment_{i:04d}.mp4"
            
            logger.info(f"Creating segment {i+1}/{len(timeline_items)}: {photo_file.name} ({duration:.2f}s)")
            
            # 使用FFmpeg将照片转换为视频片段
            # -loop 1: 循环输入图片
            # -i: 输入文件
            # -t: 持续时间
            # -vf scale: 缩放到目标分辨率，保持宽高比
            # -r: 帧率
            # -c:v: 视频编码器
            # -pix_fmt: 像素格式
            cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出文件
                '-loop', '1',  # 循环图片
                '-i', str(photo_file),  # 输入图片
                '-t', str(duration),  # 持续时间
                '-vf', f"scale={self.config.resolution}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1",  # 缩放并填充
                '-r', str(self.config.fps),  # 帧率
                '-c:v', self.config.video_codec,  # 视频编码器
                '-preset', self.config.preset,  # 编码预设
                '-crf', str(self.config.crf),  # 质量因子
                '-pix_fmt', self.config.pixel_format,  # 像素格式
                str(segment_file)
            ]
            
            try:
                # Calculate timeout based on duration
                # Formula: duration * factor + base_overhead
                # Factor depends on encoding complexity (preset, resolution, etc.)
                # For still images to video, processing is roughly 1-2x realtime for fast preset
                timeout = max(duration * 2.0 + 30, 120)  # Minimum 2 minutes timeout
                
                logger.debug(f"Using timeout: {timeout:.1f}s for duration: {duration:.1f}s")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"FFmpeg error: {result.stderr}")
                    raise RuntimeError(f"Failed to create segment for {photo_file.name}")
                
                segment_files.append(segment_file)
                
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Timeout creating segment for {photo_file.name} (duration: {duration:.1f}s, timeout: {timeout:.1f}s)")
        
        return segment_files
    
    def _concatenate_segments(self, segment_files: List[Path], output_file: Path):
        """
        合并视频片段
        
        Args:
            segment_files: 视频片段文件列表
            output_file: 输出文件
        """
        # 创建concat文件列表
        concat_file = output_file.parent / "concat_list.txt"
        
        with open(concat_file, 'w') as f:
            for segment in segment_files:
                f.write(f"file '{segment.absolute()}'\n")
        
        # 使用concat demuxer合并视频
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',  # concat demuxer
            '-safe', '0',  # 允许绝对路径
            '-i', str(concat_file),  # 输入列表文件
            '-c', 'copy',  # 直接复制流，不重新编码
            str(output_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                raise RuntimeError("Failed to concatenate video segments")
            
            # 删除concat文件
            concat_file.unlink()
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout concatenating video segments")
    
    def _add_audio_track(self, video_file: Path, audio_file: Path, 
                        output_file: Path, audio_duration: float):
        """
        添加音频轨道到视频
        
        Args:
            video_file: 视频文件（无音频）
            audio_file: 音频文件
            output_file: 输出文件
            audio_duration: 音频时长
        """
        # 合并视频和音频
        # -i: 输入文件（视频和音频）
        # -c:v copy: 直接复制视频流
        # -c:a: 音频编码器
        # -b:a: 音频比特率
        # -shortest: 以较短的流为准
        cmd = [
            'ffmpeg',
            '-y',
            '-i', str(video_file),  # 输入视频
            '-i', str(audio_file),  # 输入音频
            '-c:v', 'copy',  # 复制视频流
            '-c:a', self.config.audio_codec,  # 音频编码器
            '-b:a', self.config.audio_bitrate,  # 音频比特率
            '-shortest',  # 以较短的流为准
            str(output_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                raise RuntimeError("Failed to add audio track")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout adding audio track")
    
    def get_video_info(self, video_file: Path) -> Dict[str, Any]:
        """
        获取视频文件信息
        
        Args:
            video_file: 视频文件路径
            
        Returns:
            视频信息字典
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(video_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to get video info: {result.stderr}")
            
            info = json.loads(result.stdout)
            
            # 提取关键信息
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
            
            return {
                'duration': float(info['format'].get('duration', 0)),
                'size': int(info['format'].get('size', 0)),
                'bitrate': int(info['format'].get('bit_rate', 0)),
                'video': {
                    'codec': video_stream.get('codec_name') if video_stream else None,
                    'width': video_stream.get('width') if video_stream else None,
                    'height': video_stream.get('height') if video_stream else None,
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0,
                } if video_stream else None,
                'audio': {
                    'codec': audio_stream.get('codec_name') if audio_stream else None,
                    'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else None,
                    'channels': audio_stream.get('channels') if audio_stream else None,
                } if audio_stream else None
            }
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout getting video info")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse video info: {e}")


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Video Exporter Test')
    parser.add_argument('--check', action='store_true', help='Check FFmpeg installation')
    parser.add_argument('--info', type=Path, help='Get video file info')
    
    args = parser.parse_args()
    
    if args.check:
        try:
            exporter = VideoExporter()
            print("✅ FFmpeg is properly installed and working")
        except RuntimeError as e:
            print(f"❌ {e}")
            return 1
    
    if args.info:
        try:
            exporter = VideoExporter()
            info = exporter.get_video_info(args.info)
            print(json.dumps(info, indent=2))
        except Exception as e:
            print(f"❌ Error: {e}")
            return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
