"""Login startup registration. Registry and schtasks are mocked."""
from core.windows_startup import (
    REQUIRES_ADMIN_ELEVATION,
    SOURCE_NOTE,
    StartupRegistrar,
    command_from_task_xml,
    commands_equivalent,
    format_launch_command,
)


class MemoryRegistry:
    def __init__(self, value=None):
        self.value = value
        self.writes = []
        self.deletes = 0

    def read(self):
        return self.value

    def write(self, command):
        self.writes.append(command)
        self.value = command

    def delete(self):
        self.deletes += 1
        self.value = None


class Proc:
    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _xml(command, arguments='--minimized'):
    return f'''<?xml version="1.0"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Actions>
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>
    </Exec>
  </Actions>
</Task>
'''


def test_format_launch_command_quotes_path_with_spaces():
    command = format_launch_command(r'C:\Program Files\LoL\LoLAutoAccept.exe')
    assert command == r'"C:\Program Files\LoL\LoLAutoAccept.exe" --minimized'
    assert commands_equivalent(command, r'C:\Program Files\LoL\LoLAutoAccept.exe --minimized')


def test_source_run_does_not_touch_registry_or_schtasks():
    def run(_args):
        raise AssertionError('schtasks should not be called from source')

    class Guard:
        def read(self):
            raise AssertionError('registry read')

        def write(self, _command):
            raise AssertionError('registry write')

        def delete(self):
            raise AssertionError('registry delete')

    registrar = StartupRegistrar(
        frozen=False,
        executable=r'C:\LoLAutoAccept.exe',
        registry=Guard(),
        run_command=run,
    )
    enabled = registrar.sync(True)
    disabled = registrar.sync(False)

    assert enabled.available is False
    assert enabled.ok is True
    assert enabled.changed is False
    assert enabled.message == SOURCE_NOTE
    assert disabled.available is False
    assert registrar.status()['available'] is False
    assert registrar.status()['requires_admin'] is REQUIRES_ADMIN_ELEVATION


def test_run_key_registers_quoted_exe_and_minimized_flag():
    registry = MemoryRegistry()
    calls = []

    def run(args):
        calls.append(list(args))
        return Proc()

    exe = r'C:\Program Files\LoL\LoLAutoAccept.exe'
    registrar = StartupRegistrar(
        frozen=True,
        executable=exe,
        requires_admin=False,
        registry=registry,
        run_command=run,
    )

    result = registrar.sync(True)
    assert result.ok is True
    assert result.method == 'hkcu_run'
    assert result.changed is True
    assert registry.value == f'"{exe}" --minimized'
    assert calls == []

    again = registrar.sync(True)
    assert again.changed is False
    assert registry.writes == [f'"{exe}" --minimized']


def test_run_key_reregisters_when_exe_moves_and_removes_when_disabled():
    exe = r'E:\New\LoLAutoAccept.exe'
    registry = MemoryRegistry(r'"D:\Old\LoLAutoAccept.exe" --minimized')
    registrar = StartupRegistrar(
        frozen=True,
        executable=exe,
        requires_admin=False,
        registry=registry,
        run_command=lambda _args: (_ for _ in ()).throw(AssertionError('schtasks')),
    )

    moved = registrar.sync(True)
    assert moved.changed is True
    assert registry.value == f'"{exe}" --minimized'

    # Same command with different quoting is left alone.
    registry.value = f'{exe} --minimized'
    same = registrar.sync(True)
    assert same.changed is False

    removed = registrar.sync(False)
    assert removed.enabled is False
    assert removed.changed is True
    assert registry.value is None

    already_gone = registrar.sync(False)
    assert already_gone.changed is False
    assert already_gone.ok is True


def test_task_scheduler_used_only_when_elevation_is_required():
    registry = MemoryRegistry()
    calls = []

    def run(args):
        calls.append(list(args))
        if '/Query' in args:
            return Proc(1, '', 'ERROR: The system cannot find the file specified.')
        return Proc(0, 'SUCCESS', '')

    exe = r'C:\Program Files\LoL\LoLAutoAccept.exe'
    registrar = StartupRegistrar(
        frozen=True,
        executable=exe,
        requires_admin=True,
        registry=registry,
        run_command=run,
    )

    created = registrar.sync(True)
    assert created.ok is True
    assert created.method == 'task_scheduler'
    assert created.changed is True
    assert registry.writes == []

    create = calls[-1]
    assert create[:2] == ['schtasks', '/Create']
    assert create[create.index('/SC') + 1] == 'ONLOGON'
    assert create[create.index('/RL') + 1] == 'HIGHEST'
    assert create[create.index('/TN') + 1] == 'LoLAutoAccept'
    assert create[create.index('/TR') + 1] == f'"{exe}" --minimized'
    assert '/F' in create


def test_task_is_not_recreated_when_command_matches_and_deletes_when_disabled():
    exe = r'C:\Tools\LoLAutoAccept.exe'
    calls = []

    def run(args):
        calls.append(list(args))
        if '/Query' in args:
            return Proc(0, _xml(exe), '')
        return Proc(0, 'SUCCESS', '')

    registrar = StartupRegistrar(
        frozen=True,
        executable=exe,
        requires_admin=True,
        registry=MemoryRegistry(),
        run_command=run,
    )

    same = registrar.sync(True)
    assert same.changed is False
    assert all('/Create' not in call for call in calls)

    removed = registrar.sync(False)
    assert removed.changed is True
    assert calls[-1] == ['schtasks', '/Delete', '/TN', 'LoLAutoAccept', '/F']


def test_task_command_is_refreshed_when_path_changes():
    calls = []

    def run(args):
        calls.append(list(args))
        if '/Query' in args:
            return Proc(0, _xml(r'D:\Old\LoLAutoAccept.exe'), '')
        return Proc(0, 'SUCCESS', '')

    exe = r'E:\Moved\LoLAutoAccept.exe'
    registrar = StartupRegistrar(
        frozen=True,
        executable=exe,
        requires_admin=True,
        registry=MemoryRegistry(),
        run_command=run,
    )
    result = registrar.sync(True)
    assert result.changed is True
    create = [call for call in calls if '/Create' in call][-1]
    assert create[create.index('/TR') + 1] == f'"{exe}" --minimized'


def test_schtasks_failure_is_reported():
    def run(args):
        if '/Query' in args:
            return Proc(1, '', 'not found')
        return Proc(1, '', 'Access is denied.')

    registrar = StartupRegistrar(
        frozen=True,
        executable=r'C:\LoLAutoAccept.exe',
        requires_admin=True,
        registry=MemoryRegistry(),
        run_command=run,
    )
    result = registrar.sync(True)
    assert result.ok is False
    assert result.changed is False
    assert 'Access is denied' in result.message


def test_disabled_task_query_miss_does_not_delete():
    calls = []

    def run(args):
        calls.append(list(args))
        return Proc(1, '', 'not found')

    registrar = StartupRegistrar(
        frozen=True,
        executable=r'C:\LoLAutoAccept.exe',
        requires_admin=True,
        registry=MemoryRegistry(),
        run_command=run,
    )
    result = registrar.sync(False)
    assert result.ok is True
    assert result.changed is False
    assert all('/Delete' not in call for call in calls)


def test_command_from_task_xml():
    parsed = command_from_task_xml(_xml(r'C:\Program Files\LoL\LoLAutoAccept.exe'))
    assert commands_equivalent(
        parsed,
        r'"C:\Program Files\LoL\LoLAutoAccept.exe" --minimized',
    )
    assert command_from_task_xml('not xml') is None
    assert command_from_task_xml('') is None
