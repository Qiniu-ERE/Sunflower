"""
Image Processing Service
图片处理服务 - 提取图片元数据和处理图片文件
"""

from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageMetadata:
    """图片元数据"""
    
    def __init__(self, file_path: Path, width: int, height: int, 
                 format: str, file_size: int, mode: Optional[str] = None):
        self.file_path = file_path
        self.width = width
        self.height = height
        self.format = format
        self.file_size = file_size
        self.mode = mode
        
    @property
    def aspect_ratio(self) -> float:
        """计算宽高比"""
        return self.width / self.height if self.height > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'file_path': str(self.file_path),
            'filename': self.file_path.name,
            'width': self.width,
            'height': self.height,
            'format': self.format,
            'file_size': self.file_size,
            'mode': self.mode,
            'aspect_ratio': self.aspect_ratio
        }
    
    def __repr__(self):
        return f"ImageMetadata(file={self.file_path.name}, size={self.width}x{self.height}, format={self.format})"


class ImageService:
    """图片处理服务"""
    
    @staticmethod
    def get_metadata(image_file: Path) -> ImageMetadata:
        """
        提取图片元数据
        
        Args:
            image_file: 图片文件路径
            
        Returns:
            ImageMetadata对象
            
        Raises:
            FileNotFoundError: 文件不存在
            RuntimeError: 无法提取元数据
        """
        if not image_file.exists():
            raise FileNotFoundError(f"Image file not found: {image_file}")
        
        logger.info(f"Extracting metadata from: {image_file.name}")
        
        try:
            from PIL import Image
            
            with Image.open(image_file) as img:
                metadata = ImageMetadata(
                    file_path=image_file,
                    width=img.width,
                    height=img.height,
                    format=img.format or 'unknown',
                    file_size=image_file.stat().st_size,
                    mode=img.mode
                )
                
            logger.info(f"Metadata extracted: {metadata}")
            return metadata
            
        except ImportError:
            raise RuntimeError("PIL/Pillow library not installed. Install with: pip install Pillow")
        except Exception as e:
            raise RuntimeError(f"Failed to extract image metadata: {e}") from e
    
    @staticmethod
    def validate_image_file(image_file: Path) -> bool:
        """
        验证图片文件是否有效
        
        Args:
            image_file: 图片文件路径
            
        Returns:
            文件是否有效
        """
        if not image_file.exists():
            logger.error(f"Image file does not exist: {image_file}")
            return False
        
        # 检查文件扩展名
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        if image_file.suffix.lower() not in valid_extensions:
            logger.warning(f"Unsupported image format: {image_file.suffix}")
            return False
        
        # 尝试提取元数据来验证文件
        try:
            metadata = ImageService.get_metadata(image_file)
            if metadata.width <= 0 or metadata.height <= 0:
                logger.error(f"Invalid image dimensions: {metadata.width}x{metadata.height}")
                return False
            return True
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False
    
    @staticmethod
    def get_dimensions(image_file: Path) -> Tuple[int, int]:
        """
        获取图片尺寸（快捷方法）
        
        Args:
            image_file: 图片文件路径
            
        Returns:
            (width, height) 元组
        """
        metadata = ImageService.get_metadata(image_file)
        return (metadata.width, metadata.height)
    
    @staticmethod
    def resize_image(image_file: Path, output_file: Path, 
                    target_size: Tuple[int, int], maintain_aspect: bool = True):
        """
        调整图片大小
        
        Args:
            image_file: 源图片文件路径
            output_file: 输出图片文件路径
            target_size: 目标尺寸 (width, height)
            maintain_aspect: 是否保持宽高比
        """
        try:
            from PIL import Image
            
            with Image.open(image_file) as img:
                if maintain_aspect:
                    img.thumbnail(target_size, Image.Resampling.LANCZOS)
                else:
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                
                img.save(output_file, quality=95)
                logger.info(f"Image resized: {output_file.name}")
                
        except ImportError:
            raise RuntimeError("PIL/Pillow library not installed. Install with: pip install Pillow")
        except Exception as e:
            raise RuntimeError(f"Failed to resize image: {e}") from e
    
    @staticmethod
    def crop_to_aspect_ratio(image_file: Path, output_file: Path, 
                            target_ratio: float = 16/9):
        """
        裁剪图片到指定宽高比
        
        Args:
            image_file: 源图片文件路径
            output_file: 输出图片文件路径
            target_ratio: 目标宽高比（默认16:9）
        """
        try:
            from PIL import Image
            
            with Image.open(image_file) as img:
                width, height = img.size
                current_ratio = width / height
                
                if abs(current_ratio - target_ratio) < 0.01:
                    # 已经是目标比例，直接保存
                    img.save(output_file)
                    return
                
                if current_ratio > target_ratio:
                    # 图片太宽，裁剪左右
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    box = (left, 0, left + new_width, height)
                else:
                    # 图片太高，裁剪上下
                    new_height = int(width / target_ratio)
                    top = (height - new_height) // 2
                    box = (0, top, width, top + new_height)
                
                cropped = img.crop(box)
                cropped.save(output_file, quality=95)
                logger.info(f"Image cropped to {target_ratio:.2f}: {output_file.name}")
                
        except ImportError:
            raise RuntimeError("PIL/Pillow library not installed. Install with: pip install Pillow")
        except Exception as e:
            raise RuntimeError(f"Failed to crop image: {e}") from e
