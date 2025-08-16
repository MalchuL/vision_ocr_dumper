#!/usr/bin/env python3
"""
OCR Annotation Dumper - Main CLI interface for dumping Google Cloud Vision OCR predictions.
"""

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from google.protobuf.json_format import MessageToJson

import click
from dotenv import load_dotenv
from google.cloud import vision
from rich.console import Console
from rich.progress import track
from rich.table import Table
from PIL import Image

# Load environment variables from .env file
load_dotenv()

from .config import Config
from .visualizer import OCRVisualizer

console = Console()


class OCRDumper:
    """Main class for handling OCR operations using Google Cloud Vision API."""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize the OCR dumper with optional credentials path."""
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        try:
            self.client = vision.ImageAnnotatorClient()
        except Exception as e:
            console.print(f"[red]Error initializing Google Cloud Vision client: {e}[/red]")
            console.print("[yellow]Make sure you have set up Google Cloud credentials.[/yellow]")
            raise
    
    def process_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Process a single image and extract OCR annotations using only document_text_detection."""
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Use only document text detection to save costs
            document_response = self.client.document_text_detection(image=image)
            document = document_response.full_text_annotation
            
            # Check for errors
            if document_response.error.message:
                raise Exception(f"Google Vision API error: {document_response.error.message}")
            
            # Process annotations - simplified structure
            annotations: Dict[str, Any] = {
                'file_name': image_path.name,
                'response': json.loads(MessageToJson(document_response._pb))
            }
            
            
            return annotations
            
        except Exception as e:
            console.print(f"[red]Error processing {image_path}: {e}[/red]")
            return None
    
    def dump_annotations(self, image_paths: List[Path], output_dir: Path):
        """Dump OCR annotations for images in YOLO-like structure with images and labels folders."""
        # Create YOLO-like directory structure
        images_dir = output_dir / "images"
        labels_dir = output_dir / "labels"
        
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        all_annotations = []
        processed_count = 0
        
        for image_path in track(image_paths, description="Processing images..."):
            annotations = self.process_image(image_path)
            if annotations:
                # Copy image to images folder
                target_image_path = images_dir / image_path.name
                try:
                    shutil.copy2(image_path, target_image_path)
                    console.print(f"[blue]Copied image to {target_image_path}[/blue]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not copy {image_path}: {e}[/yellow]")
                    continue
                
                # Save label JSON file with same name but .json extension
                label_file = labels_dir / f"{image_path.stem}.json"
                try:
                    with open(label_file, 'w', encoding='utf-8') as f:
                        json.dump(annotations, f, indent=2, ensure_ascii=False)
                    
                    console.print(f"[green]Saved label to {label_file}[/green]")
                    all_annotations.append(annotations)
                    processed_count += 1
                    
                except Exception as e:
                    console.print(f"[red]Error saving label for {image_path}: {e}[/red]")
        
        # Display summary
        self._display_summary(all_annotations, processed_count)
    
    def _display_summary(self, annotations_list: List[Dict[str, Any]], processed_count: int):
        """Display a summary table of processed annotations."""
        if not annotations_list:
            console.print("[yellow]No annotations processed.[/yellow]")
            return
        
        console.print(f"\n[bold green]Successfully processed {processed_count} images[/bold green]")
        
        table = Table(title="OCR Processing Summary")
        table.add_column("File", style="cyan")
        table.add_column("Text Length", justify="right")
        table.add_column("Pages", justify="right")
        table.add_column("Avg Confidence", justify="right")
        
        for annotations in annotations_list:
            text_length = len(annotations.get('document_text', ''))
            pages_count = len(annotations.get('pages', []))
            
            # Calculate average confidence from pages
            confidences = []
            for page in annotations.get('pages', []):
                if 'confidence' in page:
                    confidences.append(page['confidence'])
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            table.add_row(
                annotations['file_name'],
                str(text_length),
                str(pages_count),
                f"{avg_confidence:.2f}"
            )
        
        console.print(table)


@click.group()
def cli():
    """OCR Annotation Dumper - Extract and visualize Google Cloud Vision OCR predictions."""
    pass

@cli.command()
@click.argument('input_path', type=click.Path(exists=True, path_type=Path))
@click.option('--output-dir', '-o', type=click.Path(path_type=Path), 
              default=lambda: Config.get_output_dir(), 
              help='Output directory (will create images/ and labels/ subdirs)')
@click.option('--credentials', '-c', type=click.Path(exists=True), 
              default=lambda: Config.get_credentials_path(),
              help='Path to Google Cloud credentials JSON file')
@click.option('--recursive', '-r', is_flag=True,
              default=lambda: Config.is_recursive_default(),
              help='Process images recursively in subdirectories (only for folders)')
def process(input_path: Path, output_dir: Path, credentials: Optional[Path], recursive: bool):
    """
    Dump Google Cloud Vision OCR predictions from images in YOLO-like structure.
    
    Creates OUTPUT_DIR with 'images/' and 'labels/' folders.
    For each image, copies it to images/ and saves OCR JSON to labels/ with same name.
    
    INPUT_PATH can be a single image file or a directory containing images.
    Supported formats: PNG, JPEG, GIF, BMP, WebP, RAW, ICO, PDF, TIFF
    
    Uses only document_text_detection API to minimize costs.
    """
    console.print("[bold blue]OCR Annotation Dumper[/bold blue]")
    console.print(f"Processing: {input_path}")
    console.print(f"Output directory: {output_dir}")
    
    # Initialize OCR dumper
    try:
        dumper = OCRDumper(credentials_path=str(credentials) if credentials else None)
    except Exception:
        return
    
    # Find image files
    supported_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', 
                          '.raw', '.ico', '.pdf', '.tiff', '.tif'}
    
    image_paths = []
    
    if input_path.is_file():
        if input_path.suffix.lower() in supported_extensions:
            image_paths.append(input_path)
        else:
            console.print(f"[red]Unsupported file format: {input_path.suffix}[/red]")
            return
    elif input_path.is_dir():
        if recursive:
            pattern = "**/*"
            console.print("[blue]Searching recursively for images...[/blue]")
        else:
            pattern = "*"
            console.print("[blue]Searching for images in current directory only...[/blue]")
            
        for ext in supported_extensions:
            image_paths.extend(input_path.glob(f"{pattern}{ext}"))
            image_paths.extend(input_path.glob(f"{pattern}{ext.upper()}"))
    
    if not image_paths:
        console.print("[red]No supported image files found.[/red]")
        return
    
    console.print(f"Found {len(image_paths)} image(s) to process")
    console.print(f"[yellow]Using document_text_detection API (cost-optimized)[/yellow]")
    
    # Process images
    dumper.dump_annotations(image_paths, output_dir)
    
    console.print(f"\n[bold green]Processing complete![/bold green]")
    console.print(f"[blue]Images copied to: {output_dir}/images/[/blue]")
    console.print(f"[blue]Labels saved to: {output_dir}/labels/[/blue]")


@cli.command()
@click.argument('input_path', type=click.Path(exists=True, path_type=Path))
@click.option('--labels-dir', '-l', type=click.Path(exists=True, path_type=Path),
              help='Directory containing JSON label files (default: auto-detect)')
@click.option('--output-dir', '-o', type=click.Path(path_type=Path),
              help='Output directory for visualizations (default: ./visualizations)')
@click.option('--settings', '-s', type=click.Path(exists=True, path_type=Path),
              default=Path('draw_settings.yaml'),
              help='Path to visualization settings YAML file')
def draw(input_path: Path, labels_dir: Optional[Path], output_dir: Optional[Path], 
         settings: Path):
    """
    Visualize OCR annotations by drawing bounding boxes on images.
    
    INPUT_PATH can be a single image file or a directory containing images.
    For directories, it will look for corresponding JSON files in labels_dir.
    """
    console.print("[bold blue]OCR Annotation Visualizer[/bold blue]")
    console.print(f"Input: {input_path}")
    console.print(f"Settings: {settings}")
    
    # Initialize visualizer
    try:
        visualizer = OCRVisualizer(settings)
    except Exception as e:
        console.print(f"[red]Error initializing visualizer: {e}[/red]")
        return
    
    if input_path.is_file():
        # Single image visualization
        if labels_dir is None:
            # Try to find label file in same directory
            label_path = input_path.parent.parent/ "labels" / f"{input_path.stem}.json"
        else:
            label_path = labels_dir / f"{input_path.stem}.json"
            
        if not label_path.exists():
            console.print(f"[red]Label file not found: {label_path}[/red]")
            console.print("[yellow]Make sure to run 'ocr-dump process' first to generate labels[/yellow]")
            return
            
        console.print(f"Label file: {label_path}")
        result_path = visualizer.visualize_annotations(input_path, label_path, output_dir)
        
        if result_path != input_path:
            console.print(f"[green]Visualization saved to: {result_path}[/green]")
        
    elif input_path.is_dir():
        # Directory visualization
        if labels_dir is None:
            # Auto-detect: look for 'labels' subdirectory or use input directory
            potential_labels_dir = input_path / 'labels'
            if potential_labels_dir.exists():
                labels_dir = potential_labels_dir
                images_dir = input_path / 'images'
                if not images_dir.exists():
                    images_dir = input_path
            else:
                labels_dir = input_path
                images_dir = input_path
        else:
            images_dir = input_path
            
        console.print(f"Images directory: {images_dir}")
        console.print(f"Labels directory: {labels_dir}")
        
        if not labels_dir.exists():
            console.print(f"[red]Labels directory not found: {labels_dir}[/red]")
            return
            
        result_paths = visualizer.visualize_folder(images_dir, labels_dir, output_dir)
        
        if result_paths:
            console.print(f"[green]Generated {len(result_paths)} visualizations[/green]")
        else:
            console.print("[yellow]No visualizations were generated[/yellow]")
    
    console.print("[bold green]Visualization complete![/bold green]")


@cli.command()
@click.option('--output', '-o', type=click.Path(path_type=Path),
              default=Path('draw_settings.yaml'),
              help='Output path for the settings file')
def init_settings(output: Path):
    """Create a default draw_settings.yaml file for customization."""
    if output.exists():
        if not click.confirm(f"File {output} already exists. Overwrite?"):
            console.print("[yellow]Operation cancelled[/yellow]")
            return
    
    # Copy the default settings
    import shutil
    default_settings = Path(__file__).parent.parent / 'draw_settings.yaml'
    
    try:
        if default_settings.exists():
            shutil.copy2(default_settings, output)
        else:
            # Create default settings if template doesn't exist
            default_content = """# OCR Annotation Visualization Settings
page:
  draw: true
  color: [255, 0, 0]
  thickness: 3
  draw_text: true

block:
  draw: true
  color: [0, 255, 0]
  thickness: 2
  draw_text: true

paragraph:
  draw: true
  color: [0, 0, 255]
  thickness: 2
  draw_text: false

word:
  draw: true
  color: [255, 255, 0]
  thickness: 1
  draw_text: true

character:
  draw: false
  color: [255, 0, 255]
  thickness: 1
  draw_text: false

global:
  output_dir: "./visualizations"
  output_format: "png"
  show_confidence: true
  confidence_threshold: 0.5
"""
            with open(output, 'w') as f:
                f.write(default_content)
        
        console.print(f"[green]Created settings file: {output}[/green]")
        console.print("[blue]Edit this file to customize visualization settings[/blue]")
        
    except Exception as e:
        console.print(f"[red]Error creating settings file: {e}[/red]")


if __name__ == "__main__":
    cli()
