#!/usr/bin/env python3

"""
PNG to ICNS Converter

This script converts PNG images to ICNS format, which is used for macOS icons.
It requires PIL (Pillow) library and supports customizable size ranges.

Usage:
    python3 convert.py input.png output.icns [--min-size SIZE] [--max-size SIZE]
"""

import sys
import os
import argparse
import tempfile
import subprocess
from PIL import Image

SUPPORTED_FORMATS = ["icns", "png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "jpeg", "svg", "heic", "heif", "avif", "jxl", "pdf", "eps", "dds", "exr"]

def get_image_info(image_path):
    """
    Get information about the image.
    
    Args:
        image_path (str): Path to the input image file
        
    Returns:
        tuple: (width, height) of the image
    """
    img = Image.open(image_path)
    return img.width, img.height

def convert_image(input_path, output_path, output_format, min_size=16, max_size=None, quality=85, progress_callback=None, interface_settings=None):
    """
    Convert an image to the specified format.
    
    Args:
        input_path (str): Path to the input image file.
        output_path (str): Path for the output file.
        output_format (str): Desired output format (e.g., "icns", "png", "jpg", "webp").
        min_size (int): Minimum size for the icon (default: 16), primarily for ICNS.
        max_size (int): Maximum size for the icon (default: original image size), primarily for ICNS.
        quality (int): Image quality for lossy formats like JPG (default: 85, range: 1-100).
        progress_callback (function): Callback function to report progress.
        interface_settings (dict): Interface behavior settings for controlling conversion behavior.
    """
    if output_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format}. Supported formats are: {', '.join(SUPPORTED_FORMATS)}")

    if output_format == "icns":
        # Existing ICNS conversion logic
        _create_icns_internal(input_path, output_path, min_size, max_size, progress_callback)
    else:
        # Generic image conversion using Pillow
        try:
            img = Image.open(input_path)
            
            # For JPG, ensure the image is in RGB mode as JPG does not support alpha channel
            if output_format.lower() == "jpg":
                if progress_callback:
                    progress_callback(f"Processing image for JPG conversion...", 30)
                
                # Handle various image modes that need conversion to RGB
                if img.mode in ('RGBA', 'LA', 'P', 'CMYK', 'YCbCr', 'LAB', 'HSV', 'I', 'F'):
                    if progress_callback:
                        progress_callback(f"Converting from {img.mode} mode to RGB...", 40)
                    
                    # For modes with transparency, use white background
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Create white background
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                    else:
                        # For other modes, convert directly to RGB
                        img = img.convert('RGB')
                
                if progress_callback:
                    progress_callback(f"Image converted to RGB mode", 50)
            
            # Save with appropriate options for each format
            save_options = {}
            
            if output_format.lower() == "jpg":
                # Save JPG with specified quality and optimized settings
                img.save(output_path, format='JPEG', quality=quality, optimize=True, progressive=True)
            elif output_format.lower() == "webp":
                # Save WebP with quality settings
                save_options = {'quality': quality, 'method': 6}
                img.save(output_path, format='WEBP', **save_options)
            elif output_format.lower() == "tiff":
                # Save TIFF with compression
                save_options = {'compression': 'tiff_lzw'}
                img.save(output_path, format='TIFF', **save_options)
            elif output_format.lower() in ["svg", "pdf", "eps"]:
                # Vector formats require special handling
                # For now, convert raster image to these formats with basic settings
                if progress_callback:
                    progress_callback(f"Converting to vector format {output_format.upper()}...", 70)
                img.save(output_path, format=output_format.upper())
            elif output_format.lower() in ["heic", "heif"]:
                # HEIC/HEIF format support
                if progress_callback:
                    progress_callback(70, 100, f"Converting to {output_format.upper()} format...")
                # Try to save as HEIF if available, otherwise fallback
                try:
                    img.save(output_path, format='HEIF', quality=quality)
                except Exception:
                    # Fallback to PNG if HEIF not supported
                    if progress_callback:
                        progress_callback(f"HEIF format not available, falling back to PNG", 80)
                    img.save(output_path, format='PNG')
            elif output_format.lower() in ["avif", "jxl"]:
                # Modern formats that may require additional libraries
                if progress_callback:
                    progress_callback(f"Converting to {output_format.upper()} format...", 70)
                try:
                    img.save(output_path, format=output_format.upper(), quality=quality)
                except Exception as format_error:
                    # Fallback to WebP if modern format not supported
                    if progress_callback:
                        progress_callback(f"{output_format.upper()} format not available, falling back to WebP", 80)
                    img.save(output_path, format='WEBP', quality=quality)
            elif output_format.lower() in ["dds", "exr"]:
                # Specialized formats for gaming and HDR
                if progress_callback:
                    progress_callback(f"Converting to {output_format.upper()} format...", 70)
                img.save(output_path, format=output_format.upper())
            else:
                # Default handling for other formats
                img.save(output_path, format=output_format.upper())
                
            if progress_callback:
                progress_callback(100, 100, f"Successfully converted {input_path} to {output_path} ({output_format})")
            else:
                print(f"Successfully converted {input_path} to {output_path} ({output_format})")
        except Exception as e:
            error_msg = f"Error converting image to {output_format.upper()}: {e}"
            if progress_callback:
                progress_callback(error_msg, 0)
            raise Exception(error_msg) from e

def _create_icns_internal(png_path, icns_path, min_size=16, max_size=None, progress_callback=None):
    """
    Internal function to convert a PNG image to ICNS format using iconset method.
    This function contains the original logic of create_icns.
    """
    # Open the source image
    img = Image.open(png_path)
    
    # Automatically detect image size if not provided
    if max_size is None:
        max_size = min(img.width, img.height)
        if progress_callback:
            progress_callback(5, 100, f"Auto-detected maximum size: {max_size}")
        else:
            print(f"Auto-detected maximum size: {max_size}")
    
    if progress_callback:
        progress_callback(10, 100, f"Source image size: {img.width}x{img.height}")
    else:
        print(f"Source image size: {img.width}x{img.height}")
    
    # Ensure the image is square
    if img.width != img.height:
        if progress_callback:
            progress_callback(15, 100, "Warning: Image is not square. Cropping to square.")
        else:
            print("Warning: Image is not square. Cropping to square.")
        min_dimension = min(img.width, img.height)
        left = (img.width - min_dimension) // 2
        top = (img.height - min_dimension) // 2
        right = left + min_dimension
        bottom = top + min_dimension
        img = img.crop((left, top, right, bottom))
    
    # Create a temporary directory for iconset
    with tempfile.TemporaryDirectory() as tmp_dir:
        iconset_dir = os.path.join(tmp_dir, "iconset.iconset")
        os.makedirs(iconset_dir)
        
        # Define standard sizes for ICNS (based on Apple's specifications)
        standard_sizes = [16, 32, 64, 128, 256, 512, 1024]
        
        # Generate icons for standard sizes within our range
        generated_sizes = []
        total_steps = len(standard_sizes) * 2  # Approximate steps
        current_step = 0
        
        for size in standard_sizes:
            if min_size <= size <= max_size:
                current_step += 1
                if progress_callback:
                    progress_callback(20 + int(60 * current_step / total_steps), 100, f"Generating size: {size}x{size}")
                else:
                    print(f"Generated size: {size}x{size}")
                
                # Create a copy of the image and resize it
                resized_img = img.copy().resize((size, size), Image.Resampling.LANCZOS)
                
                # Save as PNG in iconset directory
                filename = f"icon_{size}x{size}.png"
                resized_img.save(os.path.join(iconset_dir, filename), "PNG")
                generated_sizes.append(size)
                
                # For specific sizes, also generate retina versions
                retina_pairs = {16: 32, 32: 64, 128: 256, 256: 512, 512: 1024}
                if size in retina_pairs and retina_pairs[size] <= max_size:
                    current_step += 1
                    retina_size = retina_pairs[size]
                    if progress_callback:
                        progress_callback(20 + int(60 * current_step / total_steps), 100, f"Generating retina size: {retina_size}x{retina_size}")
                    else:
                        print(f"Generated retina size: {retina_size}x{retina_size}")
                    
                    retina_img = img.copy().resize((retina_size, retina_size), Image.Resampling.LANCZOS)
                    retina_filename = f"icon_{size}x{size}@2x.png"
                    retina_img.save(os.path.join(iconset_dir, retina_filename), "PNG")
                    generated_sizes.append(retina_size)
        
        # Make sure we include max_size if it's not already included
        if max_size not in generated_sizes:
            if progress_callback:
                progress_callback(85, 100, f"Generating max size: {max_size}x{max_size}")
            else:
                print(f"Generated max size: {max_size}x{max_size}")
            
            resized_img = img.copy().resize((max_size, max_size), Image.Resampling.LANCZOS)
            filename = f"icon_{max_size}x{max_size}.png"
            resized_img.save(os.path.join(iconset_dir, filename), "PNG")
            generated_sizes.append(max_size)
        
        # Use iconutil to create ICNS file (macOS only)
        if progress_callback:
            progress_callback(90, 100, "Creating ICNS file with iconutil...")
        else:
            print("Creating ICNS file with iconutil...")
            
        try:
            subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", icns_path], check=True)
            if progress_callback:
                progress_callback(100, 100, f"Successfully converted {png_path} to {icns_path}")
            else:
                print(f"Successfully converted {png_path} to {icns_path}")
                print(f"Generated sizes: {sorted(set(generated_sizes))}")
        except subprocess.CalledProcessError as e:
            error_detail = e.stderr.decode() if e.stderr else str(e)
            error_msg = f"Error creating ICNS with iconutil: {error_detail}"
            if progress_callback:
                progress_callback(90, 100, error_msg)
                progress_callback(90, 100, "Falling back to Pillow method...")
            else:
                print(error_msg)
                print("Falling back to Pillow method...")
            # Fallback to Pillow method if iconutil fails
            _fallback_method_internal(iconset_dir, icns_path, progress_callback)
        except Exception as e:
            error_msg = f"Unexpected error during iconutil conversion: {e}"
            if progress_callback:
                progress_callback(90, 100, error_msg)
                progress_callback(90, 100, "Falling back to Pillow method...")
            else:
                print(error_msg)
                print("Falling back to Pillow method...")
            _fallback_method_internal(iconset_dir, icns_path, progress_callback)

def _fallback_method_internal(iconset_dir, icns_path, progress_callback=None):
    """
    Internal fallback method using Pillow if iconutil is not available
    """
    icon_files = os.listdir(iconset_dir)
    if not icon_files:
        error_msg = "No icons generated, cannot create ICNS file"
        if progress_callback:
            progress_callback(100, 100, error_msg)
        else:
            print(error_msg)
        return
        
    # Find the largest icon file to use as main image
    icon_paths = [os.path.join(iconset_dir, f) for f in icon_files]
    largest_icon = max(icon_paths, key=lambda p: Image.open(p).size[0])
    
    # Open the largest icon as main image
    main_img = Image.open(largest_icon)
    
    # Create list of additional images
    append_images = []
    for icon_path in icon_paths:
        if icon_path != largest_icon:
            append_images.append(Image.open(icon_path))
    
    # Save as ICNS
    if append_images:
        main_img.save(
            icns_path,
            format='ICNS',
            append_images=append_images
        )
    else:
        main_img.save(icns_path, format='ICNS')
    
    success_msg = f"Successfully converted using fallback method to {icns_path}"
    if progress_callback:
        progress_callback(100, 100, success_msg)
    else:
        print(success_msg)

def main():
    parser = argparse.ArgumentParser(description="Convert images to various formats (ICNS, PNG, JPG, WebP)")
    parser.add_argument("input", help="Input image file path")
    parser.add_argument("output", help="Output file path")
    parser.add_argument("--format", default="icns", choices=SUPPORTED_FORMATS,
                        help=f"Output format ({', '.join(SUPPORTED_FORMATS)}) (default: icns)")
    parser.add_argument("--min-size", type=int, default=16, help="Minimum icon size (default: 16), primarily for ICNS")
    parser.add_argument("--max-size", type=int, help="Maximum icon size (default: auto-detected from image), primarily for ICNS")
    
    args = parser.parse_args()
    
    input_path = args.input
    output_path = args.output
    output_format = args.format.lower()
    
    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' does not exist.")
        sys.exit(1)
        
    try:
        # Display image information
        width, height = get_image_info(input_path)
        print(f"Input image: {input_path}")
        print(f"Image dimensions: {width}x{height}")
        
        convert_image(input_path, output_path, output_format, args.min_size, args.max_size)
    except Exception as e:
        print(f"Error converting image: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()