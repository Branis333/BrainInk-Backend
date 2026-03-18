"""
Image compression and handling service for course images
Compresses images to reduce storage size by ~50% while maintaining quality
"""

import io
import base64
from typing import Optional, Tuple
from PIL import Image


class ImageService:
    """Service for handling image compression and encoding/decoding"""
    
    # Maximum image dimensions after compression
    MAX_WIDTH = 800
    MAX_HEIGHT = 600
    
    # JPEG quality for compression (0-95)
    JPEG_QUALITY = 75
    
    # Supported image formats
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    # Maximum file size before compression (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024
    
    @staticmethod
    def compress_image(image_data: bytes, filename: str = "image") -> Optional[bytes]:
        """
        Compress image data to reduce file size by ~50%
        
        Args:
            image_data: Raw image bytes
            filename: Original filename (for extension detection)
            
        Returns:
            Compressed image bytes or None if compression fails
            
        Raises:
            ValueError: If image format is not supported
        """
        try:
            # Validate file size before processing
            if len(image_data) > ImageService.MAX_FILE_SIZE:
                raise ValueError(f"Image file too large. Maximum size: 5MB")
            
            # Validate file extension
            file_ext = None
            if '.' in filename:
                file_ext = '.' + filename.split('.')[-1].lower()
                if file_ext not in ImageService.SUPPORTED_FORMATS:
                    raise ValueError(
                        f"Unsupported image format: {file_ext}. "
                        f"Supported formats: {', '.join(ImageService.SUPPORTED_FORMATS)}"
                    )
            
            # Open image from bytes
            img = Image.open(io.BytesIO(image_data))
            
            # Convert RGBA to RGB for JPEG compression (JPEG doesn't support transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                # Paste image with alpha channel as mask
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate new dimensions (maintain aspect ratio)
            img.thumbnail((ImageService.MAX_WIDTH, ImageService.MAX_HEIGHT), Image.Resampling.LANCZOS)
            
            # Compress and save as JPEG
            output = io.BytesIO()
            img.save(
                output,
                format='JPEG',
                quality=ImageService.JPEG_QUALITY,
                optimize=True
            )
            
            compressed_data = output.getvalue()
            
            # Log compression ratio
            original_size = len(image_data)
            compressed_size = len(compressed_data)
            ratio = ((original_size - compressed_size) / original_size) * 100
            
            print(f"📸 Image compressed: {original_size:,} bytes → {compressed_size:,} bytes ({ratio:.1f}% reduction)")
            
            return compressed_data
            
        except Exception as e:
            print(f"❌ Error compressing image: {str(e)}")
            raise ValueError(f"Failed to compress image: {str(e)}")
    
    @staticmethod
    def encode_image_to_base64(image_data: Optional[bytes]) -> Optional[str]:
        """
        Encode image bytes to base64 string
        
        Args:
            image_data: Raw or compressed image bytes
            
        Returns:
            Base64 encoded string or None
        """
        if image_data is None:
            return None
        
        try:
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            print(f"❌ Error encoding image to base64: {str(e)}")
            return None
    
    @staticmethod
    def decode_image_from_base64(image_base64: Optional[str]) -> Optional[bytes]:
        """
        Decode base64 string to image bytes
        
        Args:
            image_base64: Base64 encoded image string
            
        Returns:
            Image bytes or None
        """
        if image_base64 is None or image_base64 == "":
            return None
        
        try:
            return base64.b64decode(image_base64)
        except Exception as e:
            print(f"❌ Error decoding image from base64: {str(e)}")
            return None
    
    @staticmethod
    def process_and_compress_image(image_data: bytes, filename: str = "image") -> Tuple[bytes, str]:
        """
        Process image: compress and encode to base64
        
        Args:
            image_data: Raw image bytes
            filename: Original filename
            
        Returns:
            Tuple of (compressed_bytes, base64_string)
        """
        # Compress image
        compressed = ImageService.compress_image(image_data, filename)
        
        # Encode to base64 for storage
        base64_str = ImageService.encode_image_to_base64(compressed)
        
        return compressed, base64_str


# Global service instance
image_service = ImageService()
