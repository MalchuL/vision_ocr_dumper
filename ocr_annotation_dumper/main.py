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


@click.command()
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
def cli(input_path: Path, output_dir: Path, credentials: Optional[Path], recursive: bool):
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


if __name__ == "__main__":
    cli()
