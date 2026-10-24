"""App-level settings: defaults, close behaviour, and launch flags.

Feature settings live on the features themselves. These keys belong to the
shell (window close and login startup) and must stay valid for older
config.yaml files that do not mention them.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Optional

import yaml

DEFAULT_CLOSE_ACTION = 'exit'
VALID_CLOSE_ACTIONS = ('exit', 'tray')
DEFAULT_START_WITH_WINDOWS = False


def default_config() -> dict:
    """Baseline config used when keys are missing from config.yaml."""
    return {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4,
        'start_minimized': False,
        'log_level': 'INFO',
        'close_action': DEFAULT_CLOSE_ACTION,
        'start_with_windows': DEFAULT_START_WITH_WINDOWS,
    }


def normalize_close_action(value: Any, invalid: Optional[str] = DEFAULT_CLOSE_ACTION) -> Optional[str]:
    """Return 'exit' or 'tray'. Unknown values become ``invalid`` (default 'exit')."""
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in VALID_CLOSE_ACTIONS:
            return candidate
    return invalid


def coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerce config values without treating the string 'false' as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ('1', 'true', 'yes', 'on'):
            return True
        if lowered in ('0', 'false', 'no', 'off', ''):
            return False
    return default


def apply_app_setting_defaults(config: dict) -> dict:
    """Fill close_action and start_with_windows. Other keys are left as-is."""
    if 'close_action' not in config:
        config['close_action'] = DEFAULT_CLOSE_ACTION
    else:
        normalized = normalize_close_action(config.get('close_action'), invalid=None)
        config['close_action'] = DEFAULT_CLOSE_ACTION if normalized is None else normalized

    if 'start_with_windows' not in config:
        config['start_with_windows'] = DEFAULT_START_WITH_WINDOWS
    else:
        config['start_with_windows'] = coerce_bool(
            config.get('start_with_windows'),
            default=DEFAULT_START_WITH_WINDOWS,
        )
    return config


def load_config_file(path: str) -> dict:
    """Load config.yaml, then apply shell-setting defaults for missing keys."""
    config = default_config()
    if path and os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                loaded = yaml.safe_load(handle)
            if isinstance(loaded, dict):
                config.update(loaded)
            elif loaded is not None:
                print(f"Warning: Config at {path} is not a mapping; using defaults")
        except Exception as exc:
            print(f"Warning: Failed to load config: {exc}")
    return apply_app_setting_defaults(config)


def should_start_minimized(config: Optional[dict], argv: Optional[list] = None) -> bool:
    """True when the UI window should stay hidden.

    ``--minimized`` is how the login startup entry launches the app.
    A normal double-click does not pass the flag, so the window is shown
    unless config.yaml itself sets start_minimized.
    """
    args = sys.argv if argv is None else argv
    if any(arg == '--minimized' for arg in args):
        return True
    if not config:
        return False
    return coerce_bool(config.get('start_minimized', False), default=False)
