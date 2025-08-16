"""
OCR Annotation Visualizer - Draw bounding boxes and text on images based on OCR results.
"""

import json
import yaml
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from rich.console import Console

from google.protobuf.json_format import MessageToDict
from google.cloud.vision import AnnotateImageResponse

console = Console()


class OCRVisualizer:
    """Visualize OCR annotations by drawing bounding boxes and text on images."""
    
    def __init__(self, settings_path: Optional[Path] = None):
        """Initialize visualizer with drawing settings."""
        self.settings_path = settings_path or Path("draw_settings.yaml")
        self.settings = self._load_settings()
        
    def _load_settings(self) -> Dict[str, Any]:
        """Load drawing settings from YAML file."""
        try:
            with open(self.settings_path, 'r') as f:
                settings = yaml.safe_load(f)
            console.print(f"[green]Loaded visualization settings from {self.settings_path}[/green]")
            return settings
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load settings from {self.settings_path}: {e}[/yellow]")
            console.print("[yellow]Using default settings[/yellow]")
            return self._get_default_settings()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default visualization settings."""
        return {
            'page': {'draw': True, 'color': [255, 0, 0], 'thickness': 3, 'draw_text': True},
            'block': {'draw': True, 'color': [0, 255, 0], 'thickness': 2, 'draw_text': True},
            'paragraph': {'draw': True, 'color': [0, 0, 255], 'thickness': 2, 'draw_text': False},
            'word': {'draw': True, 'color': [255, 255, 0], 'thickness': 1, 'draw_text': True},
            'character': {'draw': False, 'color': [255, 0, 255], 'thickness': 1, 'draw_text': False},
            'global': {
                'output_dir': './visualizations',
                'output_format': 'png',
                'font': 'FONT_HERSHEY_SIMPLEX',
                'show_confidence': True,
                'confidence_threshold': 0.5
            }
        }
    
    def _extract_vertices(self, bounding_box: Dict[str, Any]) -> List[Tuple[int, int]]:
        """Extract vertices from bounding box."""
        vertices = []
        if 'vertices' in bounding_box:
            for vertex in bounding_box['vertices']:
                x = int(vertex.get('x', 0))
                y = int(vertex.get('y', 0))
                vertices.append((x, y))
        return vertices
    
    def _draw_bounding_box(self, img: np.ndarray, vertices: List[Tuple[int, int]], 
                          color: List[int], thickness: int) -> np.ndarray:
        """Draw bounding box on image."""
        if len(vertices) >= 4:
            # Convert to numpy array for cv2
            pts = np.array(vertices, np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(img, [pts], True, color, thickness)
        return img
    
    def _draw_text(self, img: np.ndarray, text: str, position: Tuple[int, int],
                   settings: Dict[str, Any]) -> np.ndarray:
        """Draw text on image."""
        if not text or not settings.get('draw_text', False):
            return img
            
        font = getattr(cv2, settings.get('font', 'FONT_HERSHEY_SIMPLEX'), cv2.FONT_HERSHEY_SIMPLEX)
        font_scale = settings.get('text_size', 0.5)
        color = settings.get('text_color', settings.get('color', [255, 255, 255]))
        thickness = settings.get('text_thickness', 1)
        
        # Truncate long text
        if len(text) > 20:
            text = text[:17] + "..."
            
        # Get text size to position it properly
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        
        # Adjust position to be inside image bounds
        x, y = position
        if x < 0:
            x = 0
        if y < text_height:
            y = text_height + 5
        if x + text_width > img.shape[1]:
            x = img.shape[1] - text_width
        if y > img.shape[0]:
            y = img.shape[0] - 5
            
        # Draw background if enabled
        if self.settings.get('global', {}).get('text_background', True):
            bg_color = self.settings.get('global', {}).get('text_background_color', [255, 255, 255])
            cv2.rectangle(img, (x-2, y-text_height-2), (x+text_width+2, y+baseline+2), bg_color, -1)
        
        # Draw text
        cv2.putText(img, text, (x, y), font, font_scale, color, thickness)
        
        return img
    
    def _process_page_level(self, img: np.ndarray, page_data: Dict[str, Any]) -> np.ndarray:
        """Draw page-level annotations."""
        settings = self.settings.get('page', {})
        if not settings.get('draw', False):
            return img
            
        # Draw page boundary (full image)
        h, w = img.shape[:2]
        vertices = [(0, 0), (w, 0), (w, h), (0, h)]
        
        color = settings.get('color', [255, 0, 0])
        thickness = settings.get('thickness', 3)
        
        img = self._draw_bounding_box(img, vertices, color, thickness)
        
        if settings.get('draw_text', False):
            confidence = page_data.get('confidence', 0)
            text = f"Page (conf: {confidence:.2f})"
            img = self._draw_text(img, text, (10, 30), settings)
            
        return img
    
    def _process_block_level(self, img: np.ndarray, blocks: List[Dict[str, Any]]) -> np.ndarray:
        """Draw block-level annotations."""
        settings = self.settings.get('block', {})
        if not settings.get('draw', False):
            return img
            
        for block in blocks:
            if 'boundingBox' in block:
                vertices = self._extract_vertices(block['boundingBox'])
                if vertices:
                    color = settings.get('color', [0, 255, 0])
                    thickness = settings.get('thickness', 2)
                    img = self._draw_bounding_box(img, vertices, color, thickness)
                    
                    if settings.get('draw_text', False):
                        confidence = block.get('confidence', 0)
                        block_type = block.get('blockType', 'UNKNOWN')
                        text = f"{block_type} (conf: {confidence:.2f})"
                        img = self._draw_text(img, text, vertices[0], settings)
                        
        return img
    
    def _process_paragraph_level(self, img: np.ndarray, blocks: List[Dict[str, Any]]) -> np.ndarray:
        """Draw paragraph-level annotations."""
        settings = self.settings.get('paragraph', {})
        if not settings.get('draw', False):
            return img
            
        for block in blocks:
            paragraphs = block.get('paragraphs', [])
            for paragraph in paragraphs:
                if 'boundingBox' in paragraph:
                    vertices = self._extract_vertices(paragraph['boundingBox'])
                    if vertices:
                        color = settings.get('color', [0, 0, 255])
                        thickness = settings.get('thickness', 2)
                        img = self._draw_bounding_box(img, vertices, color, thickness)
                        
                        if settings.get('draw_text', False):
                            confidence = paragraph.get('confidence', 0)
                            text = f"Para (conf: {confidence:.2f})"
                            img = self._draw_text(img, text, vertices[0], settings)
                            
        return img
    
    def _process_word_level(self, img: np.ndarray, blocks: List[Dict[str, Any]]) -> np.ndarray:
        """Draw word-level annotations."""
        settings = self.settings.get('word', {})
        if not settings.get('draw', False):
            return img
            
        confidence_threshold = self.settings.get('global', {}).get('confidence_threshold', 0.5)
        
        for block in blocks:
            paragraphs = block.get('paragraphs', [])
            for paragraph in paragraphs:
                words = paragraph.get('words', [])
                for word in words:
                    if 'boundingBox' in word:
                        confidence = word.get('confidence', 0)
                        if confidence < confidence_threshold:
                            continue
                            
                        vertices = self._extract_vertices(word['boundingBox'])
                        if vertices:
                            color = settings.get('color', [255, 255, 0])
                            thickness = settings.get('thickness', 1)
                            img = self._draw_bounding_box(img, vertices, color, thickness)
                            
                            if settings.get('draw_text', False):
                                # Extract word text from symbols
                                word_text = self._extract_word_text(word)
                                if word_text:
                                    img = self._draw_text(img, word_text, vertices[0], settings)
                                    
        return img
    
    def _process_character_level(self, img: np.ndarray, blocks: List[Dict[str, Any]]) -> np.ndarray:
        """Draw character-level annotations."""
        settings = self.settings.get('character', {})
        if not settings.get('draw', False):
            return img
            
        confidence_threshold = self.settings.get('global', {}).get('confidence_threshold', 0.5)
        
        for block in blocks:
            paragraphs = block.get('paragraphs', [])
            for paragraph in paragraphs:
                words = paragraph.get('words', [])
                for word in words:
                    symbols = word.get('symbols', [])
                    for symbol in symbols:
                        if 'boundingBox' in symbol:
                            confidence = symbol.get('confidence', 0)
                            if confidence < confidence_threshold:
                                continue
                                
                            vertices = self._extract_vertices(symbol['boundingBox'])
                            if vertices:
                                color = settings.get('color', [255, 0, 255])
                                thickness = settings.get('thickness', 1)
                                img = self._draw_bounding_box(img, vertices, color, thickness)
                                
                                if settings.get('draw_text', False):
                                    char_text = symbol.get('text', '')
                                    if char_text:
                                        img = self._draw_text(img, char_text, vertices[0], settings)
                                        
        return img
    
    def _extract_word_text(self, word: Dict[str, Any]) -> str:
        """Extract text from word symbols."""
        symbols = word.get('symbols', [])
        return ''.join([symbol.get('text', '') for symbol in symbols])
    
    def visualize_annotations(self, image_path: Path, annotations_path: Path, 
                            output_path: Optional[Path] = None) -> Path:
        """Visualize OCR annotations on an image."""
        try:
            # Load image
            img = cv2.imread(str(image_path))
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")
                
            # Load annotations
            with open(annotations_path, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
                
            # Extract OCR response data
            response_data = annotations.get('response', {})
            full_text_annotation = response_data.get('fullTextAnnotation', {})
            
            if not full_text_annotation:
                console.print(f"[yellow]No fullTextAnnotation found in {annotations_path}[/yellow]")
                return image_path
                
            pages = full_text_annotation.get('pages', [])
            
            if not pages:
                console.print(f"[yellow]No pages found in annotations: {annotations_path}[/yellow]")
                return image_path
                
            # Process each page
            for page in pages:
                # Draw different levels based on settings
                img = self._process_page_level(img, page)
                
                blocks = page.get('blocks', [])
                img = self._process_block_level(img, blocks)
                img = self._process_paragraph_level(img, blocks)
                img = self._process_word_level(img, blocks)
                img = self._process_character_level(img, blocks)
            
            # Determine output path
            if output_path is None:
                output_dir = Path(self.settings.get('global', {}).get('output_dir', './visualizations'))
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_format = self.settings.get('global', {}).get('output_format', 'png')
                output_path = output_dir / f"{image_path.stem}_visualized.{output_format}"
            
            # Save visualized image
            cv2.imwrite(str(output_path), img)
            console.print(f"[green]Saved visualization to {output_path}[/green]")
            
            return output_path
            
        except Exception as e:
            console.print(f"[red]Error visualizing {image_path}: {e}[/red]")
            return image_path
    
    def visualize_folder(self, images_dir: Path, labels_dir: Path, 
                        output_dir: Optional[Path] = None) -> List[Path]:
        """Visualize all images in a folder with their corresponding labels."""
        if output_dir is None:
            output_dir = Path(self.settings.get('global', {}).get('output_dir', './visualizations'))
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        visualized_paths = []
        
        # Find all images in the images directory
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
        image_files: List[Path] = []
        
        for ext in image_extensions:
            image_files.extend(images_dir.glob(f"*{ext}"))
            image_files.extend(images_dir.glob(f"*{ext.upper()}"))
        
        if not image_files:
            console.print(f"[yellow]No image files found in {images_dir}[/yellow]")
            return []
            
        console.print(f"[blue]Found {len(image_files)} images to visualize[/blue]")
        
        for image_path in image_files:
            # Find corresponding label file
            label_path = labels_dir / f"{image_path.stem}.json"
            
            if not label_path.exists():
                console.print(f"[yellow]No label file found for {image_path.name}[/yellow]")
                continue
                
            # Create output path
            output_format = self.settings.get('global', {}).get('output_format', 'png')
            output_path = output_dir / f"{image_path.stem}_visualized.{output_format}"
            
            # Visualize
            result_path = self.visualize_annotations(image_path, label_path, output_path)
            visualized_paths.append(result_path)
            
        console.print(f"[green]Visualized {len(visualized_paths)} images[/green]")
        return visualized_paths
