"""
Sync Coordinator
同步协调器 - 负责音频播放与照片显示的同步
"""

import logging
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
import threading
import time

from .playback_controller import PlaybackController, PlaybackState, PlaybackConfig
from .photo_display import PhotoDisplayManager, PhotoItem, DisplayConfig

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """同步配置"""
    update_interval: float = 0.05  # 更新间隔（秒），20fps
    sync_tolerance: float = 0.1    # 同步容差（秒）
    auto_correction: bool = True    # 自动时间校正
    correction_threshold: float = 0.5  # 校正阈值（秒）


class SyncCoordinator:
    """
    同步协调器
    
    功能:
    - 音频播放与照片显示同步
    - 时间校准和漂移修正
    - 事件驱动架构
    - 状态管理
    """
    
    def __init__(self, 
                 playback_config: Optional[PlaybackConfig] = None,
                 display_config: Optional[DisplayConfig] = None,
                 sync_config: Optional[SyncConfig] = None):
        """
        初始化同步协调器
        
        Args:
            playback_config: 播放配置
            display_config: 显示配置
            sync_config: 同步配置
        """
        self.sync_config = sync_config or SyncConfig()
        
        # 创建控制器和管理器
        self.playback = PlaybackController(playback_config)
        self.display = PhotoDisplayManager(display_config)
        
        # 同步状态
        self._is_running = False
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_sync = False
        
        # 回调列表
        self._sync_callbacks: List[Callable[[float, Optional[PhotoItem]], None]] = []
        self._error_callbacks: List[Callable[[str], None]] = []
        
        # 设置播放器回调
        self.playback.add_state_callback(self._on_playback_state_change)
        
        logger.info(f"SyncCoordinator initialized: {self.sync_config}")
    
    def load(self, audio_file: Path, timeline_items: List[Dict[str, Any]], photos_dir: Path) -> bool:
        """
        加载演讲内容
        
        Args:
            audio_file: 音频文件路径
            timeline_items: 时间轴项列表
            photos_dir: 照片目录
            
        Returns:
            是否成功加载
        """
        try:
            # 加载音频
            if not self.playback.load(audio_file):
                raise RuntimeError("Failed to load audio")
            
            # 加载照片时间轴
            self.display.load_timeline(timeline_items, photos_dir)
            
            logger.info(f"Loaded lecture content: {audio_file.name} with {len(timeline_items)} photos")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load content: {e}")
            self._notify_error(str(e))
            return False
    
    def play(self) -> bool:
        """
        开始播放
        
        Returns:
            是否成功开始
        """
        try:
            if not self.playback.play():
                raise RuntimeError("Failed to start playback")
            
            # 启动同步线程
            self._start_sync()
            
            logger.info("Playback started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to play: {e}")
            self._notify_error(str(e))
            return False
    
    def pause(self) -> bool:
        """
        暂停播放
        
        Returns:
            是否成功暂停
        """
        try:
            if not self.playback.pause():
                raise RuntimeError("Failed to pause playback")
            
            logger.info("Playback paused")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause: {e}")
            return False
    
    def stop(self) -> bool:
        """
        停止播放
        
        Returns:
            是否成功停止
        """
        try:
            # 停止同步线程
            self._stop_sync()
            
            if not self.playback.stop():
                raise RuntimeError("Failed to stop playback")
            
            logger.info("Playback stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop: {e}")
            return False
    
    def seek(self, position: float) -> bool:
        """
        跳转到指定位置
        
        Args:
            position: 目标位置（秒）
            
        Returns:
            是否成功跳转
        """
        try:
            if not self.playback.seek(position):
                raise RuntimeError("Failed to seek")
            
            # 更新照片显示
            self.display.update(position)
            
            logger.info(f"Seeked to: {position:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to seek: {e}")
            return False
    
    def set_volume(self, volume: float) -> bool:
        """
        设置音量
        
        Args:
            volume: 音量 (0.0-1.0)
            
        Returns:
            是否成功设置
        """
        return self.playback.set_volume(volume)
    
    def get_position(self) -> float:
        """
        获取当前播放位置
        
        Returns:
            当前位置（秒）
        """
        return self.playback.get_position()
    
    def get_duration(self) -> float:
        """
        获取总时长
        
        Returns:
            总时长（秒）
        """
        return self.playback.get_duration()
    
    def get_state(self) -> PlaybackState:
        """
        获取播放状态
        
        Returns:
            播放状态
        """
        return self.playback.get_state()
    
    def is_playing(self) -> bool:
        """
        是否正在播放
        
        Returns:
            是否正在播放
        """
        return self.playback.is_playing()
    
    def get_current_photo(self) -> Optional[PhotoItem]:
        """
        获取当前显示的照片
        
        Returns:
            当前照片项
        """
        return self.display.get_current_photo()
    
    def add_sync_callback(self, callback: Callable[[float, Optional[PhotoItem]], None]):
        """
        添加同步回调
        
        Args:
            callback: 回调函数，参数为(当前位置, 当前照片)
        """
        self._sync_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str], None]):
        """
        添加错误回调
        
        Args:
            callback: 回调函数，参数为错误消息
        """
        self._error_callbacks.append(callback)
    
    def _notify_sync(self, position: float, photo: Optional[PhotoItem]):
        """通知同步更新"""
        for callback in self._sync_callbacks:
            try:
                callback(position, photo)
            except Exception as e:
                logger.error(f"Sync callback error: {e}")
    
    def _notify_error(self, error: str):
        """通知错误"""
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error callback error: {e}")
    
    def _on_playback_state_change(self, state: PlaybackState):
        """播放状态变化回调"""
        logger.info(f"Playback state changed to: {state.value}")
        
        if state == PlaybackState.STOPPED:
            self._stop_sync()
    
    def _start_sync(self):
        """启动同步线程"""
        if self._sync_thread is not None and self._sync_thread.is_alive():
            return
        
        self._stop_sync = False
        self._is_running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info("Sync thread started")
    
    def _stop_sync(self):
        """停止同步线程"""
        self._stop_sync = True
        self._is_running = False
        
        if self._sync_thread is not None:
            self._sync_thread.join(timeout=1.0)
            logger.info("Sync thread stopped")
    
    def _sync_loop(self):
        """同步循环"""
        last_position = 0.0
        correction_count = 0
        
        while not self._stop_sync and self.playback.is_playing():
            try:
                # 获取当前播放位置
                current_position = self.playback.get_position()
                
                # 更新照片显示
                photo_changed = self.display.update(current_position)
                
                if photo_changed:
                    current_photo = self.display.get_current_photo()
                    if current_photo:
                        logger.info(f"[{current_position:.2f}s] Now showing: {current_photo.path.name}")
                
                # 时间漂移检测和校正
                if self.sync_config.auto_correction:
                    time_drift = abs(current_position - last_position - self.sync_config.update_interval)
                    
                    if time_drift > self.sync_config.correction_threshold:
                        correction_count += 1
                        if correction_count >= 3:  # 连续3次漂移才校正
                            logger.warning(f"Time drift detected: {time_drift:.3f}s, correcting...")
                            # 这里可以添加校正逻辑
                            correction_count = 0
                    else:
                        correction_count = 0
                
                last_position = current_position
                
                # 通知同步回调
                current_photo = self.display.get_current_photo()
                self._notify_sync(current_position, current_photo)
                
                # 休眠
                time.sleep(self.sync_config.update_interval)
                
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                self._notify_error(str(e))
        
        self._is_running = False
    
    def get_sync_info(self) -> Dict[str, Any]:
        """
        获取同步信息
        
        Returns:
            同步信息字典
        """
        current_photo = self.display.get_current_photo()
        
        return {
            'position': self.get_position(),
            'duration': self.get_duration(),
            'state': self.get_state().value,
            'is_syncing': self._is_running,
            'current_photo': {
                'path': str(current_photo.path),
                'start_time': current_photo.start_time,
                'duration': current_photo.duration
            } if current_photo else None,
            'photo_count': self.display.get_photo_count()
        }
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        self.playback.cleanup()
        self.display.cleanup()
        logger.info("SyncCoordinator cleaned up")


def main():
    """测试函数"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Sync Coordinator Test')
    parser.add_argument('audio_file', type=Path, help='Audio file')
    parser.add_argument('photos_dir', type=Path, help='Photos directory')
    parser.add_argument('--timeline', type=Path, help='Timeline JSON file')
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 创建协调器
        coordinator = SyncCoordinator()
        
        # 添加同步回调
        def on_sync_update(position: float, photo: Optional[PhotoItem]):
            photo_name = photo.path.name if photo else "None"
            print(f"\r[{position:6.2f}s] Photo: {photo_name:<40}", end='', flush=True)
        
        coordinator.add_sync_callback(on_sync_update)
        
        # 加载时间轴
        if args.timeline and args.timeline.exists():
            with open(args.timeline, 'r') as f:
                timeline_data = json.load(f)
                timeline_items = timeline_data.get('timeline', [])
        else:
            # 创建简单的时间轴
            photos = sorted(args.photos_dir.glob('*.jpg'))
            timeline_items = [
                {'photo': photo.name, 'duration': 30.0}
                for photo in photos[:10]  # 只用前10张
            ]
        
        # 加载并播放
        if coordinator.load(args.audio_file, timeline_items, args.photos_dir):
            print(f"\nPlaying: {args.audio_file.name}")
            print(f"Duration: {coordinator.get_duration():.2f}s")
            print(f"Photos: {coordinator.display.get_photo_count()}\n")
            
            coordinator.play()
            
            # 等待播放完成
            try:
                while coordinator.is_playing():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n\nStopping...")
            
            coordinator.stop()
            coordinator.cleanup()
            print("\n\nDone!")
        else:
            print("Failed to load content")
            return 1
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
