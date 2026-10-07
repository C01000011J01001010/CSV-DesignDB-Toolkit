import os
import time
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utils import is_disabled_path
from core.converter import convert_xlsx_file

class WatcherHandler(FileSystemEventHandler):
    def __init__(self, log_callback):
        super().__init__()
        self.log_callback = log_callback
        self.last_processed = {}

    def on_created(self, event):
        self.process_event(event)

    def on_modified(self, event):
        self.process_event(event)

    def process_event(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        filename = os.path.basename(filepath)

        if is_disabled_path(filepath):
            return

        if filepath.endswith('.xlsx') and not filename.startswith('~$'):
            current_time = time.time()
            if filepath in self.last_processed:
                if current_time - self.last_processed[filepath] < 1.5:
                    return
            self.last_processed[filepath] = current_time

            self.log_callback(f"👀 [자동 감지] {filename} 변환 중...")
            success, result = convert_xlsx_file(filepath)
            if success:
                self.log_callback(f"✅ [감지 변환 완료] {os.path.basename(result)}\n")
            else:
                self.log_callback(f"❌ [감지 변환 실패] {filename}: {result}\n")

class PipelineWatcher:
    def __init__(self, log_callback):
        self.observer = None
        self.is_watching = False
        self.log_callback = log_callback

    def start(self, target_dir, recursive):
        if self.is_watching:
            return
        event_handler = WatcherHandler(self.log_callback)
        self.observer = Observer()
        self.observer.schedule(event_handler, target_dir, recursive=recursive)
        self.observer.start()
        self.is_watching = True

    def stop(self):
        if self.observer and self.is_watching:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.is_watching = False
