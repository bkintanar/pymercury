#!/usr/bin/env python3
"""
Simple test runner for pymercury library

Run the modern pytest test suite.
"""

import subprocess
import sys


def main():
    """Run the complete test suite"""
    print("🧪 PyMercury Library - Modern Test Suite")
    print("=" * 50)

    # Check if pytest is available
    try:
        import pytest
        print("✅ pytest available")
    except ImportError:
        print("❌ pytest not found. Install with: pip install pytest")
        return 1

    # Run all tests
    print("\n🚀 Running comprehensive test suite...")
    result = subprocess.run([
        sys.executable, '-m', 'pytest', 'tests/',
        '-v', '--tb=short', '--strict-markers'
    ])

    if result.returncode == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Refactored structure working correctly")
        print("✅ All three services (Electricity, Gas, Broadband) tested")
        print("✅ Complete import system validated")
        print("✅ Error handling verified")
        print("✅ Configuration system tested")
        print("✅ API client functionality confirmed")
        return 0
    else:
        print("\n❌ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
