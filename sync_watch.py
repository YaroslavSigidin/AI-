#!/usr/bin/env python3
"""
Скрипт автоматической синхронизации файлов при сохранении (альтернативный вариант)
Требует: pip install watchdog
"""

import os
import sys
import subprocess
import time
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("❌ Библиотека watchdog не установлена")
    print("Установите: pip install watchdog")
    sys.exit(1)


class SyncHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.last_sync = 0
        self.sync_delay = 1  # Задержка между синхронизациями (секунды)
        self.pending_files = set()
        
    def should_sync_file(self, path):
        """Проверяет, нужно ли синхронизировать файл"""
        path_str = str(path)
        exclusions = [
            '.bak.', '.broken.', '.git', '__pycache__', '.venv', 'venv',
            '.DS_Store', 'deploy.conf', '.example',
            '.db', '.sqlite', '.log', '.pid', '.pyc', '.pyo'
        ]
        return not any(excl in path_str for excl in exclusions)
    
    def sync_files(self):
        """Синхронизирует файлы на сервер"""
        current_time = time.time()
        if current_time - self.last_sync < self.sync_delay:
            return  # Слишком часто
        self.last_sync = current_time
        
        server = f"{self.config['user']}@{self.config['host']}"
        path = self.config['path']
        ssh_opts = self.config.get('ssh_opts', '')
        
        # Создаем exclude файл
        exclude_patterns = [
            '.bak.*', '*.bak.*', '.git/', '.gitignore', '.env',
            '*.db', '*.sqlite', '*.sqlite3', '*.log', '*.pid',
            '__pycache__/', '*.pyc', '*.pyo', '.venv/', 'venv/',
            '.DS_Store', 'deploy.conf', '*.example'
        ]
        
        exclude_file = Path('/tmp/rsync_exclude_sync')
        exclude_file.write_text('\n'.join(exclude_patterns))
        
        try:
            # Синхронизируем через rsync
            cmd = [
                'rsync', '-avz', '--delete',
                '--exclude-from', str(exclude_file),
                '-e', f'ssh {ssh_opts}' if ssh_opts else 'ssh',
                './', f'{server}:{path}/'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"✓ {time.strftime('%H:%M:%S')} Синхронизировано")
            else:
                print(f"⚠ {time.strftime('%H:%M:%S')} Ошибка: {result.stderr[:100]}")
        except Exception as e:
            print(f"⚠ {time.strftime('%H:%M:%S')} Ошибка синхронизации: {e}")
        finally:
            if exclude_file.exists():
                exclude_file.unlink()
    
    def on_modified(self, event):
        if event.is_directory:
            return
        if self.should_sync_file(event.src_path):
            self.sync_files()
    
    def on_created(self, event):
        if event.is_directory:
            return
        if self.should_sync_file(event.src_path):
            self.sync_files()
    
    def on_deleted(self, event):
        if event.is_directory:
            return
        self.sync_files()


def load_config():
    """Загружает конфигурацию из deploy.conf"""
    config_file = Path('deploy.conf')
    if not config_file.exists():
        print("❌ Файл deploy.conf не найден!")
        print("Скопируйте deploy.conf.example в deploy.conf и заполните параметры")
        sys.exit(1)
    
    config = {}
    with open(config_file) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                config[key.lower()] = value
    
    required = ['server_host', 'server_user', 'server_path']
    for key in required:
        if key not in config:
            print(f"❌ Отсутствует параметр {key.upper()} в deploy.conf")
            sys.exit(1)
    
    return {
        'host': config['server_host'],
        'user': config['server_user'],
        'path': config['server_path'],
        'ssh_opts': config.get('ssh_opts', '')
    }


def main():
    print("🔄 Запуск автоматической синхронизации (Python)...")
    
    config = load_config()
    print(f"📁 Локальная папка: {Path.cwd()}")
    print(f"🌐 Удаленный сервер: {config['user']}@{config['host']}:{config['path']}")
    print("💡 Для остановки нажмите Ctrl+C\n")
    
    # Первоначальная синхронизация
    handler = SyncHandler(config)
    print("📦 Первоначальная синхронизация...")
    handler.sync_files()
    print("✅ Первоначальная синхронизация завершена")
    print("👀 Ожидание изменений файлов...\n")
    
    # Запускаем наблюдатель
    observer = Observer()
    observer.schedule(handler, '.', recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n✅ Синхронизация остановлена")
    
    observer.join()


if __name__ == '__main__':
    main()
