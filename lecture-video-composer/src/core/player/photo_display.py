"""
Photo Display Manager
照片显示管理器 - 负责照片的显示和切换
"""

import logging
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import threading
import time

# 尝试导入PIL用于图片处理
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL not available. Install with: pip install Pillow")

logger = logging.getLogger(__name__)


class TransitionType(Enum):
    """过渡效果类型"""
    NONE = "none"           # 无过渡
    FADE = "fade"           # 淡入淡出
    SLIDE = "slide"         # 滑动
    CROSSFADE = "crossfade" # 交叉淡化


@dataclass
class DisplayConfig:
    """显示配置"""
    window_size: tuple[int, int] = (1280, 720)  # 窗口大小
    transition_type: TransitionType = TransitionType.FADE  # 过渡效果
    transition_duration: float = 0.5  # 过渡时长（秒）
    transition_fps: int = 30  # 过渡动画帧率
    preload_count: int = 3  # 预加载照片数量
    background_color: tuple[int, int, int] = (0, 0, 0)  # 背景颜色
    enable_transitions: bool = True  # 是否启用过渡动画


@dataclass
class PhotoItem:
    """照片项"""
    path: Path
    start_time: float  # 开始显示时间（秒）
    duration: float    # 显示时长（秒）
    image: Optional[Image.Image] = None  # 预加载的图片对象


class PhotoDisplayManager:
    """
    照片显示管理器
    
    功能:
    - 根据时间轴切换照片
    - 照片预加载
    - 过渡动画效果
    - 显示状态管理
    """
    
    def __init__(self, config: Optional[DisplayConfig] = None):
        """
        初始化照片显示管理器
        
        Args:
            config: 显示配置
        """
        if not PIL_AVAILABLE:
            raise RuntimeError(
                "PIL is required for photo display. "
                "Install with: pip install Pillow"
            )
        
        self.config = config or DisplayConfig()
        self._photos: List[PhotoItem] = []
        self._current_index: int = -1
        self._current_photo: Optional[PhotoItem] = None
        self._next_photo: Optional[PhotoItem] = None
        self._display_callbacks: List[Callable[[Optional[PhotoItem]], None]] = []
        self._preload_thread: Optional[threading.Thread] = None
        self._stop_preload = False
        
        logger.info(f"PhotoDisplayManager initialized: {self.config}")
    
    def load_timeline(self, timeline_items: List[Dict[str, Any]], photos_dir: Path):
        """
        加载时间轴照片列表
        
        Args:
            timeline_items: 时间轴项列表
            photos_dir: 照片目录
        """
        self._photos.clear()
        self._current_index = -1
        self._current_photo = None
        
        current_time = 0.0
        for item in timeline_items:
            photo_path = photos_dir / item['photo']
            duration = item['duration']
            
            photo_item = PhotoItem(
                path=photo_path,
                start_time=current_time,
                duration=duration
            )
            self._photos.append(photo_item)
            current_time += duration
        
        logger.info(f"Loaded {len(self._photos)} photos into timeline")
        
        # 启动预加载
        self._start_preloading()
    
    def get_photo_at_time(self, time_position: float) -> Optional[PhotoItem]:
        """
        获取指定时间应该显示的照片
        
        Args:
            time_position: 时间位置（秒）
            
        Returns:
            照片项，如果没有则返回None
        """
        for photo in self._photos:
            if photo.start_time <= time_position < photo.start_time + photo.duration:
                return photo
        
        # 如果超过最后一张照片的时间，返回最后一张
        if self._photos and time_position >= self._photos[-1].start_time:
            return self._photos[-1]
        
        return None
    
    def update(self, time_position: float) -> bool:
        """
        更新显示（根据当前时间位置）
        
        Args:
            time_position: 当前时间位置（秒）
            
        Returns:
            照片是否发生变化
        """
        target_photo = self.get_photo_at_time(time_position)
        
        if target_photo != self._current_photo:
            self._switch_to_photo(target_photo)
            return True
        
        return False
    
    def _switch_to_photo(self, photo: Optional[PhotoItem]):
        """
        切换到指定照片（带过渡效果）
        
        Args:
            photo: 目标照片项
        """
        if photo == self._current_photo:
            return
        
        old_photo = self._current_photo
        
        # 确保照片已加载
        if photo and not photo.image:
            self._load_photo(photo)
        
        # 执行过渡效果（如果启用）
        if self.config.enable_transitions and old_photo and photo:
            self._perform_transition(old_photo, photo)
        
        self._current_photo = photo
        
        # 更新索引
        if photo:
            try:
                self._current_index = self._photos.index(photo)
            except ValueError:
                self._current_index = -1
        else:
            self._current_index = -1
        
        # 通知回调
        self._notify_display_change()
        
        if old_photo:
            logger.info(f"Switched from {old_photo.path.name} to {photo.path.name if photo else 'None'} "
                       f"(transition: {self.config.transition_type.value})")
        else:
            logger.info(f"Switched to {photo.path.name if photo else 'None'}")
    
    def _perform_transition(self, old_photo: PhotoItem, new_photo: PhotoItem):
        """
        执行照片过渡动画
        
        Args:
            old_photo: 旧照片项
            new_photo: 新照片项
        """
        if not old_photo.image or not new_photo.image:
            return
        
        transition_type = self.config.transition_type
        
        if transition_type == TransitionType.NONE:
            return
        elif transition_type == TransitionType.FADE:
            self._transition_fade(old_photo.image, new_photo.image)
        elif transition_type == TransitionType.CROSSFADE:
            self._transition_crossfade(old_photo.image, new_photo.image)
        elif transition_type == TransitionType.SLIDE:
            self._transition_slide(old_photo.image, new_photo.image)
        else:
            logger.warning(f"Unsupported transition type: {transition_type}")
    
    def _transition_fade(self, old_image: Image.Image, new_image: Image.Image):
        """
        淡入淡出过渡效果
        
        逻辑：旧照片淡出（alpha逐渐变为0），然后新照片淡入（alpha从0变为255）
        
        Args:
            old_image: 旧图片
            new_image: 新图片
        """
        try:
            duration = self.config.transition_duration
            fps = self.config.transition_fps
            frames = int(duration * fps)
            
            if frames <= 0:
                return
            
            # 注意：这里只是生成过渡帧的逻辑示例
            # 实际显示需要由GUI层（如pygame surface或tkinter canvas）处理
            logger.debug(f"Fade transition: {frames} frames over {duration:.2f}s")
            
            # 这里我们只记录过渡信息，实际的渲染由调用者处理
            # 可以通过回调返回过渡帧序列
            
        except Exception as e:
            logger.error(f"Failed to perform fade transition: {e}")
    
    def _transition_crossfade(self, old_image: Image.Image, new_image: Image.Image):
        """
        交叉淡化过渡效果
        
        逻辑：旧照片和新照片同时过渡，旧照片alpha从255->0，新照片alpha从0->255
        
        Args:
            old_image: 旧图片
            new_image: 新图片
        """
        try:
            duration = self.config.transition_duration
            fps = self.config.transition_fps
            frames = int(duration * fps)
            
            if frames <= 0:
                return
            
            logger.debug(f"Crossfade transition: {frames} frames over {duration:.2f}s")
            
            # 交叉淡化的实现示例（需要GUI层支持）
            # for frame_num in range(frames):
            #     alpha = frame_num / frames  # 0.0 -> 1.0
            #     # 混合两张图片
            #     blended = Image.blend(old_image, new_image, alpha)
            #     # 显示混合后的图片
            
        except Exception as e:
            logger.error(f"Failed to perform crossfade transition: {e}")
    
    def _transition_slide(self, old_image: Image.Image, new_image: Image.Image):
        """
        滑动过渡效果
        
        逻辑：新照片从右侧滑入，推出旧照片
        
        Args:
            old_image: 旧图片
            new_image: 新图片
        """
        try:
            duration = self.config.transition_duration
            fps = self.config.transition_fps
            frames = int(duration * fps)
            
            if frames <= 0:
                return
            
            logger.debug(f"Slide transition: {frames} frames over {duration:.2f}s")
            
            # 滑动效果的实现示例（需要GUI层支持）
            # for frame_num in range(frames):
            #     offset = int((frame_num / frames) * old_image.width)
            #     # 旧照片向左移动，新照片从右侧进入
            
        except Exception as e:
            logger.error(f"Failed to perform slide transition: {e}")
    
    def generate_transition_frames(self, old_photo: PhotoItem, new_photo: PhotoItem) -> List[Image.Image]:
        """
        生成过渡动画帧序列
        
        Args:
            old_photo: 旧照片项
            new_photo: 新照片项
            
        Returns:
            过渡帧图片列表
        """
        if not old_photo.image or not new_photo.image:
            return []
        
        frames = []
        duration = self.config.transition_duration
        fps = self.config.transition_fps
        frame_count = int(duration * fps)
        
        if frame_count <= 0:
            return [new_photo.image]
        
        try:
            transition_type = self.config.transition_type
            
            if transition_type == TransitionType.CROSSFADE:
                # 生成交叉淡化帧
                for i in range(frame_count):
                    alpha = i / frame_count
                    # 确保两张图片尺寸一致
                    old_resized = old_photo.image.resize(self.config.window_size, Image.Resampling.LANCZOS)
                    new_resized = new_photo.image.resize(self.config.window_size, Image.Resampling.LANCZOS)
                    
                    # 转换为RGBA模式以支持alpha混合
                    if old_resized.mode != 'RGBA':
                        old_resized = old_resized.convert('RGBA')
                    if new_resized.mode != 'RGBA':
                        new_resized = new_resized.convert('RGBA')
                    
                    # 混合图片
                    blended = Image.blend(old_resized, new_resized, alpha)
                    frames.append(blended)
                    
            elif transition_type == TransitionType.FADE:
                # 先淡出旧照片，再淡入新照片
                half_frames = frame_count // 2
                
                # 淡出阶段
                for i in range(half_frames):
                    alpha = 1.0 - (i / half_frames)
                    img = old_photo.image.copy()
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    # 调整alpha通道
                    img.putalpha(int(255 * alpha))
                    frames.append(img)
                
                # 淡入阶段
                for i in range(half_frames):
                    alpha = i / half_frames
                    img = new_photo.image.copy()
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    img.putalpha(int(255 * alpha))
                    frames.append(img)
            else:
                # 默认直接返回新图片
                frames.append(new_photo.image)
            
            logger.debug(f"Generated {len(frames)} transition frames")
            return frames
            
        except Exception as e:
            logger.error(f"Failed to generate transition frames: {e}")
            return [new_photo.image]
    
    def _load_photo(self, photo: PhotoItem) -> bool:
        """
        加载照片到内存
        
        Args:
            photo: 照片项
            
        Returns:
            是否成功加载
        """
        try:
            if not photo.path.exists():
                raise FileNotFoundError(f"Photo not found: {photo.path}")
            
            # 加载并调整大小
            image = Image.open(photo.path)
            
            # 保持纵横比，缩放到窗口大小
            image.thumbnail(self.config.window_size, Image.Resampling.LANCZOS)
            
            photo.image = image
            logger.debug(f"Loaded photo: {photo.path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load photo {photo.path}: {e}")
            return False
    
    def _start_preloading(self):
        """启动预加载线程"""
        if self._preload_thread is not None and self._preload_thread.is_alive():
            return
        
        self._stop_preload = False
        self._preload_thread = threading.Thread(target=self._preload_loop, daemon=True)
        self._preload_thread.start()
    
    def _stop_preloading(self):
        """停止预加载线程"""
        self._stop_preload = True
        if self._preload_thread is not None:
            self._preload_thread.join(timeout=1.0)
    
    def _preload_loop(self):
        """预加载循环"""
        while not self._stop_preload:
            # 预加载当前照片之后的N张照片
            start_index = max(0, self._current_index)
            end_index = min(len(self._photos), start_index + self.config.preload_count)
            
            for i in range(start_index, end_index):
                if self._stop_preload:
                    break
                
                photo = self._photos[i]
                if not photo.image:
                    self._load_photo(photo)
            
            # 休眠一段时间
            time.sleep(0.5)
    
    def get_current_photo(self) -> Optional[PhotoItem]:
        """
        获取当前显示的照片
        
        Returns:
            当前照片项
        """
        return self._current_photo
    
    def get_current_image(self) -> Optional[Image.Image]:
        """
        获取当前照片的图片对象
        
        Returns:
            PIL Image对象
        """
        if self._current_photo and self._current_photo.image:
            return self._current_photo.image
        return None
    
    def get_photo_count(self) -> int:
        """
        获取照片总数
        
        Returns:
            照片数量
        """
        return len(self._photos)
    
    def add_display_callback(self, callback: Callable[[Optional[PhotoItem]], None]):
        """
        添加显示变化回调
        
        Args:
            callback: 回调函数，参数为当前照片项
        """
        self._display_callbacks.append(callback)
    
    def _notify_display_change(self):
        """通知显示变化"""
        for callback in self._display_callbacks:
            try:
                callback(self._current_photo)
            except Exception as e:
                logger.error(f"Display callback error: {e}")
    
    def save_current_photo(self, output_path: Path) -> bool:
        """
        保存当前照片到文件
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            是否成功保存
        """
        try:
            if not self._current_photo or not self._current_photo.image:
                logger.error("No photo to save")
                return False
            
            self._current_photo.image.save(output_path)
            logger.info(f"Saved current photo to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save photo: {e}")
            return False
    
    def get_photo_info(self, index: int) -> Optional[Dict[str, Any]]:
        """
        获取指定索引照片的信息
        
        Args:
            index: 照片索引
            
        Returns:
            照片信息字典
        """
        if 0 <= index < len(self._photos):
            photo = self._photos[index]
            return {
                'path': str(photo.path),
                'start_time': photo.start_time,
                'duration': photo.duration,
                'loaded': photo.image is not None,
                'size': photo.image.size if photo.image else None
            }
        return None
    
    def cleanup(self):
        """清理资源"""
        self._stop_preloading()
        
        # 清理图片内存
        for photo in self._photos:
            if photo.image:
                photo.image.close()
                photo.image = None
        
        self._photos.clear()
        self._current_photo = None
        logger.info("PhotoDisplayManager cleaned up")


def main():
    """测试函数"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Photo Display Manager Test')
    parser.add_argument('photos_dir', type=Path, help='Photos directory')
    parser.add_argument('--timeline', type=Path, help='Timeline JSON file')
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 创建管理器
        manager = PhotoDisplayManager()
        
        # 加载时间轴
        if args.timeline and args.timeline.exists():
            with open(args.timeline, 'r') as f:
                timeline_data = json.load(f)
                timeline_items = timeline_data.get('timeline', [])
        else:
            # 创建简单的时间轴
            photos = sorted(args.photos_dir.glob('*.jpg'))
            timeline_items = [
                {'photo': photo.name, 'duration': 5.0}
                for photo in photos
            ]
        
        manager.load_timeline(timeline_items, args.photos_dir)
        
        print(f"\nLoaded {manager.get_photo_count()} photos")
        print("\nSimulating timeline playback...")
        
        # 模拟时间流逝
        total_duration = sum(item['duration'] for item in timeline_items)
        time_step = 1.0  # 每秒更新一次
        
        for t in range(0, int(total_duration) + 1, int(time_step)):
            if manager.update(float(t)):
                current = manager.get_current_photo()
                if current:
                    print(f"[{t:3d}s] Displaying: {current.path.name}")
            
            time.sleep(0.1)  # 实际中这会是实时更新
        
        manager.cleanup()
        print("\nDone!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
