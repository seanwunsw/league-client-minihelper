"""Register this app to start at Windows login, minimised to the tray.

The packaged executable does not request elevation. ``build.spec`` leaves
``uac_admin`` unset (PyInstaller default False) and the repository has no
manifest with ``requireAdministrator``, so the exe runs as the logged-in
user. A value under
``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` therefore starts
it at logon without a UAC prompt.

HKCU Run cannot elevate a process silently. If a future build sets
``uac_admin=True``, set ``REQUIRES_ADMIN_ELEVATION`` below to True as well.
Registration then creates a Task Scheduler ONLOGON task with highest
privileges (``schtasks /RL HIGHEST``) instead of a Run key.

Running from source (``sys.frozen`` is false) does not register anything.
The UI disables the setting and shows a note.
"""
from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

try:
    import winreg
except ImportError:  # non-Windows (tests, source on Linux)
    winreg = None

# Keep this in lockstep with build.spec. False -> HKCU Run. True -> schtasks.
REQUIRES_ADMIN_ELEVATION = False

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "LoLAutoAccept"
TASK_NAME = "LoLAutoAccept"

SOURCE_NOTE = (
    "Start with Windows is only available in the packaged LoLAutoAccept.exe, "
    "not when running from source."
)
ADMIN_NOTE = (
    "This build requires administrator rights, so startup is a Task Scheduler "
    "logon task with highest privileges. A registry Run entry would not "
    "elevate silently at login."
)


@dataclass
class StartupResult:
    ok: bool
    available: bool
    enabled: bool
    method: Optional[str] = None
    changed: bool = False
    message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'ok': self.ok,
            'available': self.available,
            'enabled': self.enabled,
            'method': self.method,
            'changed': self.changed,
            'message': self.message,
        }


def format_launch_command(executable: str) -> str:
    """Quoted exe path plus the flag that starts the app in the tray."""
    cleaned = str(executable).replace('"', '').strip()
    return f'"{cleaned}" --minimized'


def commands_equivalent(left: Optional[str], right: Optional[str]) -> bool:
    """Compare launch commands, ignoring quote style and path case."""
    if not left or not right:
        return False

    def norm(value: str) -> str:
        return ' '.join(value.replace('"', '').split()).casefold()

    return norm(left) == norm(right)


class _WinregStore:
    """HKCU Run key. Inject a fake with the same three methods in tests."""

    def read(self) -> Optional[str]:
        if winreg is None:
            raise OSError('winreg is not available')
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
                value, _regtype = winreg.QueryValueEx(key, RUN_VALUE_NAME)
                return str(value)
        except FileNotFoundError:
            return None

    def write(self, command: str) -> None:
        if winreg is None:
            raise OSError('winreg is not available')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)

    def delete(self) -> None:
        if winreg is None:
            raise OSError('winreg is not available')
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
            ) as key:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                except FileNotFoundError:
                    return
        except FileNotFoundError:
            return


class StartupRegistrar:
    """Create, refresh, or remove the login startup entry."""

    def __init__(
        self,
        *,
        frozen: Optional[bool] = None,
        executable: Optional[str] = None,
        requires_admin: Optional[bool] = None,
        registry=None,
        run_command: Optional[Callable[[Sequence[str]], object]] = None,
    ):
        self.frozen = bool(getattr(sys, 'frozen', False) if frozen is None else frozen)
        if executable is None:
            self.executable = os.path.abspath(sys.executable)
        else:
            self.executable = executable
        self.requires_admin = (
            REQUIRES_ADMIN_ELEVATION if requires_admin is None else bool(requires_admin)
        )
        self.registry = registry if registry is not None else _WinregStore()
        self.run_command = run_command if run_command is not None else self._default_run

    def status(self) -> dict:
        """UI description. Does not touch the registry or Task Scheduler."""
        if not self.frozen:
            return {
                'available': False,
                'method': None,
                'note': SOURCE_NOTE,
                'requires_admin': self.requires_admin,
            }
        if self.requires_admin:
            return {
                'available': True,
                'method': 'task_scheduler',
                'note': ADMIN_NOTE,
                'requires_admin': True,
            }
        return {
            'available': True,
            'method': 'hkcu_run',
            'note': None,
            'requires_admin': False,
        }

    def sync(self, enabled: bool) -> StartupResult:
        """Make the login entry match ``enabled`` and the current exe path.

        When the exe has moved, the stored command no longer matches and is
        rewritten. From source this is a no-op so a dev run cannot delete
        the registration of an installed copy.
        """
        enabled = bool(enabled)
        if not self.frozen:
            return StartupResult(
                ok=True,
                available=False,
                enabled=enabled,
                method=None,
                changed=False,
                message=SOURCE_NOTE,
            )
        try:
            if self.requires_admin:
                return self._sync_task(enabled)
            return self._sync_run_key(enabled)
        except Exception as exc:
            method = 'task_scheduler' if self.requires_admin else 'hkcu_run'
            return StartupResult(False, True, enabled, method, False, str(exc))

    def _desired_command(self) -> str:
        if not str(self.executable).strip():
            raise ValueError('Executable path is empty')
        return format_launch_command(self.executable)

    def _sync_run_key(self, enabled: bool) -> StartupResult:
        current = self.registry.read()
        if not enabled:
            if current is None:
                return StartupResult(True, True, False, 'hkcu_run', False, None)
            self.registry.delete()
            return StartupResult(True, True, False, 'hkcu_run', True, None)

        desired = self._desired_command()
        if commands_equivalent(current, desired):
            return StartupResult(True, True, True, 'hkcu_run', False, None)
        self.registry.write(desired)
        return StartupResult(True, True, True, 'hkcu_run', True, None)

    def _sync_task(self, enabled: bool) -> StartupResult:
        current = self._query_task_command()
        if not enabled:
            if current is None:
                return StartupResult(True, True, False, 'task_scheduler', False, None)
            result = self._schtasks(['/Delete', '/TN', TASK_NAME, '/F'])
            if not _success(result):
                return StartupResult(
                    False, True, True, 'task_scheduler', False, _error_text(result)
                )
            return StartupResult(True, True, False, 'task_scheduler', True, None)

        desired = self._desired_command()
        if commands_equivalent(current, desired):
            return StartupResult(True, True, True, 'task_scheduler', False, None)
        result = self._schtasks([
            '/Create', '/F',
            '/TN', TASK_NAME,
            '/SC', 'ONLOGON',
            '/RL', 'HIGHEST',
            '/TR', desired,
        ])
        if not _success(result):
            return StartupResult(
                False, True, False, 'task_scheduler', False, _error_text(result)
            )
        return StartupResult(True, True, True, 'task_scheduler', True, None)

    def _query_task_command(self) -> Optional[str]:
        result = self._schtasks(['/Query', '/TN', TASK_NAME, '/XML'])
        if not _success(result):
            return None
        return command_from_task_xml(_stdout(result))

    def _schtasks(self, args: Sequence[str]):
        return self.run_command(['schtasks', *list(args)])

    @staticmethod
    def _default_run(args: Sequence[str]):
        return subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            check=False,
        )


def command_from_task_xml(xml_text: str) -> Optional[str]:
    """Rebuild the launch command from a ``schtasks /Query /XML`` document."""
    if not xml_text or not str(xml_text).strip():
        return None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    command = None
    arguments = None
    for elem in root.iter():
        tag = elem.tag.rsplit('}', 1)[-1]
        text = (elem.text or '').strip()
        if not text:
            continue
        if tag == 'Command' and command is None:
            command = text
        elif tag == 'Arguments' and arguments is None:
            arguments = text
    if not command:
        return None
    if arguments:
        if command.startswith('"'):
            return f'{command} {arguments}'
        return f'"{command}" {arguments}'
    return command


def _success(result: object) -> bool:
    return getattr(result, 'returncode', 1) == 0


def _stdout(result: object) -> str:
    return getattr(result, 'stdout', '') or ''


def _error_text(result: object) -> str:
    stderr = (getattr(result, 'stderr', '') or '').strip()
    stdout = (getattr(result, 'stdout', '') or '').strip()
    return stderr or stdout or f'schtasks exited with code {getattr(result, "returncode", "?")}'
