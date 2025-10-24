"""
Subtitle Service
字幕服务 - 从音频生成字幕文件
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SubtitleSegment:
    """字幕片段"""
    index: int
    start_time: float  # 开始时间（秒）
    end_time: float    # 结束时间（秒）
    text: str          # 字幕文本
    
    def to_srt_format(self) -> str:
        """转换为SRT格式"""
        start_time_str = self._seconds_to_srt_time(self.start_time)
        end_time_str = self._seconds_to_srt_time(self.end_time)
        return f"{self.index}\n{start_time_str} --> {end_time_str}\n{self.text}\n"
    
    @staticmethod
    def _seconds_to_srt_time(seconds: float) -> str:
        """将秒数转换为SRT时间格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


@dataclass
class SubtitleConfig:
    """字幕配置"""
    model: str = "base"  # Whisper模型 (tiny, base, small, medium, large)
    language: str = "zh"  # 语言代码
    font_name: str = "Arial"  # 字体名称
    font_size: int = 24  # 字体大小
    font_color: str = "white"  # 字体颜色
    outline_color: str = "black"  # 描边颜色
    outline_width: int = 2  # 描边宽度
    position: str = "bottom"  # 位置 (bottom, top, center)
    max_line_length: int = 42  # 每行最大字符数
    
    def get_ass_style(self) -> str:
        """获取ASS样式定义"""
        # ASS样式格式
        # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,
        #         Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle,
        #         Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        
        # 颜色转换为ASS格式 (&HAABBGGRR)
        color_map = {
            'white': '&H00FFFFFF',
            'black': '&H00000000',
            'yellow': '&H0000FFFF',
            'red': '&H000000FF',
            'green': '&H0000FF00',
            'blue': '&H00FF0000',
        }
        
        primary_color = color_map.get(self.font_color.lower(), '&H00FFFFFF')
        outline_color = color_map.get(self.outline_color.lower(), '&H00000000')
        
        # 位置对齐
        alignment_map = {
            'bottom': '2',  # 底部居中
            'top': '8',     # 顶部居中
            'center': '5'   # 中间居中
        }
        alignment = alignment_map.get(self.position, '2')
        
        return (
            f"Style: Default,{self.font_name},{self.font_size},"
            f"{primary_color},{primary_color},{outline_color},&H00000000,"
            f"0,0,0,0,100,100,0,0,1,"
            f"{self.outline_width},0,{alignment},10,10,10,1"
        )


class SubtitleService:
    """字幕服务"""
    
    def __init__(self, config: Optional[SubtitleConfig] = None):
        """
        初始化字幕服务
        
        Args:
            config: 字幕配置
        """
        self.config = config or SubtitleConfig()
        self._check_whisper()
        logger.info(f"SubtitleService initialized with config: {self.config}")
    
    def _check_whisper(self):
        """检查Whisper是否可用"""
        try:
            import whisper
            # 禁用SSL证书验证以解决下载问题
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            
            self.whisper = whisper
            logger.info("Whisper is available")
        except ImportError:
            logger.warning(
                "Whisper not installed. Subtitle generation will be disabled.\n"
                "To enable subtitles, install: pip install openai-whisper"
            )
            self.whisper = None
    
    def generate_subtitles(self, audio_file: Path, output_dir: Path) -> Optional[Path]:
        """
        从音频生成字幕文件
        
        Args:
            audio_file: 音频文件路径
            output_dir: 输出目录
            
        Returns:
            生成的SRT字幕文件路径，如果Whisper不可用则返回None
        """
        if self.whisper is None:
            logger.warning("Whisper not available, skipping subtitle generation")
            return None
        
        logger.info(f"Generating subtitles for: {audio_file}")
        
        try:
            # 加载Whisper模型
            logger.info(f"Loading Whisper model: {self.config.model}")
            logger.info("Note: If model download fails due to SSL errors, you can:")
            logger.info("1. Use a VPN or proxy")
            logger.info("2. Manually download the model from: https://github.com/openai/whisper/discussions/categories/models")
            logger.info("3. Place it in: ~/.cache/whisper/")
            
            model = self.whisper.load_model(self.config.model)
            
            # 转录音频
            logger.info("Transcribing audio...")
            result = model.transcribe(
                str(audio_file),
                language=self.config.language,
                verbose=False
            )
            
            # 转换为字幕片段
            segments = []
            for i, segment in enumerate(result['segments'], start=1):
                subtitle_seg = SubtitleSegment(
                    index=i,
                    start_time=segment['start'],
                    end_time=segment['end'],
                    text=segment['text'].strip()
                )
                segments.append(subtitle_seg)
            
            logger.info(f"Generated {len(segments)} subtitle segments")
            
            # 保存SRT文件
            srt_file = output_dir / f"{audio_file.stem}.srt"
            self._save_srt(segments, srt_file)
            
            # 保存ASS文件（用于更好的样式控制）
            ass_file = output_dir / f"{audio_file.stem}.ass"
            self._save_ass(segments, ass_file)
            
            logger.info(f"Subtitles saved to: {srt_file}")
            return srt_file
            
        except Exception as e:
            logger.error(f"Failed to generate subtitles: {e}")
            return None
    
    def _save_srt(self, segments: List[SubtitleSegment], output_file: Path):
        """
        保存为SRT格式
        
        Args:
            segments: 字幕片段列表
            output_file: 输出文件路径
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for segment in segments:
                f.write(segment.to_srt_format())
                f.write('\n')
        
        logger.info(f"SRT file saved: {output_file}")
    
    def _save_ass(self, segments: List[SubtitleSegment], output_file: Path):
        """
        保存为ASS格式（高级字幕格式，支持更多样式）
        
        Args:
            segments: 字幕片段列表
            output_file: 输出文件路径
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # ASS文件头部
        header = (
            "[Script Info]\n"
            "Title: Auto-generated Subtitles\n"
            "ScriptType: v4.00+\n"
            "Collisions: Normal\n"
            "PlayDepth: 0\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"{self.config.get_ass_style()}\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(header)
            
            for segment in segments:
                start_time = self._seconds_to_ass_time(segment.start_time)
                end_time = self._seconds_to_ass_time(segment.end_time)
                text = segment.text.replace('\n', '\\N')
                
                f.write(
                    f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n"
                )
        
        logger.info(f"ASS file saved: {output_file}")
    
    @staticmethod
    def _seconds_to_ass_time(seconds: float) -> str:
        """将秒数转换为ASS时间格式 (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
    
    def embed_subtitles(self, video_file: Path, subtitle_file: Path, 
                       output_file: Path) -> Path:
        """
        将字幕嵌入到视频中
        
        Args:
            video_file: 视频文件路径
            subtitle_file: 字幕文件路径
            output_file: 输出文件路径
            
        Returns:
            生成的视频文件路径
        """
        logger.info(f"Embedding subtitles into video: {video_file}")
        
        # 使用FFmpeg烧录字幕
        cmd = [
            'ffmpeg',
            '-y',
            '-i', str(video_file),
            '-vf', f"subtitles={subtitle_file}:force_style='FontName={self.config.font_name},FontSize={self.config.font_size}'",
            '-c:a', 'copy',
            str(output_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                raise RuntimeError("Failed to embed subtitles")
            
            logger.info(f"Subtitles embedded successfully: {output_file}")
            return output_file
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout embedding subtitles")
    
    def get_transcript_text(self, audio_file: Path) -> Optional[str]:
        """
        获取音频的文本转录（不带时间戳）
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            转录文本，如果失败则返回None
        """
        if self.whisper is None:
            return None
        
        try:
            logger.info(f"Transcribing audio to text: {audio_file}")
            model = self.whisper.load_model(self.config.model)
            result = model.transcribe(
                str(audio_file),
                language=self.config.language,
                verbose=False
            )
            return result['text'].strip()
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            return None


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Subtitle Service Test')
    parser.add_argument('audio_file', type=Path, help='Audio file to transcribe')
    parser.add_argument('--output-dir', type=Path, default=Path('output/subtitles'),
                       help='Output directory for subtitle files')
    parser.add_argument('--model', default='base', 
                       choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='Whisper model size')
    parser.add_argument('--language', default='zh', help='Language code')
    
    args = parser.parse_args()
    
    # 创建字幕服务
    config = SubtitleConfig(model=args.model, language=args.language)
    service = SubtitleService(config)
    
    # 生成字幕
    subtitle_file = service.generate_subtitles(args.audio_file, args.output_dir)
    
    if subtitle_file:
        print(f"✅ Subtitles generated: {subtitle_file}")
        
        # 获取纯文本转录
        text = service.get_transcript_text(args.audio_file)
        if text:
            print(f"\n📝 Transcript:\n{text}")
        
        return 0
    else:
        print("❌ Failed to generate subtitles")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
