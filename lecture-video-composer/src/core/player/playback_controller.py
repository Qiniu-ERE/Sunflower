"""
Playback Controller
播放控制器 - 负责音频播放控制
"""

import logging
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import time

# 尝试导入pygame用于音频播放
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logging.warning("pygame not available. Install with: pip install pygame")

logger = logging.getLogger(__name__)


class PlaybackState(Enum):
    """播放状态枚举"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class PlaybackConfig:
    """播放配置"""
    volume: float = 1.0  # 音量 (0.0-1.0)
    speed: float = 1.0   # 播放速度 (0.5-2.0，注意：pygame不原生支持，通过时间轴模拟)
    buffer_size: int = 4096  # 缓冲区大小
    speed_change_smooth: bool = True  # 是否平滑切换速度


class PlaybackController:
    """
    播放控制器
    
    功能:
    - 音频播放控制（播放/暂停/停止/跳转）
    - 播放进度追踪
    - 音量控制
    - 倍速播放（如果支持）
    """
    
    def __init__(self, config: Optional[PlaybackConfig] = None):
        """
        初始化播放控制器
        
        Args:
            config: 播放配置
        """
        if not PYGAME_AVAILABLE:
            raise RuntimeError(
                "pygame is required for audio playback. "
                "Install with: pip install pygame"
            )
        
        self.config = config or PlaybackConfig()
        self._state = PlaybackState.STOPPED
        self._audio_file: Optional[Path] = None
        self._duration: float = 0.0
        self._position: float = 0.0
        self._position_lock = threading.Lock()
        self._position_callbacks: list[Callable[[float], None]] = []
        self._state_callbacks: list[Callable[[PlaybackState], None]] = []
        self._update_thread: Optional[threading.Thread] = None
        self._stop_update = False
        
        # 初始化pygame mixer
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=self.config.buffer_size)
        pygame.mixer.music.set_volume(self.config.volume)
        
        logger.info(f"PlaybackController initialized: {self.config}")
    
    def load(self, audio_file: Path) -> bool:
        """
        加载音频文件
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            是否成功加载
        """
        try:
            if not audio_file.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_file}")
            
            # 停止当前播放
            if self._state != PlaybackState.STOPPED:
                self.stop()
            
            # 加载音频文件
            pygame.mixer.music.load(str(audio_file))
            self._audio_file = audio_file
            
            # 获取音频时长（使用pygame的方法不太准确，可能需要其他库）
            # 这里使用一个估算方法或者从外部获取
            self._duration = self._get_audio_duration(audio_file)
            self._position = 0.0
            
            logger.info(f"Loaded audio: {audio_file.name} (duration: {self._duration:.2f}s)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            return False
    
    def _get_audio_duration(self, audio_file: Path) -> float:
        """
        获取音频时长
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            音频时长（秒）
        """
        try:
            # 使用ffprobe获取准确的时长
            import subprocess
            import json
            
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(audio_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info = json.loads(result.stdout)
                return float(info['format']['duration'])
        except Exception as e:
            logger.warning(f"Failed to get accurate duration: {e}")
        
        # 如果失败，返回0（调用者需要从其他地方获取）
        return 0.0
    
    def play(self) -> bool:
        """
        播放音频
        
        Returns:
            是否成功开始播放
        """
        try:
            if self._audio_file is None:
                logger.error("No audio file loaded")
                return False
            
            if self._state == PlaybackState.PLAYING:
                logger.warning("Already playing")
                return True
            
            if self._state == PlaybackState.PAUSED:
                # 从暂停恢复
                pygame.mixer.music.unpause()
            else:
                # 从头开始播放
                pygame.mixer.music.play()
            
            self._state = PlaybackState.PLAYING
            self._notify_state_change()
            
            # 启动位置更新线程
            self._start_position_update()
            
            logger.info("Playback started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to play: {e}")
            return False
    
    def pause(self) -> bool:
        """
        暂停播放
        
        Returns:
            是否成功暂停
        """
        try:
            if self._state != PlaybackState.PLAYING:
                logger.warning("Not playing")
                return False
            
            pygame.mixer.music.pause()
            self._state = PlaybackState.PAUSED
            self._notify_state_change()
            
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
            pygame.mixer.music.stop()
            self._state = PlaybackState.STOPPED
            self._position = 0.0
            self._notify_state_change()
            
            # 停止位置更新线程
            self._stop_position_update()
            
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
            if self._audio_file is None:
                logger.error("No audio file loaded")
                return False
            
            if position < 0 or position > self._duration:
                logger.error(f"Invalid position: {position}")
                return False
            
            # pygame的seek功能有限，需要重新加载并播放
            was_playing = self._state == PlaybackState.PLAYING
            
            pygame.mixer.music.stop()
            pygame.mixer.music.load(str(self._audio_file))
            
            # pygame.mixer.music.set_pos()接受秒数
            # 但并不是所有格式都支持
            try:
                pygame.mixer.music.set_pos(position)
            except:
                logger.warning("set_pos not supported, using play with start position")
                pygame.mixer.music.play(start=position)
            
            with self._position_lock:
                self._position = position
            
            if was_playing:
                pygame.mixer.music.play()
                self._state = PlaybackState.PLAYING
            
            self._notify_position_change()
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
        try:
            if not 0.0 <= volume <= 1.0:
                raise ValueError(f"Invalid volume: {volume}. Must be between 0.0 and 1.0")
            
            pygame.mixer.music.set_volume(volume)
            self.config.volume = volume
            logger.info(f"Volume set to: {volume:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False
    
    def set_speed(self, speed: float) -> bool:
        """
        设置播放速度
        
        注意：pygame.mixer不原生支持倍速播放，此方法通过调整时间轴来模拟倍速效果。
        这意味着音频实际以正常速度播放，但位置更新会根据速度倍率调整。
        
        要实现真正的倍速播放（包括音高变化），需要使用其他库如pydub + ffmpeg。
        
        Args:
            speed: 播放速度 (0.5-2.0)
                  1.0 = 正常速度
                  0.5 = 半速播放
                  1.5 = 1.5倍速
                  2.0 = 2倍速
            
        Returns:
            是否成功设置
        """
        try:
            if not 0.5 <= speed <= 2.0:
                raise ValueError(f"Invalid speed: {speed}. Must be between 0.5 and 2.0")
            
            old_speed = self.config.speed
            self.config.speed = speed
            
            logger.info(f"Playback speed changed: {old_speed:.2f}x -> {speed:.2f}x")
            logger.warning(
                "Note: pygame does not support native speed change. "
                "Speed is simulated by adjusting timeline position updates. "
                "Audio pitch will NOT change."
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set speed: {e}")
            return False
    
    def get_speed(self) -> float:
        """
        获取当前播放速度
        
        Returns:
            当前播放速度
        """
        return self.config.speed
    
    def cycle_speed(self, speeds: list[float] = None) -> float:
        """
        循环切换播放速度
        
        Args:
            speeds: 可选的速度列表，默认为 [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
            
        Returns:
            新的播放速度
        """
        if speeds is None:
            speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        
        try:
            current_speed = self.config.speed
            # 找到下一个速度
            try:
                current_index = speeds.index(current_speed)
                next_index = (current_index + 1) % len(speeds)
            except ValueError:
                # 当前速度不在列表中，使用第一个
                next_index = 0
            
            new_speed = speeds[next_index]
            self.set_speed(new_speed)
            return new_speed
            
        except Exception as e:
            logger.error(f"Failed to cycle speed: {e}")
            return self.config.speed
    
    def get_position(self) -> float:
        """
        获取当前播放位置
        
        Returns:
            当前位置（秒）
        """
        with self._position_lock:
            return self._position
    
    def get_duration(self) -> float:
        """
        获取音频总时长
        
        Returns:
            总时长（秒）
        """
        return self._duration
    
    def get_state(self) -> PlaybackState:
        """
        获取当前播放状态
        
        Returns:
            播放状态
        """
        return self._state
    
    def is_playing(self) -> bool:
        """
        是否正在播放
        
        Returns:
            是否正在播放
        """
        return self._state == PlaybackState.PLAYING
    
    def add_position_callback(self, callback: Callable[[float], None]):
        """
        添加位置变化回调
        
        Args:
            callback: 回调函数，参数为当前位置（秒）
        """
        self._position_callbacks.append(callback)
    
    def add_state_callback(self, callback: Callable[[PlaybackState], None]):
        """
        添加状态变化回调
        
        Args:
            callback: 回调函数，参数为新状态
        """
        self._state_callbacks.append(callback)
    
    def _notify_position_change(self):
        """通知位置变化"""
        position = self.get_position()
        for callback in self._position_callbacks:
            try:
                callback(position)
            except Exception as e:
                logger.error(f"Position callback error: {e}")
    
    def _notify_state_change(self):
        """通知状态变化"""
        for callback in self._state_callbacks:
            try:
                callback(self._state)
            except Exception as e:
                logger.error(f"State callback error: {e}")
    
    def _start_position_update(self):
        """启动位置更新线程"""
        if self._update_thread is not None and self._update_thread.is_alive():
            return
        
        self._stop_update = False
        self._update_thread = threading.Thread(target=self._update_position_loop, daemon=True)
        self._update_thread.start()
    
    def _stop_position_update(self):
        """停止位置更新线程"""
        self._stop_update = True
        if self._update_thread is not None:
            self._update_thread.join(timeout=1.0)
    
    def _update_position_loop(self):
        """位置更新循环（支持倍速）"""
        last_time = time.time()
        
        while not self._stop_update and self._state == PlaybackState.PLAYING:
            current_time = time.time()
            elapsed = current_time - last_time
            last_time = current_time
            
            # 更新位置（应用播放速度）
            with self._position_lock:
                # 使用速度倍率调整位置增量
                self._position += elapsed * self.config.speed
                if self._position >= self._duration:
                    self._position = self._duration
                    self._stop_update = True
            
            # 通知位置变化
            self._notify_position_change()
            
            # 检查是否播放结束
            if not pygame.mixer.music.get_busy() and self._state == PlaybackState.PLAYING:
                self._state = PlaybackState.STOPPED
                self._notify_state_change()
                break
            
            # 休眠一小段时间
            time.sleep(0.05)  # 20fps更新频率
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        pygame.mixer.quit()
        logger.info("PlaybackController cleaned up")


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Playback Controller Test')
    parser.add_argument('audio_file', type=Path, help='Audio file to play')
    parser.add_argument('--volume', type=float, default=1.0, help='Volume (0.0-1.0)')
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 创建控制器
        controller = PlaybackController(PlaybackConfig(volume=args.volume))
        
        # 添加位置回调
        def on_position_change(position: float):
            print(f"\rPosition: {position:.2f}s / {controller.get_duration():.2f}s", end='', flush=True)
        
        controller.add_position_callback(on_position_change)
        
        # 加载并播放
        if controller.load(args.audio_file):
            print(f"\nPlaying: {args.audio_file.name}")
            print(f"Duration: {controller.get_duration():.2f}s")
            print("\nControls: [space] pause/resume, [s] stop, [q] quit")
            
            controller.play()
            
            # 简单的键盘控制（需要终端支持）
            try:
                while controller.get_state() != PlaybackState.STOPPED:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n\nStopping...")
            
            controller.stop()
            controller.cleanup()
            print("\nDone!")
        else:
            print("Failed to load audio file")
            return 1
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
