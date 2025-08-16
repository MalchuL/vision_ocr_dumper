"""Configuration utilities for OCR Annotation Dumper."""

import os
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv

# Load environment variables from .env file if not already loaded
load_dotenv()


class Config:
    """Configuration manager for OCR Annotation Dumper."""
    
    # Supported image formats
    SUPPORTED_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
        '.raw', '.ico', '.pdf', '.tiff', '.tif'
    }
    
    # Default output directory
    DEFAULT_OUTPUT_DIR = Path('./ocr_output')
    
    # Google Cloud Vision API limits
    MAX_FILE_SIZE_MB = 20  # 20MB limit for Vision API
    MAX_BATCH_SIZE = 16    # Maximum files in a single batch request
    
    @staticmethod
    def get_credentials_path() -> Optional[str]:
        """Get Google Cloud credentials path from environment."""
        return os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    @staticmethod
    def get_output_dir() -> Path:
        """Get default output directory from environment or use default."""
        output_dir = os.environ.get('OCR_OUTPUT_DIR', './ocr_output')
        return Path(output_dir)
    
    @staticmethod
    def get_batch_size() -> int:
        """Get batch size from environment or use default."""
        try:
            return int(os.environ.get('OCR_BATCH_SIZE', '16'))
        except ValueError:
            return 16
    
    @staticmethod
    def get_log_level() -> str:
        """Get log level from environment or use default."""
        return os.environ.get('OCR_LOG_LEVEL', 'INFO').upper()
    
    @staticmethod
    def is_recursive_default() -> bool:
        """Get default recursive setting from environment."""
        return os.environ.get('OCR_RECURSIVE_DEFAULT', 'false').lower() in ('true', '1', 'yes')
    
    @staticmethod
    def validate_credentials(credentials_path: Optional[str] = None) -> bool:
        """Validate Google Cloud credentials."""
        cred_path = credentials_path or Config.get_credentials_path()
        
        if not cred_path:
            return False
        
        cred_file = Path(cred_path)
        return cred_file.exists() and cred_file.is_file()
    
    @staticmethod
    def get_file_size_mb(file_path: Path) -> float:
        """Get file size in megabytes."""
        return file_path.stat().st_size / (1024 * 1024)
    
    @staticmethod
    def is_supported_format(file_path: Path) -> bool:
        """Check if file format is supported."""
        return file_path.suffix.lower() in Config.SUPPORTED_EXTENSIONS
    
    @staticmethod
    def filter_valid_files(file_paths: list[Path]) -> Dict[str, list]:
        """Filter and categorize files based on validity."""
        valid_files = []
        invalid_files = []
        oversized_files = []
        
        for file_path in file_paths:
            if not Config.is_supported_format(file_path):
                invalid_files.append(file_path)
            elif Config.get_file_size_mb(file_path) > Config.MAX_FILE_SIZE_MB:
                oversized_files.append(file_path)
            else:
                valid_files.append(file_path)
        
        return {
            'valid': valid_files,
            'invalid': invalid_files,
            'oversized': oversized_files
        }
    
    @staticmethod
    def create_output_structure(output_dir: Path) -> Dict[str, Path]:
        """Create output directory structure."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        subdirs = {
            'annotations': output_dir / 'annotations',
            'logs': output_dir / 'logs',
            'reports': output_dir / 'reports'
        }
        
        for subdir in subdirs.values():
            subdir.mkdir(parents=True, exist_ok=True)
        
        return subdirs


# Environment variable names
ENV_VARS = {
    'GOOGLE_APPLICATION_CREDENTIALS': 'Path to Google Cloud credentials JSON file',
    'OCR_OUTPUT_DIR': 'Default output directory for OCR annotations',
    'OCR_BATCH_SIZE': 'Batch size for processing multiple files',
    'OCR_LOG_LEVEL': 'Logging level (DEBUG, INFO, WARNING, ERROR)',
}


def print_env_help():
    """Print help for environment variables."""
    print("Environment Variables:")
    print("=" * 50)
    for var, description in ENV_VARS.items():
        current_value = os.environ.get(var, 'Not set')
        print(f"{var}: {description}")
        print(f"  Current value: {current_value}")
        print()
