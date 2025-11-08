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
        "--standalone",
        "--assume-yes-for-downloads",   # Assume yes for downloads  
        "--clang",
        "--lto=no",
        "--macos-create-app-bundle", # Create macOS app bundle
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

#!/usr/bin/env python3

"""
Compile Script for PNG to ICNS Converter

This script compiles the GUI application using PyInstaller to create a standalone executable.
"""

import subprocess
import sys
import os
import shutil

def build_pyinstaller():
    """Build the application using PyInstaller with spec file"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(current_dir, "Converter.py")
    spec_file = os.path.join(current_dir, "Converter.spec")
    
    if not os.path.exists(main_script):
        print(f"Error: Main script not found at {main_script}")
        return False
    
    # Create spec file if it doesn't exist
    if not os.path.exists(spec_file):
        print(f"Error: Spec file not found at {spec_file}")
        return False
    
    # Clean previous builds
    dist_path = os.path.join(current_dir, "dist")
    build_path = os.path.join(current_dir, "build")
    
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    
    # PyInstaller command with spec file
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",     # Clean PyInstaller cache
        spec_file
    ]
    
    try:
        print("Running PyInstaller build with spec file...")
        subprocess.run(cmd, check=True, text=True)
        print("PyInstaller build successful!")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print("PyInstaller build failed!")
        print(f"Error: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error during build: {e}")
        return False

def create_macos_app_bundle(current_dir, dist_path):
    """Create proper macOS .app bundle structure"""
    print("Creating macOS .app bundle...")
    
    app_name = "Converter.app"
    app_path = os.path.join(dist_path, app_name)
    contents_path = os.path.join(app_path, "Contents")
    macos_path = os.path.join(contents_path, "MacOS")
    resources_path = os.path.join(contents_path, "Resources")
    
    # Create directory structure
    os.makedirs(macos_path, exist_ok=True)
    os.makedirs(resources_path, exist_ok=True)
    
    # Move the executable to MacOS folder
    executable_src = os.path.join(dist_path, "Converter")
    executable_dest = os.path.join(macos_path, "Converter")
    
    if os.path.exists(executable_src):
        shutil.move(executable_src, executable_dest)
        
        # Make executable
        os.chmod(executable_dest, 0o755)
    
    # Create Info.plist
    info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>Converter</string>
    <key>CFBundleExecutable</key>
    <string>Converter</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.pyquick.converter</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Converter</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleVersion</key>
    <string>2.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
</dict>
</plist>"""
    
    with open(os.path.join(contents_path, "Info.plist"), "w") as f:
        f.write(info_plist)
    
    # Copy additional resources
    resources_to_copy = [
        ("zip.png", resources_path),
        ("AppIcon.icns", resources_path),
        ("AppIcon.png", resources_path),
        ("AppIcond.png", resources_path),
        ("Assets.car", resources_path),
    ]
    
    for resource, dest_dir in resources_to_copy:
        src = os.path.join(current_dir, resource)
        if os.path.exists(src):
            shutil.copy2(src, dest_dir)
            print(f"Copied {resource} to Resources/")
    
    # Copy qss directory
    qss_src = os.path.join(current_dir, "qss")
    qss_dest = os.path.join(resources_path, "qss")
    if os.path.exists(qss_src):
        if os.path.exists(qss_dest):
            shutil.rmtree(qss_dest)
        shutil.copytree(qss_src, qss_dest)
        print("Copied qss directory to Resources/")
    
    # Copy support files
    support_src = os.path.join(current_dir, "support", "CLI", "Darwin")
    support_dest = os.path.join(resources_path, "support", "CLI", "Darwin")
    if os.path.exists(support_src):
        os.makedirs(os.path.dirname(support_dest), exist_ok=True)
        if os.path.exists(support_dest):
            shutil.rmtree(support_dest)
        shutil.copytree(support_src, support_dest)
        print("Copied support files to Resources/")
    
    # Copy update directory
    update_src = os.path.join(current_dir, "update")
    update_dest = os.path.join(resources_path, "update")
    if os.path.exists(update_src):
        if os.path.exists(update_dest):
            shutil.rmtree(update_dest)
        shutil.copytree(update_src, update_dest)
        print("Copied update directory to Resources/")
        
        # Set execute permissions for .command files
        for root, dirs, files in os.walk(update_dest):
            for file in files:
                if file.endswith(".command"):
                    file_path = os.path.join(root, file)
                    os.chmod(file_path, 0o755)
                    print(f"Set execute permissions for {file}")
    
    print(f"macOS app bundle created at: {app_path}")
def main_py():
    print("PNG to ICNS Converter - PyInstaller Build Script")
    print("=" * 50)
    
    # Create dist directory if it doesn't exist
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist_pyinstaller")
    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)
    
    # Build with PyInstaller using spec file
    pyinstaller_success = build_pyinstaller()
    
    print("\n" + "=" * 50)
    if pyinstaller_success:
        print("PyInstaller build completed successfully!")
        print("Application bundle is located in the 'dist' directory:")
        print("- GUI application: dist/Converter.app")
    else:
        print("PyInstaller build failed. Please check the error messages above.")