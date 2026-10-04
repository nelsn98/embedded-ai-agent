"""Run this project's offline suite without ESP-IDF pytest plugin interference."""
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0, str(root))
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
os.environ.pop('PYTEST_PLUGINS', None)
os.environ.pop('PYTEST_ADDOPTS', None)
import pytest
raise SystemExit(pytest.main(['-c', 'pytest.ini', '--confcutdir=tests', 'tests', '-q']))
