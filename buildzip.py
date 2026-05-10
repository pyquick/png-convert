from support.archive_manager import create_archive

def build_zip():
    print("Building Zip for ARM64")
    create_archive(
        "./dist/Converter_arm64_darwin.zip",
        ["./dist/Converter.app"],
        "zip"
    )

def build_zip_intel():
    print("Building Zip for Intel")
    create_archive(
        "./dist/Converter_intel_darwin.zip",
        ["./dist/Converter.app"],
        "zip"
    )
build_zip_intel()