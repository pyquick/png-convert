#!/usr/bin/env python3

"""
Compile Script for PNG to ICNS Converter

This script compiles the GUI application using Nuitka to create a standalone executable.
"""

import subprocess
import sys
import os

def compile_gui():
    """Compile the GUI application using Nuitka"""
    print("Compiling GUI application with Nuitka...")
    
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the main script to compile
    main_script = os.path.join(current_dir, "Converter.py")
    
    # Check if the main script exists
    if not os.path.exists(main_script):
        print(f"Error: Main script not found at {main_script}")
        return False
    path= os.path.dirname(os.path.abspath(__file__))
    # Nuitka compilation command
    cmd = [
        sys.executable, "-m", "nuitka",
        
        "--assume-yes-for-downloads",   # Assume yes for downloads  
        "--mode=app",
        "--clang",
        "--lto=no",
        #"--clang++-args=-headerpad_max_install_names",
        "--macos-app-icon=" + os.path.join(current_dir,"AppIcon.icns"), # App icon
        "--include-data-file=" + os.path.join(current_dir,"zip.png")+ f"=./zip.png",
        "--include-data-file=" + os.path.join(current_dir,"update","update_apply.command")+ f"=./update/update_apply.command",
        "--include-data-file=" + os.path.join(current_dir,"update","restart.command")+ f"=./update/restart.command",
        "--include-data-file=" + os.path.join(current_dir,"update","README.md")+ f"=./update/README.md",
        "--include-data-file=" + os.path.join(current_dir,"update","download_update.py")+ f"=./update/download_update.py",
        "--include-data-file=" + os.path.join(current_dir,"update","update_manager.py")+ f"=./update/update_manager.py",
        "--include-data-file=" + os.path.join(current_dir,"zipd.png")+ f"=./zipd.png",
        "--include-data-file=" + os.path.join(current_dir,"AppIcon.png")+ f"=./AppIcon.png",
        "--include-data-file=" + os.path.join(current_dir,"AppIcond.png")+ f"=./AppIcond.png",
        "--include-data-dir="+os.path.join(current_dir,"qss")+"=./qss",
        "--include-data-dir="+os.path.join(current_dir,"support","CLI","Darwin")+"=./support/CLI/Darwin",
        "--macos-app-name=Converter", # App name
        "--macos-app-mode=gui",
        "--macos-app-version=2.0",
        "--include-package=arc_gui",
        "--include-package=image_converter", 
        "--include-package=support",
        "--include-package=update",  # 添加update包以确保所有更新功能正常工作
        "--macos-signed-app-name=com.pyquick.converter",
        "--enable-plugin=pyside6",
        "--prefer-source-code",
        "--output-dir=dist",      # Output directory
        "--remove-output", 
        "--follow-imports",
        # Python 3默认使用UTF-8编码，移除不支持的参数
        main_script
    ]
    
    try:
        print("Running Nuitka compilation...")
        subprocess.run(cmd, check=True, text=True)
        print("Compilation successful!")
        
        
        print("Executable created in dist/ directory")
        print("Copying Assets.car to Resources/")
        subprocess.run(["cp", os.path.join(current_dir,  "Assets.car"), os.path.join(current_dir, "dist", "Converter.app", "Contents", "Resources", "Assets.car")])
        print("Copying zip.png to MacOS/")
        subprocess.run(["cp", os.path.join(current_dir,  "zip.png"), os.path.join(current_dir, "dist", "Converter.app", "Contents", "MacOS", "zip.png")])
        subprocess.run(["cp", os.path.join(current_dir, "AppIcon.icns"), os.path.join(current_dir, "dist", "Converter.app", "Contents", "MacOS", "AppIcon.icns")])
        subprocess.run(["cp", os.path.join(current_dir, "AppIcon.png"), os.path.join(current_dir, "dist", "Converter.app", "Contents", "MacOS", "AppIcon.png")])
        subprocess.run(["cp", os.path.join(current_dir, "AppIcond.png"), os.path.join(current_dir, "dist", "Converter.app", "Contents", "MacOS", "AppIcond.png")])
        
        # Copy update directory and scripts to MacOS/update/
        print("Copying update directory to MacOS/")
        update_dest_dir = os.path.join(current_dir, "dist", "Converter.app", "Contents", "MacOS", "update")
        os.makedirs(update_dest_dir, exist_ok=True)
        
        # Copy all update files
        update_files = ["update_apply.command", "restart.command", "README.md", "download_update.py", "update_manager.py"]
        for file_name in update_files:
            src_file = os.path.join(current_dir, "update", file_name)
            dest_file = os.path.join(update_dest_dir, file_name)
            if os.path.exists(src_file):
                subprocess.run(["cp", src_file, dest_file])
                print(f"Copied {file_name} to update/")
                # Ensure scripts have execute permissions
                if file_name.endswith(".command"):
                    subprocess.run(["chmod", "+x", dest_file])
                    print(f"Set execute permissions for {file_name}")
        return True
    except subprocess.CalledProcessError as e:
        print("Compilation failed!")
        print(f"Error: {e}")
        print(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error during compilation: {e}")
        return False



def main():
    print("PNG to ICNS Converter - Compilation Script")
    print("=" * 40)
    
    # Create dist directory if it doesn't exist
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)
    
    # Compile both versions
    gui_success = compile_gui()
    print()

    print("\n" + "=" * 40)
    if gui_success:
        print("All compilations completed successfully!")
        print("Executables are located in the 'dist' directory:")
        print("- GUI application: dist/Converter.app")
    else:
        print("Some compilations failed. Please check the error messages above.")
        if not gui_success:
            print("- GUI compilation failed")

