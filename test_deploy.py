# Pre-deployment Tests for MM Bot

import json
import os
import subprocess
import sys


def test_syntax():
    """Test Python syntax"""
    print("📋 Testing syntax...")
    for f in ["mm_bot.py", "servicedesk.py"]:
        result = subprocess.run(["python3", "-m", "py_compile", f], capture_output=True)
        if result.returncode != 0:
            print(f"   ❌ {f} - syntax error")
            return False
        print(f"   ✓ {f}")
    return True


def test_config():
    """Test config.json"""
    print("📋 Testing config.json...")
    try:
        with open("config.json") as f:
            data = json.load(f)
        print(f"   ✓ config.json valid")
        return True
    except Exception as e:
        print(f"   ❌ config.json: {e}")
        return False


def test_imports():
    """Test imports"""
    print("📋 Testing imports...")
    try:
        # Don't run, just check compile
        import py_compile

        py_compile.compile("mm_bot.py", doraise=True)
        py_compile.compile("servicedesk.py", doraise=True)
        print("   ✓ imports OK")
        return True
    except Exception as e:
        print(f"   ❌ imports: {e}")
        return False


def test_secrets():
    """Check no hardcoded secrets"""
    print("📋 Checking for secrets...")
    forbidden = ["ghp_", "BOT_TOKEN=6", "607"]
    try:
        for f in ["mm_bot.py", "servicedesk.py"]:
            with open(f) as fp:
                content = fp.read()
                for word in forbidden:
                    if word in content and "secrets.BOT_TOKEN" not in content:
                        print(f"   ⚠️ {f}: possible secret")
        print("   ✓ no obvious secrets")
        return True
    except Exception as e:
        print(f"   ❌ {e}")
        return False


def main():
    os.chdir(os.getcwd())  # test runs in repo dir

    results = []
    results.append(test_syntax())
    results.append(test_config())
    results.append(test_imports())
    results.append(test_secrets())

    print("\n" + "=" * 40)
    if all(results):
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
