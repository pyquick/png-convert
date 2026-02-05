# PNG to ICNS Converter & ZIP File Processing Tools

This repository contains tools for converting PNG images to ICNS format and processing ZIP files.

## Requirements

- Python 3.11, 3.12, or 3.13 (recommended) 
- PIL (Pillow) library
- Tkinter (usually included with Python)
- Nuitka (for building standalone applications)

You can install the required dependencies using:
```
pip install -r requirements.txt
```

### requirements.txt
```
Pillow>=8.0.0
Nuitka>=1.0.0
PySide6
rarfile
py7zr
```

**Note for RAR support:** The `rarfile` Python library requires the external `unrar` program to be installed on your system. Please install it using your system's package manager or download it from [RarLab](https://www.rarlab.com/rar_add.htm).

- **macOS (using Homebrew)**:
  ```bash
  brew install unrar
  ```
- **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt-get install unrar
  ```
- **Windows**: Download and install the UnRAR DLL from [RarLab](https://www.rarlab.com/rar_add.htm) and ensure its path is added to your system's PATH environment variable.

Note: Tkinter is usually included with Python installations. For ZIP file GUI functionality, no additional dependencies are required beyond the standard library.

## PNG to ICNS Converter

### Usage

#### Command Line Version

Basic usage:
```
python3 support/convert.py input.png output.icns
```

Advanced usage with size options:
```
python3 support/convert.py input.png output.icns --min-size 16 --max-size 512
```

#### GUI Version

For a graphical interface, run:
```
python3 Converter.py
```

## Building a Standalone Application

To compile the application into a macOS .app bundle, run:
```
./build.command
```

This will create a standalone application in the `dist` folder using Nuitka with Python 3.13.

**Note:** The build script is specifically designed to work with Python 3.13 to avoid compatibility issues.

### Requirements for Building

- Python 3.13
- Nuitka
- Pillow

Install build requirements:
```
python3.14 -m pip install Pillow nuitka
```

The build script will automatically:
1. Download ccache to avoid SSL certificate issues
2. Use Python 3.13 for compilation
3. Create a standalone .app bundle

## ZIP File Processing Tools

This repository also includes tools for creating, extracting, and managing ZIP files.

### Command Line Version

The command line tool supports several operations:

#### Create a ZIP file
```
python3 convertzip.py create output.zip file1.txt folder1/ file2.txt
```

#### Extract a ZIP file
```
python3 convertzip.py extract archive.zip /path/to/extract/
```

#### Add a file to existing ZIP
```
python3 convertzip.py add archive.zip newfile.txt
```

#### List ZIP file contents
```
python3 convertzip.py list archive.zip
```

### GUI Version

For a graphical interface for ZIP file operations, run:
```
python3 arc_gui.py
```

The GUI provides tabs for:
- Creating ZIP files from selected files and folders
- Extracting ZIP files to a destination folder
- Adding files to existing ZIP files
- Listing the contents of ZIP files

## Alternative: Simple Converter Script

If you cannot build the application with Nuitka, you can use the provided Converter script:
```
./PNG_to_ICNS_Converter.command
```

This script will run the application directly with Python without requiring compilation.

## Options

- `--min-size`: Minimum icon size (default: 16)
- `--max-size`: Maximum icon size (default: auto-detected from image)

## Features

### PNG to ICNS Converter
- Automatically generates multiple icon sizes from the original image
- Supports retina (2x) versions for common sizes
- Crops non-square images to square format
- Automatically detects image size and uses it as maximum icon size
- GUI interface for easier use with image preview
- Progress indication during conversion
- Automatic opening of the result in Preview app

### ZIP File Processing Tools
- Create ZIP files from files and folders with progress tracking
- Extract ZIP files with progress tracking
- Add files to existing ZIP files
- List contents of ZIP files
- Both command-line and GUI interfaces
- Error handling and user-friendly feedback
- Enhanced security with path traversal protection

## Example

To convert a 256x256 PNG image to ICNS with default settings:
```
python3 support/convert.py icon.png icon.icns
```

This will generate icons in sizes: 16x16, 32x32, 64x64, 128x128, and 256x256, including retina versions where appropriate.

To use the GUI version:
```
python3 Converter.py
```

The GUI provides a user-friendly interface with:
- File browsing for input and output files
- Preview of the source image
- Image information display (dimensions)
- Customizable minimum and maximum icon sizes
- Auto-detect maximum size button
- Progress indication during conversion
- Status bar showing current operation

When using the GUI, the maximum icon size is automatically set to match the smaller dimension of the source image when you select an input file.

To build a standalone macOS application, run:
```
./build.command
```

This will create a .app bundle in the dist folder that can be run without requiring Python to be installed.

If you encounter issues with the build process, you can use the simple Converter script instead:
```
./PNG_to_ICNS_Converter.command
```

Or run directly with Python 3.13:
```
python3.14 Converter.py
```

For ZIP file operations, you can use either the command line:
```
python3 convertzip.py [command] [options]
```

Or the GUI:
```
python3 arc_gui.py
```