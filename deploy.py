#!/usr/bin/env python3
"""
PyMercury Deployment Script (Python version)
Usage: python deploy.py <version>
Example: python deploy.py 1.0.5
"""

import sys
import os
import subprocess
import re
import shutil
from pathlib import Path

def print_colored(message, color_code):
    """Print colored text to terminal"""
    print(f"\033[{color_code}m{message}\033[0m")

def print_info(message):
    print_colored(f"ℹ️  {message}", "0;34")

def print_success(message):
    print_colored(f"✅ {message}", "0;32")

def print_warning(message):
    print_colored(f"⚠️  {message}", "1;33")

def print_error(message):
    print_colored(f"❌ {message}", "0;31")

def print_step(message):
    print_colored(f"🔄 {message}", "0;34")

def validate_version(version):
    """Validate semantic version format"""
    pattern = r'^[0-9]+\.[0-9]+\.[0-9]+$'
    return re.match(pattern, version) is not None

def check_dependencies():
    """Check if required Python packages are available"""
    try:
        import build
        import twine
        return True
    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Install with: pip install build twine")
        return False

def get_current_version():
    """Extract current version from pyproject.toml"""
    try:
        with open('pyproject.toml', 'r') as f:
            content = f.read()
            match = re.search(r'^version = "([^"]+)"', content, re.MULTILINE)
            if match:
                return match.group(1)
    except FileNotFoundError:
        print_error("pyproject.toml not found in current directory!")
        return None
    return None

def update_version(new_version):
    """Update version in pyproject.toml"""
    try:
        # Create backup
        shutil.copy('pyproject.toml', 'pyproject.toml.backup')
        print_success("Backup created: pyproject.toml.backup")

        # Read and update
        with open('pyproject.toml', 'r') as f:
            content = f.read()

        # Replace version
        updated_content = re.sub(
            r'^version = "[^"]+"',
            f'version = "{new_version}"',
            content,
            flags=re.MULTILINE
        )

        # Write back
        with open('pyproject.toml', 'w') as f:
            f.write(updated_content)

        # Verify
        if get_current_version() == new_version:
            return True
        else:
            # Restore backup on failure
            shutil.copy('pyproject.toml.backup', 'pyproject.toml')
            return False

    except Exception as e:
        print_error(f"Failed to update version: {e}")
        return False

def run_command(command, description):
    """Run a shell command with proper error handling"""
    print_step(description)
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print_success(f"{description} completed")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed!")
        if e.stderr:
            print_error(f"Error: {e.stderr}")
        return False, e.stderr

def restore_backup():
    """Restore backup if it exists"""
    if os.path.exists('pyproject.toml.backup'):
        print_info("Restoring backup...")
        shutil.copy('pyproject.toml.backup', 'pyproject.toml')
        os.remove('pyproject.toml.backup')

def main():
    # Check arguments
    if len(sys.argv) != 2:
        print_error("No version number provided!")
        print("Usage: python deploy.py <version>")
        print("Example: python deploy.py 1.0.5")
        sys.exit(1)

    version = sys.argv[1]

    # Validate version format
    if not validate_version(version):
        print_error("Invalid version format! Use semantic versioning (e.g., 1.0.5)")
        sys.exit(1)

    # Check if pyproject.toml exists
    if not os.path.exists('pyproject.toml'):
        print_error("pyproject.toml not found in current directory!")
        sys.exit(1)

    # Check dependencies
    print_step("Checking required tools...")
    if not check_dependencies():
        sys.exit(1)
    print_success("All required tools are available")

    # Get current version
    current_version = get_current_version()
    if not current_version:
        print_error("Could not determine current version from pyproject.toml")
        sys.exit(1)

    print_info(f"Current version: {current_version}")
    print_info(f"New version: {version}")

    # Confirm deployment
    response = input(f"\nDo you want to deploy version {version}? (y/N): ").strip().lower()
    if response != 'y':
        print_warning("Deployment cancelled")
        sys.exit(0)

    try:
        # Update version
        print_step("Updating version in pyproject.toml...")
        if not update_version(version):
            print_error("Failed to update version in pyproject.toml")
            sys.exit(1)
        print_success(f"Version updated: {current_version} → {version}")

        # Step 1: Clean up build artifacts
        success, _ = run_command(
            "rm -rf dist/ *.egg-info/ build/",
            "Cleaning up build artifacts"
        )
        if not success:
            restore_backup()
            sys.exit(1)

        # Step 2: Build package
        success, _ = run_command(
            "python -m build",
            "Building package"
        )
        if not success:
            restore_backup()
            sys.exit(1)

        # Check if dist has files
        dist_path = Path("dist")
        if not dist_path.exists() or not any(dist_path.iterdir()):
            print_error("No files found in dist/ directory after build")
            restore_backup()
            sys.exit(1)

        # List built files
        print_info("Built files:")
        for file in dist_path.iterdir():
            print(f"  {file.name}")

        # Step 3: Confirm upload
        print()
        print_warning("About to upload to PyPI. Make sure you have:")
        print_warning("1. Configured your PyPI credentials (~/.pypirc or environment variables)")
        print_warning("2. Tested the package locally")
        print_warning("3. Updated documentation and changelog")

        response = input("\nContinue with PyPI upload? (y/N): ").strip().lower()
        if response != 'y':
            print_warning("Upload cancelled. Build artifacts remain in dist/")
            print_info("You can upload manually later with: python -m twine upload dist/*")
            os.remove('pyproject.toml.backup')
            sys.exit(0)

        # Upload to PyPI
        success, output = run_command(
            "python -m twine upload dist/*",
            "Uploading to PyPI"
        )

        if success:
            print_success(f"Successfully deployed version {version} to PyPI!")
            os.remove('pyproject.toml.backup')

            print()
            print_info("Deployment Summary:")
            print_info(f"  Package: mercury-co-nz-api")
            print_info(f"  Version: {version}")
            print_info(f"  Previous: {current_version}")
            print_info(f"  Status: ✅ Published to PyPI")

            print()
            print_info("Next steps:")
            print_info(f"1. Tag the release: git tag v{version} && git push origin v{version}")
            print_info("2. Create GitHub release with changelog")
            print_info("3. Update documentation if needed")
        else:
            print_error("Upload to PyPI failed!")
            restore_backup()
            print_warning("Build artifacts remain in dist/ for manual inspection")
            sys.exit(1)

    except KeyboardInterrupt:
        print_warning("\nDeployment interrupted by user")
        restore_backup()
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        restore_backup()
        sys.exit(1)

if __name__ == "__main__":
    main()
