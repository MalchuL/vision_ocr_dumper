"""Utility functions for OCR Annotation Dumper."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from rich.logging import RichHandler


def setup_logging(log_level: str = "INFO", log_dir: Optional[Path] = None) -> logging.Logger:
    """Set up logging with Rich handler and optional file output."""
    logger = logging.getLogger("ocr_annotation_dumper")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Rich console handler
    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    formatter = logging.Formatter(
        fmt="%(message)s",
        datefmt="[%X]"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if log directory is provided
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"ocr_dumper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def save_json(data: Any, file_path: Path, indent: int = 2) -> bool:
    """Save data to JSON file with error handling."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save JSON to {file_path}: {e}")
        return False


def load_json(file_path: Path) -> Optional[Any]:
    """Load data from JSON file with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load JSON from {file_path}: {e}")
        return None


def extract_text_content(annotations: Dict[str, Any]) -> str:
    """Extract plain text content from OCR annotations."""
    if 'document_text' in annotations and annotations['document_text']:
        return annotations['document_text']
    
    # Fallback to text annotations
    if 'text_annotations' in annotations and annotations['text_annotations']:
        # First annotation usually contains the full text
        return annotations['text_annotations'][0].get('description', '')
    
    return ''


def calculate_reading_statistics(annotations: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate reading statistics from OCR annotations."""
    text = extract_text_content(annotations)
    
    stats = {
        'character_count': len(text),
        'word_count': len(text.split()) if text else 0,
        'line_count': len(text.splitlines()) if text else 0,
        'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]) if text else 0,
    }
    
    # Calculate confidence statistics from pages
    confidences = []
    for page in annotations.get('pages', []):
        if 'confidence' in page:
            confidences.append(page['confidence'])
        
        for block in page.get('blocks', []):
            if 'confidence' in block:
                confidences.append(block['confidence'])
    
    if confidences:
        stats.update({
            'avg_confidence': sum(confidences) / len(confidences),
            'min_confidence': min(confidences),
            'max_confidence': max(confidences),
            'confidence_std': calculate_std(confidences),
        })
    else:
        stats.update({
            'avg_confidence': 0.0,
            'min_confidence': 0.0,
            'max_confidence': 0.0,
            'confidence_std': 0.0,
        })
    
    return stats


def calculate_std(values: List[float]) -> float:
    """Calculate standard deviation of a list of values."""
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


def create_summary_report(all_annotations: List[Dict[str, Any]], output_path: Path) -> bool:
    """Create a summary report of all processed annotations."""
    try:
        report = {
            'generation_time': datetime.now().isoformat(),
            'total_files': len(all_annotations),
            'files': [],
            'overall_statistics': {
                'total_characters': 0,
                'total_words': 0,
                'total_lines': 0,
                'avg_confidence': 0.0,
            }
        }
        
        all_confidences = []
        
        for annotations in all_annotations:
            stats = calculate_reading_statistics(annotations)
            
            file_info = {
                'file_name': annotations.get('file_name', 'unknown'),
                'file_path': annotations.get('file_path', 'unknown'),
                'statistics': stats,
            }
            
            report['files'].append(file_info)
            
            # Accumulate overall statistics
            report['overall_statistics']['total_characters'] += stats['character_count']
            report['overall_statistics']['total_words'] += stats['word_count']
            report['overall_statistics']['total_lines'] += stats['line_count']
            
            if stats['avg_confidence'] > 0:
                all_confidences.append(stats['avg_confidence'])
        
        # Calculate overall average confidence
        if all_confidences:
            report['overall_statistics']['avg_confidence'] = sum(all_confidences) / len(all_confidences)
        
        return save_json(report, output_path)
        
    except Exception as e:
        logging.error(f"Failed to create summary report: {e}")
        return False


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def validate_image_file(file_path: Path) -> Dict[str, Any]:
    """Validate an image file for OCR processing."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'info': {}
    }
    
    try:
        # Check if file exists
        if not file_path.exists():
            result['errors'].append(f"File does not exist: {file_path}")
            return result
        
        # Check file size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        result['info']['size_mb'] = size_mb
        
        if size_mb > 20:  # Google Vision API limit
            result['errors'].append(f"File size ({size_mb:.1f}MB) exceeds 20MB limit")
        elif size_mb > 10:
            result['warnings'].append(f"Large file size ({size_mb:.1f}MB) may take longer to process")
        
        # Check file extension
        from .config import Config
        if not Config.is_supported_format(file_path):
            result['errors'].append(f"Unsupported file format: {file_path.suffix}")
        
        # Try to open with PIL for additional validation
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                result['info']['dimensions'] = img.size
                result['info']['format'] = img.format
                result['info']['mode'] = img.mode
        except Exception as e:
            result['warnings'].append(f"Could not validate image with PIL: {e}")
        
        # If no errors, mark as valid
        if not result['errors']:
            result['valid'] = True
        
    except Exception as e:
        result['errors'].append(f"Validation error: {e}")
    
    return result
