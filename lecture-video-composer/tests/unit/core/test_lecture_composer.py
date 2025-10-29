"""
Unit tests for LectureComposer
核心编排器单元测试
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import shutil

from src.core.lecture_composer import LectureComposer
from src.services.audio.audio_service import AudioMetadata
from src.services.image.image_service import ImageMetadata
from src.core.timeline.timeline_sync import Timeline, TimelineItem
from datetime import datetime


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
    audio_file.write_text("mock audio content")
    return audio_file


@pytest.fixture
def mock_photo_files(temp_dir):
    """创建模拟照片文件"""
    photos = []
    for i in range(3):
        photo_file = temp_dir / f"2025-10-29-10:0{i}:00.jpg"
        photo_file.write_text("mock photo content")
        photos.append(photo_file)
    return photos


@pytest.fixture
def composer(mock_audio_file, mock_photo_files):
    """创建LectureComposer实例"""
    return LectureComposer(mock_audio_file, mock_photo_files)


class TestLectureComposerInit:
    """测试LectureComposer初始化"""
    
    def test_init_with_valid_inputs(self, mock_audio_file, mock_photo_files):
        """测试使用有效输入初始化"""
        composer = LectureComposer(mock_audio_file, mock_photo_files)
        
        assert composer.audio_file == mock_audio_file
        assert len(composer.photo_files) == 3
        assert composer.output_dir == Path.cwd() / "output"
        assert composer.audio_metadata is None
        assert composer.photo_metadata == []
        assert composer.timeline is None
        assert composer.project_metadata is None
    
    def test_init_with_custom_output_dir(self, mock_audio_file, mock_photo_files, temp_dir):
        """测试使用自定义输出目录初始化"""
        custom_output = temp_dir / "custom_output"
        composer = LectureComposer(mock_audio_file, mock_photo_files, output_dir=custom_output)
        
        assert composer.output_dir == custom_output
    
    def test_init_sorts_photo_files(self, mock_audio_file, temp_dir):
        """测试初始化时照片文件排序"""
        photos = [
            temp_dir / "2025-10-29-10:02:00.jpg",
            temp_dir / "2025-10-29-10:00:00.jpg",
            temp_dir / "2025-10-29-10:01:00.jpg",
        ]
        for photo in photos:
            photo.write_text("mock")
        
        composer = LectureComposer(mock_audio_file, photos)
        
        # 验证排序
        assert composer.photo_files[0].name == "2025-10-29-10:00:00.jpg"
        assert composer.photo_files[1].name == "2025-10-29-10:01:00.jpg"
        assert composer.photo_files[2].name == "2025-10-29-10:02:00.jpg"


class TestValidateInputs:
    """测试输入验证"""
    
    @patch('src.core.lecture_composer.AudioService.validate_audio_file')
    @patch('src.core.lecture_composer.ImageService.validate_image_file')
    @patch('src.core.lecture_composer.TimelineSync.validate_files')
    def test_validate_inputs_success(self, mock_timeline_validate, mock_image_validate, 
                                     mock_audio_validate, composer):
        """测试所有输入验证通过"""
        mock_audio_validate.return_value = True
        mock_image_validate.return_value = True
        mock_timeline_validate.return_value = True
        
        result = composer.validate_inputs()
        
        assert result is True
        mock_audio_validate.assert_called_once_with(composer.audio_file)
        assert mock_image_validate.call_count == 3
        mock_timeline_validate.assert_called_once()
    
    @patch('src.core.lecture_composer.AudioService.validate_audio_file')
    def test_validate_inputs_invalid_audio(self, mock_audio_validate, composer):
        """测试音频文件验证失败"""
        mock_audio_validate.return_value = False
        
        result = composer.validate_inputs()
        
        assert result is False
    
    @patch('src.core.lecture_composer.AudioService.validate_audio_file')
    @patch('src.core.lecture_composer.ImageService.validate_image_file')
    def test_validate_inputs_invalid_photo(self, mock_image_validate, mock_audio_validate, composer):
        """测试照片文件验证失败"""
        mock_audio_validate.return_value = True
        mock_image_validate.side_effect = [True, False, True]  # 第二张照片无效
        
        result = composer.validate_inputs()
        
        assert result is False
    
    @patch('src.core.lecture_composer.AudioService.validate_audio_file')
    @patch('src.core.lecture_composer.ImageService.validate_image_file')
    @patch('src.core.lecture_composer.TimelineSync.validate_files')
    def test_validate_inputs_invalid_filenames(self, mock_timeline_validate, 
                                               mock_image_validate, mock_audio_validate, composer):
        """测试文件名格式验证失败"""
        mock_audio_validate.return_value = True
        mock_image_validate.return_value = True
        mock_timeline_validate.return_value = False
        
        result = composer.validate_inputs()
        
        assert result is False


class TestExtractMetadata:
    """测试元数据提取"""
    
    @patch('src.core.lecture_composer.AudioService.get_metadata')
    @patch('src.core.lecture_composer.ImageService.get_metadata')
    def test_extract_metadata_success(self, mock_image_metadata, mock_audio_metadata, composer):
        """测试成功提取元数据"""
        # 设置mock返回值
        mock_audio_meta = AudioMetadata(
            file_path=composer.audio_file,
            duration=180.0,
            sample_rate=44100,
            channels=2,
            codec="mp3"
        )
        mock_audio_metadata.return_value = mock_audio_meta
        
        mock_image_meta = ImageMetadata(
            file_path=composer.photo_files[0],
            width=1920,
            height=1080,
            format="JPEG",
            file_size=1024000
        )
        mock_image_metadata.return_value = mock_image_meta
        
        # 执行
        composer.extract_metadata()
        
        # 验证
        assert composer.audio_metadata == mock_audio_meta
        assert len(composer.photo_metadata) == 3
        mock_audio_metadata.assert_called_once_with(composer.audio_file)
        assert mock_image_metadata.call_count == 3


class TestBuildTimeline:
    """测试时间轴构建"""
    
    @patch('src.core.lecture_composer.TimelineSync.build_timeline')
    def test_build_timeline_success(self, mock_build_timeline, composer):
        """测试成功构建时间轴"""
        # 设置音频元数据
        composer.audio_metadata = AudioMetadata(
            file_path=composer.audio_file,
            duration=180.0,
            sample_rate=44100,
            channels=2,
            codec="mp3"
        )
        
        # 设置mock返回值
        mock_timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=180.0
        )
        mock_build_timeline.return_value = mock_timeline
        
        # 执行
        result = composer.build_timeline()
        
        # 验证
        assert result == mock_timeline
        assert composer.timeline == mock_timeline
        mock_build_timeline.assert_called_once_with(
            audio_file=composer.audio_file,
            photo_files=composer.photo_files,
            audio_duration=180.0
        )
    
    def test_build_timeline_without_metadata(self, composer):
        """测试在没有元数据的情况下构建时间轴"""
        with pytest.raises(RuntimeError, match="Audio metadata not extracted"):
            composer.build_timeline()


class TestCreateProjectMetadata:
    """测试项目元数据创建"""
    
    @patch('src.core.lecture_composer.MetadataService.create_project_metadata')
    def test_create_project_metadata_success(self, mock_create_metadata, composer):
        """测试成功创建项目元数据"""
        # 设置前置条件
        composer.audio_metadata = AudioMetadata(
            file_path=composer.audio_file,
            duration=180.0,
            sample_rate=44100,
            channels=2,
            codec="mp3"
        )
        
        composer.timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=180.0
        )
        composer.timeline.add_item(TimelineItem(
            timestamp=datetime(2025, 10, 29, 10, 1, 0),
            offset_seconds=60.0,
            file_path=composer.photo_files[0],
            duration=60.0
        ))
        
        # Mock返回值
        from src.services.metadata.metadata_service import ProjectMetadata
        mock_metadata = Mock(spec=ProjectMetadata)
        mock_create_metadata.return_value = mock_metadata
        
        # 执行
        result = composer.create_project_metadata(title="Test Project")
        
        # 验证
        assert result == mock_metadata
        assert composer.project_metadata == mock_metadata
        mock_create_metadata.assert_called_once()
    
    def test_create_project_metadata_without_timeline(self, composer):
        """测试在没有时间轴的情况下创建元数据"""
        with pytest.raises(RuntimeError, match="Timeline not built"):
            composer.create_project_metadata()


class TestSaveProject:
    """测试项目保存"""
    
    @patch('src.core.lecture_composer.MetadataService.save_metadata')
    def test_save_project_success(self, mock_save_metadata, composer, temp_dir):
        """测试成功保存项目"""
        # 设置输出目录为临时目录
        composer.output_dir = temp_dir / "output"
        
        # 设置项目元数据
        from src.services.metadata.metadata_service import ProjectMetadata
        composer.project_metadata = Mock(spec=ProjectMetadata)
        
        # 执行
        composer.save_project()
        
        # 验证目录创建
        assert (composer.output_dir / "audio").exists()
        assert (composer.output_dir / "photos").exists()
        
        # 验证文件复制
        assert (composer.output_dir / "audio" / composer.audio_file.name).exists()
        for photo in composer.photo_files:
            assert (composer.output_dir / "photos" / photo.name).exists()
        
        # 验证元数据保存
        mock_save_metadata.assert_called_once_with(
            composer.project_metadata,
            composer.output_dir
        )
    
    def test_save_project_without_metadata(self, composer):
        """测试在没有元数据的情况下保存项目"""
        with pytest.raises(RuntimeError, match="Project metadata not created"):
            composer.save_project()


class TestProcess:
    """测试完整处理流程"""
    
    @patch.object(LectureComposer, 'validate_inputs')
    @patch.object(LectureComposer, 'extract_metadata')
    @patch.object(LectureComposer, 'build_timeline')
    @patch.object(LectureComposer, 'create_project_metadata')
    @patch.object(LectureComposer, 'save_project')
    def test_process_with_save(self, mock_save, mock_create_meta, mock_build,
                               mock_extract, mock_validate, composer):
        """测试完整处理流程（保存）"""
        # 设置mock返回值
        mock_validate.return_value = True
        from src.services.metadata.metadata_service import ProjectMetadata
        mock_metadata = Mock(spec=ProjectMetadata)
        
        # 关键修复：让 create_project_metadata 同时返回值并设置实例属性
        def set_metadata_and_return(title=None):
            composer.project_metadata = mock_metadata
            return mock_metadata
        
        mock_create_meta.side_effect = set_metadata_and_return
        
        # 执行
        result = composer.process(title="Test", save=True)
        
        # 验证调用顺序
        assert result == mock_metadata
        mock_validate.assert_called_once()
        mock_extract.assert_called_once()
        mock_build.assert_called_once()
        mock_create_meta.assert_called_once_with(title="Test")
        mock_save.assert_called_once()
    
    @patch.object(LectureComposer, 'validate_inputs')
    @patch.object(LectureComposer, 'extract_metadata')
    @patch.object(LectureComposer, 'build_timeline')
    @patch.object(LectureComposer, 'create_project_metadata')
    @patch.object(LectureComposer, 'save_project')
    def test_process_without_save(self, mock_save, mock_create_meta, mock_build,
                                  mock_extract, mock_validate, composer):
        """测试完整处理流程（不保存）"""
        mock_validate.return_value = True
        from src.services.metadata.metadata_service import ProjectMetadata
        mock_metadata = Mock(spec=ProjectMetadata)
        
        # 关键修复：让 create_project_metadata 同时返回值并设置实例属性
        def set_metadata_and_return(title=None):
            composer.project_metadata = mock_metadata
            return mock_metadata
        
        mock_create_meta.side_effect = set_metadata_and_return
        
        result = composer.process(save=False)
        
        assert result == mock_metadata
        mock_save.assert_not_called()
    
    @patch.object(LectureComposer, 'validate_inputs')
    def test_process_validation_failure(self, mock_validate, composer):
        """测试处理流程验证失败"""
        mock_validate.return_value = False
        
        with pytest.raises(RuntimeError, match="Input validation failed"):
            composer.process()


class TestExportVideo:
    """测试视频导出"""
    
    @patch('src.core.lecture_composer.VideoExporter')
    def test_export_video_success(self, mock_exporter_class, composer, temp_dir):
        """测试成功导出视频"""
        # 设置前置条件
        composer.output_dir = temp_dir / "output"
        composer.output_dir.mkdir(parents=True, exist_ok=True)
        (composer.output_dir / "audio").mkdir(exist_ok=True)
        (composer.output_dir / "photos").mkdir(exist_ok=True)
        
        # 复制文件到输出目录
        import shutil
        shutil.copy2(composer.audio_file, composer.output_dir / "audio" / composer.audio_file.name)
        for photo in composer.photo_files:
            shutil.copy2(photo, composer.output_dir / "photos" / photo.name)
        
        composer.audio_metadata = AudioMetadata(
            file_path=composer.audio_file,
            duration=180.0,
            sample_rate=44100,
            channels=2,
            codec="mp3"
        )
        
        composer.timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=180.0
        )
        composer.timeline.add_item(TimelineItem(
            timestamp=datetime(2025, 10, 29, 10, 1, 0),
            offset_seconds=60.0,
            file_path=composer.photo_files[0],
            duration=60.0
        ))
        
        # Mock VideoExporter
        mock_exporter = Mock()
        mock_exporter_class.return_value = mock_exporter
        
        output_video = temp_dir / "output.mp4"
        mock_exporter.export_video.return_value = output_video
        mock_exporter.get_video_info.return_value = {
            'duration': 180.0,
            'size': '1280x720',
            'codec': 'h264'
        }
        
        # 执行
        result = composer.export_video(output_file=output_video)
        
        # 验证
        assert result == output_video
        mock_exporter.export_video.assert_called_once()
        mock_exporter.get_video_info.assert_called_once_with(output_video)
    
    def test_export_video_without_timeline(self, composer):
        """测试在没有时间轴的情况下导出视频"""
        with pytest.raises(RuntimeError, match="Timeline not built"):
            composer.export_video()
    
    def test_export_video_without_metadata(self, composer):
        """测试在没有音频元数据的情况下导出视频"""
        composer.timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=180.0
        )
        
        with pytest.raises(RuntimeError, match="Audio metadata not extracted"):
            composer.export_video()


class TestGetSummary:
    """测试摘要生成"""
    
    def test_get_summary_without_timeline(self, composer):
        """测试在没有时间轴时获取摘要"""
        summary = composer.get_summary()
        assert "No timeline built yet" in summary
    
    def test_get_summary_with_timeline(self, composer):
        """测试有时间轴时获取摘要"""
        # 设置元数据和时间轴
        composer.audio_metadata = AudioMetadata(
            file_path=composer.audio_file,
            duration=180.0,
            sample_rate=44100,
            channels=2,
            codec="mp3"
        )
        
        composer.timeline = Timeline(
            audio_start_time=datetime(2025, 10, 29, 10, 0, 0),
            audio_duration=180.0
        )
        
        for i, photo in enumerate(composer.photo_files):
            composer.timeline.add_item(TimelineItem(
                timestamp=datetime(2025, 10, 29, 10, i, 0),
                offset_seconds=i * 60.0,
                file_path=photo,
                duration=60.0
            ))
        
        # 获取摘要
        summary = composer.get_summary()
        
        # 验证摘要内容
        assert "Lecture Composition Summary" in summary
        assert composer.audio_file.name in summary
        assert "180.00 seconds" in summary
        assert "Total Photos: 3" in summary
        assert "Timeline Items: 3" in summary
