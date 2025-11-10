import asyncio
import aiofiles
import pathlib
import re
import shlex
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

HTPASSWD_CMD = "/usr/bin/htpasswd"  # путь к htpasswd
DEFAULT_PASSWD_FILE = "/etc/squid/passwd"
ACCESS_LOG = "/var/log/squid/access.log"

class SquidManager:
    def __init__(self, passwd_file: str = DEFAULT_PASSWD_FILE, access_log: str = ACCESS_LOG):
        self.passwd_file = pathlib.Path(passwd_file)
        self.access_log = pathlib.Path(access_log)

    # ---- Utilities (sync subprocess) ----
    def _run_cmd(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Sync wrapper. Keep fast and deterministic for htpasswd usage."""
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)

    async def add_user(self, username: str, password: str) -> Dict:
        """
        Добавить пользователя в htpasswd. Возвращает dict {ok:bool, msg:str}.
        Асинхронный API, но использует subprocess синхронно через loop.run_in_executor.
        """
        if not username or ":" in username or "/" in username:
            return False, "invalid username"

        cmd = ['sudo', HTPASSWD_CMD, "-b", str(self.passwd_file), username, password]
        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(None, lambda: self._run_cmd(cmd))
        if proc.returncode == 0 or "added" in proc.stdout.lower() or "updated" in proc.stdout.lower():
            return True, "user added/updated"
        # если файл не существовал, htpasswd -b создаст его с -c, но мы не используем -c here
        if "No such file" in proc.stderr or "No such" in proc.stdout:
            # пробуем создать файл с -c
            cmd2 = ['sudo', HTPASSWD_CMD, "-b", "-c", str(self.passwd_file), username, password]
            proc2 = await loop.run_in_executor(None, lambda: self._run_cmd(cmd2))
            if proc2.returncode == 0:
                return True, "user added and passwd file created"
            return False, proc2.stderr or proc2.stdout
        return False, proc.stderr or proc.stdout

    async def delete_user(self, username: str) -> Dict:
        """
        Удалить пользователя из htpasswd.
        """
        cmd = ['sudo', HTPASSWD_CMD, "-D", str(self.passwd_file), username]
        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(None, lambda: self._run_cmd(cmd))
        if proc.returncode == 0:
            return True, "deleted"
        # htpasswd -D возвращает non-zero если не найден; проверим stderr
        if "not found" in proc.stderr.lower() or "no such" in proc.stderr.lower():
            return False, "user not found"
        return False, proc.stderr or proc.stdout

    async def list_users(self) -> List[str]:
        """
        Вернуть список пользователей из htpasswd-файла.
        """
        if not self.passwd_file.exists():
            return []
        async with aiofiles.open(self.passwd_file, mode='r') as f:
            content = await f.read()
        users = []
        for line in content.splitlines():
            if not line.strip(): 
                continue
            parts = line.split(':', 1)
            if parts:
                users.append(parts[0])
        return users

    # ---- Log parsing / inactivity ----
    async def _tail_access_log(self, max_lines: int = 20000) -> List[str]:
        """
        Читает последние max_lines из access.log асинхронно.
        Для больших логов разумно ставить ограничения.
        """
        if not self.access_log.exists():
            return []
        stat = await asyncio.get_event_loop().run_in_executor(None, self.access_log.stat)
        size = stat.st_size
        # читаем файл полностью если небольшой, иначе читаем с конца
        if size < 5 * 1024 * 1024:  # 5MB
            async with aiofiles.open(self.access_log, mode='r') as f:
                txt = await f.read()
            return txt.splitlines()[-max_lines:]
        # если большой, читает блок с конца
        block = 200000  # bytes
        async with aiofiles.open(self.access_log, mode='rb') as f:
            await f.seek(max(0, size - block))
            data = await f.read()
        lines = data.decode(errors='ignore').splitlines()
        return lines[-max_lines:]

    async def get_last_activity_by_user(self) -> Dict[str, datetime]:
        """
        Парсит access.log и возвращает словарь {username: last_datetime_utc}.
        Важно: формат логов может отличаться. Скрипт пытается извлечь имя пользователя (username).
        """
        lines = await self._tail_access_log()
        user_last = {}
        # Простая регулярка, надеемся что лог содержит имя пользователя в отдельном поле.
        # Пример строки squid (типичный): "1596499200.123    200 192.0.2.1 TCP_MISS/200 1234 GET http://... user - HIER_NONE/0.0.0.0 text/html"
        # Мы попытаемся найти username как поле, не являющееся IP или "-", и не URL.
        user_pattern = re.compile(r'\s([A-Za-z0-9_\-\.]{1,64})\s')  # грубая попытка
        # Также попробуем найти поле %un если присутствует: оно обычно стоит после URL, поэтому возьмём 7-е поле
        for raw in reversed(lines):  # идём с конца, чтобы фиксировать последний таймстемп
            parts = raw.split()
            if len(parts) < 6:
                # попробовать regex
                m = user_pattern.search(raw)
                if m:
                    uname = m.group(1)
                else:
                    continue
            else:
                # попытка: username часто в поле 7 или 8
                possible = None
                for idx in (6,7,8):
                    if idx < len(parts):
                        cand = parts[idx]
                        if cand != '-' and not cand.startswith('http') and not re.match(r'^\d+\.\d+\.\d+\.\d+$', cand):
                            possible = cand
                            break
                uname = possible or None
            if not uname:
                continue
            # поиском timestamp в начале строки (Unix epoch with fraction) или в формате [dd/Mon/...]
            ts = None
            m_ts = re.match(r'^(\d+\.\d+)', raw)
            if m_ts:
                try:
                    ts = datetime.fromtimestamp(float(m_ts.group(1)), tz=timezone.utc)
                except Exception:
                    ts = None
            if not ts:
                # попробовать искать дату в формате [21/Oct/2025:...] - часто для httpd; пропустим если нет
                m2 = re.search(r'\[(\d{1,2}/[A-Za-z]{3}/\d{4}:[^\]]+)\]', raw)
                if m2:
                    try:
                        ts = datetime.strptime(m2.group(1), "%d/%b/%Y:%H:%M:%S %z")
                        ts = ts.astimezone(timezone.utc)
                    except Exception:
                        ts = None
            if not ts:
                # fallback: текущее время (не идеально)
                ts = datetime.now(timezone.utc)
            # сохраняем последний (так как идём с конца, первое появление — последний)
            if uname not in user_last:
                user_last[uname] = ts
        return user_last

    async def purge_inactive(self, inactive_days: int = 30) -> Dict[str, List[str]]:
        """
        Удаляет пользователей, которые не заходили более inactive_days.
        Возвращает {"deleted":[...], "skipped":[...], "errors":[...]}
        """
        now = datetime.now(timezone.utc)
        last = await self.get_last_activity_by_user()
        users = await self.list_users()
        deleted = []
        skipped = []
        errors = []
        for u in users:
            last_seen = last.get(u)
            if last_seen is None:
                # если пользователя нет в логах, считаем неактивным
                last_seen = datetime.fromtimestamp(0, tz=timezone.utc)
            age = (now - last_seen).days
            if age >= inactive_days:
                success, message = await self.delete_user(u)
                if success:
                    deleted.append(u)
                else:
                    errors.append(f"{u}: {message}")
            else:
                skipped.append(u)
        return True, {"deleted": deleted, "skipped": skipped, "errors": errors}
