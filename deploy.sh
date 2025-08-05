#!/bin/bash

# PyMercury Deployment Script
# Usage: ./deploy.sh <version>
# Example: ./deploy.sh 1.0.5

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_step() {
    echo -e "${BLUE}🔄 $1${NC}"
}

# Check if version argument is provided
if [ $# -eq 0 ]; then
    print_error "No version number provided!"
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.5"
    exit 1
fi

VERSION="$1"

# Validate version format (basic semantic versioning)
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_error "Invalid version format! Use semantic versioning (e.g., 1.0.5)"
    exit 1
fi

# Check if required files exist
if [ ! -f "pyproject.toml" ]; then
    print_error "pyproject.toml not found in current directory!"
    exit 1
fi

# Check if required tools are installed
print_step "Checking required tools..."

if ! command -v python &> /dev/null; then
    print_error "Python is not installed or not in PATH"
    exit 1
fi

if ! python -c "import build" &> /dev/null; then
    print_error "python build module not found. Install with: pip install build"
    exit 1
fi

if ! python -c "import twine" &> /dev/null; then
    print_error "twine not found. Install with: pip install twine"
    exit 1
fi

print_success "All required tools are available"

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "//' | sed 's/"//')
print_info "Current version: $CURRENT_VERSION"
print_info "New version: $VERSION"

# Confirm deployment
echo
read -p "Do you want to deploy version $VERSION? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Deployment cancelled"
    exit 0
fi

# Create backup of pyproject.toml
print_step "Creating backup of pyproject.toml..."
cp pyproject.toml pyproject.toml.backup
print_success "Backup created: pyproject.toml.backup"

# Update version in pyproject.toml
print_step "Updating version in pyproject.toml..."
sed -i.tmp "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
rm pyproject.toml.tmp 2>/dev/null || true  # Remove temp file (macOS compatibility)

# Verify the version was updated
NEW_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "//' | sed 's/"//')
if [ "$NEW_VERSION" != "$VERSION" ]; then
    print_error "Failed to update version in pyproject.toml"
    print_info "Restoring backup..."
    cp pyproject.toml.backup pyproject.toml
    rm pyproject.toml.backup
    exit 1
fi

print_success "Version updated: $CURRENT_VERSION → $VERSION"

# Step 1: Clean up build artifacts
print_step "Cleaning up build artifacts..."
rm -rf dist/ *.egg-info/ build/
print_success "Build artifacts cleaned"

# Step 2: Build the package
print_step "Building package..."
python -m build

if [ $? -ne 0 ]; then
    print_error "Build failed!"
    print_info "Restoring backup..."
    cp pyproject.toml.backup pyproject.toml
    rm pyproject.toml.backup
    exit 1
fi

print_success "Package built successfully"

# Check if dist directory has files
if [ ! "$(ls -A dist/)" ]; then
    print_error "No files found in dist/ directory after build"
    print_info "Restoring backup..."
    cp pyproject.toml.backup pyproject.toml
    rm pyproject.toml.backup
    exit 1
fi

# List built files
print_info "Built files:"
ls -la dist/

# Step 3: Upload to PyPI
echo
print_warning "About to upload to PyPI. Make sure you have:"
print_warning "1. Configured your PyPI credentials (~/.pypirc or environment variables)"
print_warning "2. Tested the package locally"
print_warning "3. Updated documentation and changelog"
echo

read -p "Continue with PyPI upload? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Upload cancelled. Build artifacts remain in dist/"
    print_info "You can upload manually later with: python -m twine upload dist/*"
    rm pyproject.toml.backup
    exit 0
fi

print_step "Uploading to PyPI..."
python -m twine upload dist/*

if [ $? -eq 0 ]; then
    print_success "Successfully deployed version $VERSION to PyPI!"
    rm pyproject.toml.backup

    echo
    print_info "Deployment Summary:"
    print_info "  Package: mercury-co-nz-api"
    print_info "  Version: $VERSION"
    print_info "  Previous: $CURRENT_VERSION"
    print_info "  Status: ✅ Published to PyPI"

    echo
    print_info "Next steps:"
    print_info "1. Tag the release: git tag v$VERSION && git push origin v$VERSION"
    print_info "2. Create GitHub release with changelog"
    print_info "3. Update documentation if needed"

else
    print_error "Upload to PyPI failed!"
    print_info "Restoring backup..."
    cp pyproject.toml.backup pyproject.toml
    rm pyproject.toml.backup
    print_warning "Build artifacts remain in dist/ for manual inspection"
    exit 1
fi
