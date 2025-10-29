"""
Unit tests for TimelineSync
时间轴同步引擎单元测试
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

from src.core.timeline.timeline_sync import TimelineSync, Timeline, TimelineItem


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def mock_audio_file(temp_dir):
    """创建模拟音频文件"""
    audio_file = temp_dir / "2025-10-29-10:00:00.mp3"
    audio_file.write_text("mock audio")
    return audio_file


@pytest.fixture
def mock_photo_files(temp_dir):
    """创建模拟照片文件"""
    photos = []
    for i in range(5):
        photo_file = temp_dir / f"2025-10-29-10:0{i}:00.jpg"
        photo_file.write_text("mock photo")
        photos.append(photo_file)
    return photos


class TestTimelineItem:
    """测试TimelineItem类"""
    
    def test_timeline_item_creation(self, temp_dir):
        """测试创建TimelineItem"""
        photo_file = temp_dir / "test.jpg"
        photo_file.write_text("test")
        
        item = TimelineItem(
            timestamp=datetime(2025, 10, 29, 10, 0, 0),
            offset_seconds=60.0,
            file_path=photo_file,
            duration=30.0
        )
        
        assert item.timestamp == datetime(2025, 10, 29, 10, 0, 0)
        assert item.offset_seconds == 60.0
        assert item.file_path == photo_file
        assert item.duration == 30.0
    
    def test_timeline_item_repr(self, temp_dir):
        """测试TimelineItem字符串表示"""
        photo_file = temp_dir / "test.jpg"
        photo_file.write_text("test")
        
        item = TimelineItem(
            timestamp=datetime(2025, 10, 29, 10, 0, 0),
            offset_seconds=60.0,
            file_path=photo_file,
            duration=30.0
        )
        
        repr_str = repr(item)
        assert "TimelineItem" in repr_str
        assert "60.00" in repr_str
        assert "30.00" in repr_str
        assert "test.jpg" in repr_str
    
    def test_timeline_item_to_dict(self, temp_dir):
        """测试TimelineItem转换为字典"""
        photo_file = temp_dir / "test.jpg"
        photo_file.write_text("test")
        
        item = TimelineItem(
            timestamp=datetime(2025, 10, 29, 10, 0, 0),
            offset_seconds=60.0,
            file_path=photo_file,
            duration=30.0
        )
        
        item_dict = item.to_dict()
        
        assert isinstance(item_dict, dict)
        assert item_dict['offset_seconds'] == 60.0
        assert item_dict['duration'] == 30.0
        assert str(photo_file) in item_dict['file_path']


class TestTimeline:
    """测试Timeline类"""
    
    def test_timeline_creation(self):
        """测试创建Timeline"""
        start_time = datetime(2025, 10, 29, 10, 0, 0)
        timeline = Timeline(audio_start_time=start_time, audio_duration=180.0)
        
        assert timeline.audio_start_time == start_time
        assert timeline.audio_duration == 180.0
        assert timeline.items == []
    
    def test_add_item(self, temp_dir):
        """测试添加时间轴项"""
        timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=180.0
        )
        
        photo_file = temp_dir / "test.jpg"
        photo_file.write_text("test")
        
        item = TimelineItem(
            timestamp=datetime(2025, 10, 29, 10, 1, 0),
            offset_seconds=60.0,
            file_path=photo_file,
            duration=0.0
        )
        
        timeline.add_item(item)
        
        assert len(timeline.items) == 1
        assert timeline.items[0] == item
    
    def test_sort_items(self, temp_dir):
        """测试时间轴项排序"""
        timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=300.0
        )
        
        # 添加乱序的项
        for offset in [120.0, 60.0, 180.0, 30.0]:
            photo_file = temp_dir / f"photo_{offset}.jpg"
            photo_file.write_text("test")
            
            item = TimelineItem(
                timestamp=datetime(2025, 10, 29, 10, 0, 0) + timedelta(seconds=offset),
                offset_seconds=offset,
                file_path=photo_file,
                duration=0.0
            )
            timeline.add_item(item)
        
        timeline.sort_items()
        
        # 验证排序
        assert timeline.items[0].offset_seconds == 30.0
        assert timeline.items[1].offset_seconds == 60.0
        assert timeline.items[2].offset_seconds == 120.0
        assert timeline.items[3].offset_seconds == 180.0
    
    def test_calculate_durations(self, temp_dir):
        """测试计算持续时间"""
        timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=300.0
        )
        
        # 添加项
        for offset in [60.0, 120.0, 180.0]:
            photo_file = temp_dir / f"photo_{offset}.jpg"
            photo_file.write_text("test")
            
            item = TimelineItem(
                timestamp=datetime(2025, 10, 29, 10, 0, 0) + timedelta(seconds=offset),
                offset_seconds=offset,
                file_path=photo_file,
                duration=0.0
            )
            timeline.add_item(item)
        
        timeline.calculate_durations()
        
        # 验证持续时间
        assert timeline.items[0].duration == 60.0  # 120.0 - 60.0
        assert timeline.items[1].duration == 60.0  # 180.0 - 120.0
        assert timeline.items[2].duration == 120.0  # 300.0 - 180.0 (到音频结束)
    
    def test_get_current_item(self, temp_dir):
        """测试获取当前时间对应的项"""
        timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=300.0
        )
        
        # 添加项
        offsets = [60.0, 120.0, 180.0]
        for offset in offsets:
            photo_file = temp_dir / f"photo_{offset}.jpg"
            photo_file.write_text("test")
            
            item = TimelineItem(
                timestamp=datetime(2025, 10, 29, 10, 0, 0) + timedelta(seconds=offset),
                offset_seconds=offset,
                file_path=photo_file,
                duration=60.0
            )
            timeline.add_item(item)
        
        # 测试不同时间点
        assert timeline.get_current_item(30.0) is None  # 第一张照片之前
        assert timeline.get_current_item(60.0).offset_seconds == 60.0
        assert timeline.get_current_item(90.0).offset_seconds == 60.0
        assert timeline.get_current_item(120.0).offset_seconds == 120.0
        assert timeline.get_current_item(150.0).offset_seconds == 120.0
        assert timeline.get_current_item(180.0).offset_seconds == 180.0
        assert timeline.get_current_item(250.0).offset_seconds == 180.0
    
    def test_get_current_item_empty_timeline(self):
        """测试空时间轴获取当前项"""
        timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=300.0
        )
        
        assert timeline.get_current_item(60.0) is None
    
    def test_timeline_to_dict(self, temp_dir):
        """测试Timeline转换为字典"""
        timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=180.0
        )
        
        photo_file = temp_dir / "test.jpg"
        photo_file.write_text("test")
        
        item = TimelineItem(
            timestamp=datetime(2025, 10, 29, 10, 1, 0),
            offset_seconds=60.0,
            file_path=photo_file,
            duration=30.0
        )
        timeline.add_item(item)
        
        timeline_dict = timeline.to_dict()
        
        assert isinstance(timeline_dict, dict)
        assert 'audio_start_time' in timeline_dict
        assert timeline_dict['audio_duration'] == 180.0
        assert len(timeline_dict['items']) == 1


class TestTimelineSyncParseTimestamp:
    """测试TimelineSync.parse_timestamp方法"""
    
    def test_parse_valid_timestamp(self):
        """测试解析有效时间戳"""
        timestamp = TimelineSync.parse_timestamp("2025-10-29-10:30:45.mp3")
        
        assert timestamp.year == 2025
        assert timestamp.month == 10
        assert timestamp.day == 29
        assert timestamp.hour == 10
        assert timestamp.minute == 30
        assert timestamp.second == 45
    
    def test_parse_timestamp_jpg(self):
        """测试解析JPG文件时间戳"""
        timestamp = TimelineSync.parse_timestamp("2025-01-15-08:00:00.jpg")
        
        assert timestamp.year == 2025
        assert timestamp.month == 1
        assert timestamp.day == 15
        assert timestamp.hour == 8
        assert timestamp.minute == 0
        assert timestamp.second == 0
    
    def test_parse_invalid_timestamp_format(self):
        """测试解析无效格式的时间戳"""
        with pytest.raises(ValueError, match="Invalid filename format"):
            TimelineSync.parse_timestamp("invalid-filename.mp3")
    
    def test_parse_timestamp_no_extension(self):
        """测试解析无扩展名的文件名"""
        timestamp = TimelineSync.parse_timestamp("2025-10-29-10:30:45")
        
        assert timestamp.year == 2025
        assert timestamp.hour == 10
    
    def test_parse_timestamp_missing_seconds(self):
        """测试解析缺少秒的时间戳"""
        with pytest.raises(ValueError):
            TimelineSync.parse_timestamp("2025-10-29-10:30.mp3")
    
    def test_parse_timestamp_invalid_date(self):
        """测试解析无效日期"""
        with pytest.raises(ValueError):
            TimelineSync.parse_timestamp("2025-13-40-10:30:45.mp3")


class TestTimelineSyncBuildTimeline:
    """测试TimelineSync.build_timeline方法"""
    
    def test_build_timeline_basic(self, mock_audio_file, temp_dir):
        """测试基本时间轴构建"""
        # 创建3张照片，每张间隔60秒
        photos = []
        for i in range(1, 4):
            photo = temp_dir / f"2025-10-29-10:0{i}:00.jpg"
            photo.write_text("test")
            photos.append(photo)
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=photos,
            audio_duration=300.0
        )
        
        assert isinstance(timeline, Timeline)
        assert len(timeline.items) == 3
        assert timeline.audio_duration == 300.0
        
        # 验证偏移量
        assert timeline.items[0].offset_seconds == 60.0
        assert timeline.items[1].offset_seconds == 120.0
        assert timeline.items[2].offset_seconds == 180.0
    
    def test_build_timeline_with_sorting(self, mock_audio_file, temp_dir):
        """测试时间轴构建时自动排序"""
        # 创建乱序的照片
        photos = [
            temp_dir / "2025-10-29-10:03:00.jpg",
            temp_dir / "2025-10-29-10:01:00.jpg",
            temp_dir / "2025-10-29-10:02:00.jpg",
        ]
        for photo in photos:
            photo.write_text("test")
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=photos,
            audio_duration=300.0
        )
        
        # 验证已排序
        assert timeline.items[0].offset_seconds == 60.0
        assert timeline.items[1].offset_seconds == 120.0
        assert timeline.items[2].offset_seconds == 180.0
    
    def test_build_timeline_calculates_durations(self, mock_audio_file, temp_dir):
        """测试时间轴构建时计算持续时间"""
        photos = []
        for i in range(1, 4):
            photo = temp_dir / f"2025-10-29-10:0{i}:00.jpg"
            photo.write_text("test")
            photos.append(photo)
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=photos,
            audio_duration=300.0
        )
        
        # 验证持续时间
        assert timeline.items[0].duration == 60.0  # 从60s到120s
        assert timeline.items[1].duration == 60.0  # 从120s到180s
        assert timeline.items[2].duration == 120.0  # 从180s到300s (音频结束)
    
    def test_build_timeline_filters_photos_before_audio(self, mock_audio_file, temp_dir):
        """测试过滤音频开始前的照片"""
        photos = [
            temp_dir / "2025-10-29-09:59:00.jpg",  # 音频前1分钟 (应该被过滤)
            temp_dir / "2025-10-29-10:00:30.jpg",  # 音频后30秒
            temp_dir / "2025-10-29-10:01:00.jpg",  # 音频后60秒
        ]
        for photo in photos:
            photo.write_text("test")
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=photos,
            audio_duration=180.0
        )
        
        # 第一张照片应该被过滤掉（负偏移）
        assert len(timeline.items) == 2
        assert timeline.items[0].offset_seconds == 30.0
        assert timeline.items[1].offset_seconds == 60.0
    
    def test_build_timeline_filters_photos_after_audio(self, mock_audio_file, temp_dir):
        """测试过滤音频结束后的照片"""
        photos = [
            temp_dir / "2025-10-29-10:01:00.jpg",  # 60秒
            temp_dir / "2025-10-29-10:02:00.jpg",  # 120秒
            temp_dir / "2025-10-29-10:05:00.jpg",  # 300秒 (超出180秒音频)
        ]
        for photo in photos:
            photo.write_text("test")
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=photos,
            audio_duration=180.0
        )
        
        # 最后一张照片应该被过滤掉（超出音频时长）
        assert len(timeline.items) == 2
        assert timeline.items[0].offset_seconds == 60.0
        assert timeline.items[1].offset_seconds == 120.0
    
    def test_build_timeline_with_invalid_photo_filename(self, mock_audio_file, temp_dir):
        """测试包含无效文件名的照片"""
        photos = [
            temp_dir / "2025-10-29-10:01:00.jpg",  # 有效
            temp_dir / "invalid-filename.jpg",  # 无效
            temp_dir / "2025-10-29-10:02:00.jpg",  # 有效
        ]
        for photo in photos:
            photo.write_text("test")
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=photos,
            audio_duration=300.0
        )
        
        # 无效的照片应该被跳过
        assert len(timeline.items) == 2
        assert timeline.items[0].offset_seconds == 60.0
        assert timeline.items[1].offset_seconds == 120.0
    
    def test_build_timeline_with_no_photos(self, mock_audio_file):
        """测试没有照片的时间轴"""
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=[],
            audio_duration=300.0
        )
        
        assert len(timeline.items) == 0
        assert timeline.audio_duration == 300.0


class TestTimelineSyncValidateFiles:
    """测试TimelineSync.validate_files方法"""
    
    def test_validate_files_all_valid(self, mock_audio_file, temp_dir):
        """测试所有文件名都有效"""
        photos = [
            temp_dir / "2025-10-29-10:01:00.jpg",
            temp_dir / "2025-10-29-10:02:00.jpg",
        ]
        for photo in photos:
            photo.write_text("test")
        
        result = TimelineSync.validate_files(mock_audio_file, photos)
        assert result is True
    
    def test_validate_files_invalid_audio(self, temp_dir):
        """测试音频文件名无效"""
        invalid_audio = temp_dir / "invalid-audio.mp3"
        invalid_audio.write_text("test")
        
        photos = [temp_dir / "2025-10-29-10:01:00.jpg"]
        photos[0].write_text("test")
        
        result = TimelineSync.validate_files(invalid_audio, photos)
        assert result is False
    
    def test_validate_files_invalid_photo(self, mock_audio_file, temp_dir):
        """测试照片文件名无效"""
        photos = [
            temp_dir / "2025-10-29-10:01:00.jpg",
            temp_dir / "invalid-photo.jpg",
        ]
        for photo in photos:
            photo.write_text("test")
        
        result = TimelineSync.validate_files(mock_audio_file, photos)
        assert result is False
    
    def test_validate_files_empty_photos(self, mock_audio_file):
        """测试空照片列表"""
        result = TimelineSync.validate_files(mock_audio_file, [])
        assert result is True


class TestTimelineSyncEdgeCases:
    """测试边界情况"""
    
    def test_photo_at_exact_audio_start(self, mock_audio_file, temp_dir):
        """测试照片恰好在音频开始时刻"""
        photo = temp_dir / "2025-10-29-10:00:00.jpg"
        photo.write_text("test")
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=[photo],
            audio_duration=180.0
        )
        
        assert len(timeline.items) == 1
        assert timeline.items[0].offset_seconds == 0.0
    
    def test_photo_at_exact_audio_end(self, mock_audio_file, temp_dir):
        """测试照片恰好在音频结束时刻"""
        photo = temp_dir / "2025-10-29-10:03:00.jpg"  # 正好180秒后
        photo.write_text("test")
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=[photo],
            audio_duration=180.0
        )
        
        assert len(timeline.items) == 1
        assert timeline.items[0].offset_seconds == 180.0
    
    def test_many_photos(self, mock_audio_file, temp_dir):
        """测试大量照片"""
        photos = []
        for i in range(100):
            minute = i // 60
            second = i % 60
            photo = temp_dir / f"2025-10-29-10:{minute:02d}:{second:02d}.jpg"
            photo.write_text("test")
            photos.append(photo)
        
        timeline = TimelineSync.build_timeline(
            audio_file=mock_audio_file,
            photo_files=photos,
            audio_duration=6000.0  # 100分钟
        )
        
        assert len(timeline.items) == 100
        # 验证第一张和最后一张
        assert timeline.items[0].offset_seconds == 0.0
        assert timeline.items[99].offset_seconds == 99.0
