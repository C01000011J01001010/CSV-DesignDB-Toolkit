import os
import sys

try:
    import msvcrt
except ImportError:
    msvcrt = None

lock_file_handle = None

def check_single_instance():
    global lock_file_handle
    temp_dir = os.environ.get("TEMP", os.path.dirname(os.path.abspath(__file__)))
    lock_file_path = os.path.join(temp_dir, "csv_toolkit.lock")
    try:
        lock_file_handle = open(lock_file_path, "w")
        if msvcrt:
            msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except (IOError, OSError):
        return False
    return True

def get_initial_dir():
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        return os.path.abspath(sys.argv[1])
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def is_disabled_path(filepath):
    parts = os.path.normpath(filepath).split(os.sep)
    for part in parts:
        if part.startswith("Disabled"):
            return True
    return False

def find_workspace_root(start_dir):
    current = os.path.abspath(start_dir)
    while True:
        try:
            for f in os.listdir(current):
                if f.startswith("__csvMetaRoot") and f.endswith(".root"):
                    return current, f
        except Exception:
            pass
        parent = os.path.dirname(current)
        if parent == current:
            return None, None
        current = parent

def create_workspace_root(target_dir, project_name):
    filename = f"__csvMetaRoot_{project_name}__.root"
    filepath = os.path.join(target_dir, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("CSV Metadata Workspace Root")
        return target_dir, filename
    except Exception as e:
        return None, None
