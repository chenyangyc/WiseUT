import subprocess
from pathlib import Path
import sys
import os


def add_module_path(module_name: str):
    """
    Ensure that a given module folder is added into sys.path,
    so it can be imported even if it uses relative-like imports inside.
    """
    module_dir = Path(__file__).parent / module_name
    os.chdir(module_dir)

    sys.path.insert(0, str(module_dir))


def run_with_interpreter(python_exec, module, func):
    """
    Launch a subprocess to run a function inside a given module,
    using a specific Python interpreter.
    """
    code = f"""
import sys
sys.path.insert(0, "{Path.cwd()}")  # ensure current project is visible
from {module} import {func}
{func}()
"""
    subprocess.run([python_exec, "-c", code], check=True)