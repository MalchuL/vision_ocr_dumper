# OCR Annotation Dumper

A powerful tool to extract and dump Google Cloud Vision OCR predictions from images and documents. This tool processes images using Google's state-of-the-art OCR technology and exports detailed annotations in JSON format.

## Features

- **Cost-Optimized OCR**: Uses only document_text_detection API to minimize costs
- **YOLO-like Structure**: Organizes output with `images/` and `labels/` folders
- **Advanced Visualization**: Draw bounding boxes and text on images with customizable settings
- **Environment Configuration**: Full support for `.env` files and environment variables
- **Batch Processing**: Process multiple images efficiently
- **Multi-Level Annotations**: Support for page, block, paragraph, word, and character level detection
- **Rich CLI Interface**: Beautiful command-line interface with progress tracking
- **Flexible Input**: Support for single files or directory processing
- **Configurable Drawing**: YAML-based settings for colors, thickness, and text rendering
- **Raw JSON Output**: Complete Google Vision API response data preserved

## Supported Formats

- **Images**: PNG, JPEG, GIF, BMP, WebP, RAW, ICO, TIFF
- **Documents**: PDF (first page)

## Installation

### Prerequisites

1. **Python 3.8+** (Python 3.13+ recommended)
2. **Google Cloud Project** with Vision API enabled
3. **Google Cloud Credentials** (Service Account Key or Application Default Credentials)

### Install with UV

```bash
# Clone or navigate to the project directory
cd ocr_annotation_dumper

# Install dependencies
uv sync

# Install in development mode
uv pip install -e .
```

### Install with pip

```bash
pip install -e .
```

## Setup Google Cloud Credentials

### Option 1: Using .env file (Recommended)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Cloud Vision API
4. Create a Service Account and download the JSON key file
5. Copy the example environment file and configure it:

```bash
cp .env.example .env
```

6. Edit `.env` file with your settings:

```bash
# OCR Annotation Dumper Environment Configuration
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
OCR_OUTPUT_DIR=./ocr_output
OCR_BATCH_SIZE=16
OCR_LOG_LEVEL=INFO
OCR_RECURSIVE_DEFAULT=false
```

### Option 2: Environment Variables

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
export OCR_OUTPUT_DIR="./my_output"
export OCR_LOG_LEVEL="DEBUG"
```

### Option 3: Application Default Credentials

```bash
# Install gcloud CLI and authenticate
gcloud auth application-default login
```

## Usage

### Basic Usage

```bash
# Process a single image
ocr-dump process image.jpg

# Process all images in a directory
ocr-dump process /path/to/images/

# Process with custom output directory (creates images/ and labels/ subdirs)
ocr-dump process images/ --output-dir ./results

# Process recursively in subdirectories
ocr-dump process images/ --recursive

# Visualize a single image (after processing)
ocr-dump draw image.jpg

# Visualize all images in a directory
ocr-dump draw ./ocr_output

# Create customizable settings file
ocr-dump init-settings
```

### Advanced Usage

```bash
# Processing with options
ocr-dump process images/ --credentials /path/to/creds.json

# Process with all options
ocr-dump process images/ \
    --output-dir ./ocr_results \
    --recursive \
    --credentials ./service-account.json

# Visualization with custom settings
ocr-dump draw images/ \
    --labels-dir ./ocr_output/labels \
    --output-dir ./visualizations \
    --settings custom_draw_settings.yaml

# Initialize and customize visualization settings
ocr-dump init-settings --output my_settings.yaml
# Edit my_settings.yaml to customize colors, thickness, etc.
ocr-dump draw images/ --settings my_settings.yaml
```

### Command Line Options

```
Usage: ocr-dump [OPTIONS] COMMAND [ARGS]...

  OCR Annotation Dumper - Extract and visualize Google Cloud Vision OCR predictions.

Commands:
  process        Process images and extract OCR annotations
  draw          Visualize OCR annotations by drawing bounding boxes
  init-settings Create a default draw_settings.yaml file

# Process command options:
ocr-dump process [OPTIONS] INPUT_PATH
  -o, --output-dir PATH      Output directory (creates images/ and labels/ subdirs)
  -c, --credentials PATH     Path to Google Cloud credentials JSON file  
  -r, --recursive            Process images recursively in subdirectories

# Draw command options:
ocr-dump draw [OPTIONS] INPUT_PATH
  -l, --labels-dir PATH      Directory containing JSON label files
  -o, --output-dir PATH      Output directory for visualizations
  -s, --settings PATH        Path to visualization settings YAML file

# Init-settings command options:
ocr-dump init-settings [OPTIONS]
  -o, --output PATH          Output path for the settings file
```

## Output Structure

The tool creates a YOLO-like directory structure:

```
ocr_output/
├── images/                # Copied original images
│   ├── image1.jpg
│   ├── image2.png
│   └── ...
└── labels/                # OCR annotations in JSON format
    ├── image1.json
    ├── image2.json
    └── ...
```

Each image is copied to the `images/` folder, and its corresponding OCR annotations are saved in the `labels/` folder with the same filename but `.json` extension.

### JSON Output Format

Each annotation file in `labels/` contains the complete Google Vision API response:

```json
{
  "file_name": "image.jpg",
  "response": {
    "fullTextAnnotation": {
      "text": "Complete extracted text from the document...",
      "pages": [
        {
          "width": 1920,
          "height": 1080,
          "confidence": 0.95,
          "blocks": [
            {
              "confidence": 0.98,
              "blockType": "TEXT",
              "boundingBox": {
                "vertices": [
                  {"x": 100, "y": 200},
                  {"x": 300, "y": 200},
                  {"x": 300, "y": 250},
                  {"x": 100, "y": 250}
                ]
              },
              "paragraphs": [
                {
                  "confidence": 0.97,
                  "boundingBox": { "vertices": [...] },
                  "words": [
                    {
                      "confidence": 0.99,
                      "boundingBox": { "vertices": [...] },
                      "symbols": [
                        {
                          "text": "H",
                          "confidence": 0.99,
                          "boundingBox": { "vertices": [...] }
                        }
                      ]
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    "textAnnotations": [...],
    "error": null
  }
}
```

The format includes:
- **file_name**: Original image filename
- **response**: Complete Google Vision API response in JSON format
- **fullTextAnnotation**: Hierarchical text structure with pages, blocks, paragraphs, words, and symbols
- **textAnnotations**: Alternative flat text annotation format
- **error**: Any API errors encountered

## Python API

You can also use the tool programmatically:

```python
from pathlib import Path
from ocr_annotation_dumper.main import OCRDumper

# Initialize the dumper
dumper = OCRDumper(credentials_path="/path/to/credentials.json")

# Process a single image
annotations = dumper.process_image(Path("image.jpg"))

# Process multiple images with YOLO-like structure
image_paths = [Path("img1.jpg"), Path("img2.jpg")]
dumper.dump_annotations(image_paths, output_dir=Path("./output"))

# This will create:
# ./output/images/img1.jpg, ./output/images/img2.jpg
# ./output/labels/img1.json, ./output/labels/img2.json
```

## Visualization

The tool includes powerful visualization capabilities to draw bounding boxes and text on images based on OCR results.

### Visualization Settings

Create and customize `draw_settings.yaml` to control visualization appearance:

```bash
# Create default settings file
ocr-dump init-settings

# Edit the file to customize
nano draw_settings.yaml
```

Example `draw_settings.yaml`:

```yaml
# Page level settings
page:
  draw: true
  color: [255, 0, 0]     # Red color in BGR format
  thickness: 3
  draw_text: true

# Block level settings  
block:
  draw: true
  color: [0, 255, 0]     # Green color
  thickness: 2
  draw_text: true

# Word level settings
word:
  draw: true
  color: [255, 255, 0]   # Cyan color
  thickness: 1
  draw_text: true

# Character level settings
character:
  draw: false            # Disable by default
  color: [255, 0, 255]   # Magenta color
  thickness: 1
  draw_text: false

# Global settings
global:
  output_dir: "./visualizations"
  confidence_threshold: 0.5
  show_confidence: true
```

### Visualization Examples

```bash
# Visualize a single image
ocr-dump draw image.jpg

# Visualize all images in a processed directory
ocr-dump draw ./ocr_output

# Custom visualization with settings
ocr-dump draw images/ \
    --labels-dir ./ocr_output/labels \
    --output-dir ./custom_viz \
    --settings my_draw_settings.yaml

# Visualize with specific labels directory
ocr-dump draw images/ --labels-dir labels/
```

## Configuration

The tool supports configuration through environment variables or a `.env` file. The `.env` file is automatically loaded when the tool starts.

### Environment Variables

- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google Cloud credentials JSON file
- `OCR_OUTPUT_DIR`: Default output directory (default: `./ocr_output`)
- `OCR_BATCH_SIZE`: Batch size for processing (default: `16`)
- `OCR_LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR (default: `INFO`)
- `OCR_RECURSIVE_DEFAULT`: Default recursive behavior - true/false (default: `false`)

### .env File Configuration

Create a `.env` file in your project directory:

```bash
# Copy the example file
cp .env.example .env

# Edit with your preferred editor
nano .env
```

Example `.env` configuration:

```bash
# Required for Google Cloud Vision API
GOOGLE_APPLICATION_CREDENTIALS=/home/user/gcp-key.json

# Optional configurations
OCR_OUTPUT_DIR=./my_ocr_results
OCR_BATCH_SIZE=8
OCR_LOG_LEVEL=DEBUG
OCR_RECURSIVE_DEFAULT=true
```

### Priority Order

Configuration values are used in this priority order:
1. Command line arguments (highest priority)
2. Environment variables  
3. `.env` file values
4. Default values (lowest priority)

### File Size Limits

- Maximum file size: 20MB (Google Vision API limit)
- Recommended: Keep files under 10MB for optimal performance

## Troubleshooting

### Common Issues

1. **Authentication Error**
   ```
   Error initializing Google Cloud Vision client
   ```
   - Ensure credentials are properly set
   - Check that Vision API is enabled in your project

2. **File Not Supported**
   ```
   Unsupported file format
   ```
   - Check the supported formats list
   - Ensure file extensions are correct

3. **API Quota Exceeded**
   - Monitor your Google Cloud Vision API usage
   - Consider implementing rate limiting for large batches

### Getting Help

- Check the logs in `ocr_output/logs/` for detailed error information
- Verify your Google Cloud setup and permissions
- Ensure your images are clear and readable

## Development

### Setting up Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd ocr_annotation_dumper

# Install in development mode with UV
uv sync --dev

# Run tests (if available)
uv run pytest

# Format code
uv run black .
uv run isort .
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google Cloud Vision API for powerful OCR capabilities
- Rich library for beautiful CLI interface
- Click for command-line interface framework
