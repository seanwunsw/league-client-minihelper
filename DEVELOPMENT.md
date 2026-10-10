# Development Notes

## Build Summary

This document summarizes the implementation, testing, and release of the League of Legends Auto-Accept Helper.

### Implementation Details

**Architecture:**
- Modular design with clear separation of concerns
- `lcu/` - League Client API integration (client discovery, HTTP API, WebSocket)
- `core/` - Event bus for dispatching LCU events
- `features/` - Pluggable feature system with auto-accept implementation
- `main.py` - Application entry point with GUI/console modes

**Key Features:**
1. **Client Detection:**
   - Primary: Lockfile parsing (`C:\Riot Games\League of Legends\lockfile`)
   - Fallback: Process detection via `psutil` (reads `LeagueClientUx.exe` command-line args)
   - Automatic reconnection on client restart

2. **Event Handling:**
   - WebSocket (preferred): Real-time WAMP-style subscription to `OnJsonApiEvent_lol-matchmaking_v1_ready-check`
   - HTTP fallback: Could be implemented if WebSocket fails (currently WebSocket-only)
   - Event bus pattern for decoupled feature handling

3. **Auto-Accept Logic:**
   - Triggers when: `state == 'InProgress'` AND `playerResponse == 'None'`
   - Built-in cooldown (2s) prevents duplicate accepts
   - Configurable delay before accepting
   - Can be toggled on/off via system tray

4. **User Interface:**
   - System tray icon with right-click menu (Windows)
   - Console fallback mode (Linux or if GUI unavailable)
   - Status indicators: "Waiting for client", "Connected", "Accepted match"

5. **Configuration:**
   - YAML config file (`config.yaml`) created on first run
   - Settings: enable/disable, accept delay, log level
   - Placed next to executable for easy access

### Testing

**Unit Tests: 23 tests, all passing ✓**

1. **Client Finder Tests** (7 tests)
   - Lockfile parsing (valid, invalid, missing)
   - Process detection via psutil mocking
   - Fallback chain verification

2. **Auto-Accept Tests** (8 tests)
   - Feature initialization and enable/disable
   - Accept immediate vs delayed
   - Ignore when disabled, already responded, or wrong state
   - Cooldown prevents duplicate accepts

3. **Event Bus Tests** (6 tests)
   - Subscribe and publish
   - Wildcard handlers
   - Multiple handlers per event
   - Pattern matching
   - Exception handling

**Integration Testing:**
- Cannot be performed in this environment (no Windows, no League Client)
- Manual testing required on Windows 10/11 with League Client installed

### Build Pipeline

**GitHub Actions Workflow:**
- Runs on: `windows-latest`
- Triggers: Push to `v*` tags, manual dispatch
- Steps:
  1. ✓ Checkout code
  2. ✓ Set up Python 3.11
  3. ✓ Install dependencies
  4. ✓ Run unit tests (23 passed)
  5. ✓ Build with PyInstaller
  6. ✓ Verify executable exists
  7. ✓ Upload artifact
  8. ✓ Create GitHub Release with exe attached

**Release v0.1.0:**
- Status: ✓ Published
- Asset: `LoLAutoAccept.exe` (17.6 MB)
- URL: https://github.com/seanwunsw/league-client-minihelper/releases/tag/v0.1.0
- Download: https://github.com/seanwunsw/league-client-minihelper/releases/download/v0.1.0/LoLAutoAccept.exe

### What Was Tested

✓ **Tested (Unit Tests):**
- Lockfile parsing logic
- Process command-line argument extraction
- Ready check decision logic (when to accept)
- Event bus dispatching
- Feature enable/disable
- Cooldown mechanism
- Delayed accept timing
- Configuration loading

✓ **Tested (Build Pipeline):**
- Python dependencies installation on Windows
- Unit tests pass on Windows
- PyInstaller successfully creates one-file executable
- Executable file is created and has expected structure
- GitHub Release creation with asset upload

### What Was NOT Tested (Requires Manual Testing)

⚠️ **Not Tested (No League Client Available):**
- Actual connection to League Client
- WebSocket subscription to LCU events
- HTTP API calls to accept ready check
- SSL certificate handling (self-signed cert)
- System tray icon display and interaction
- Client restart detection and reconnection
- Actual ready check acceptance in game
- Performance under real-world conditions
- Config file creation and persistence
- Executable double-click behavior on Windows
- Windows SmartScreen interaction

### Manual Testing Checklist

For anyone testing this on a real Windows machine with League Client:

1. **Initial Run:**
   - [ ] Double-click `LoLAutoAccept.exe`
   - [ ] Check if `config.yaml` is created
   - [ ] Verify system tray icon appears
   - [ ] Check console for "LoL Helper started" message

2. **Client Detection:**
   - [ ] Start without League Client open - should show "Waiting for League Client..."
   - [ ] Open League Client - should connect and show "Connected to League Client"
   - [ ] Check logs for port/password detection

3. **Auto-Accept:**
   - [ ] Queue for a game
   - [ ] When ready check appears, verify it's auto-accepted
   - [ ] Check console for "Ready check detected, accepting..." and "Successfully accepted ready check"
   - [ ] Test with accept_delay_seconds set to 2-3 seconds

4. **Reconnection:**
   - [ ] Close League Client while helper is running
   - [ ] Reopen League Client
   - [ ] Verify helper reconnects automatically

5. **Configuration:**
   - [ ] Edit `config.yaml` to disable auto-accept
   - [ ] Restart helper
   - [ ] Verify ready checks are NOT auto-accepted
   - [ ] Toggle via system tray menu

6. **Edge Cases:**
   - [ ] Test with non-standard League install directory
   - [ ] Test if helper handles client being slow to start
   - [ ] Test if helper survives client crashes

### Known Limitations

1. **WebSocket Only:** No HTTP polling fallback implemented yet (WebSocket is the primary path)
2. **Windows Only:** Designed and built for Windows, may not work on Linux/Mac
3. **No GUI on Linux:** System tray requires Windows; Linux falls back to console
4. **Unsigned Executable:** Windows SmartScreen will show warnings (expected)
5. **Single Feature:** Only auto-accept implemented; structure supports adding more features

### Future Enhancements

Possible additions (not implemented):
- Auto pick/ban champion selection
- Auto rune page selection
- Match history tracking
- Queue time statistics
- Multi-language UI
- Auto-reconnect after disconnect
- Notification sounds
- Minimize to tray option

### Dependencies

**Runtime:**
- requests (HTTP client for LCU API)
- websocket-client (WebSocket for real-time events)
- PyYAML (configuration file parsing)
- psutil (process detection)
- pystray (system tray icon)
- Pillow (icon image generation)

**Development:**
- pytest (unit testing)
- pytest-cov (code coverage)
- pyinstaller (executable building)

All dependencies are pinned in `requirements.txt` and `requirements-dev.txt`.

### File Structure

```
.
├── .github/
│   └── workflows/
│       └── build-release.yml    # Build and release workflow
├── core/
│   ├── __init__.py
│   └── event_bus.py             # Event dispatching
├── features/
│   ├── __init__.py
│   ├── base_feature.py          # Base feature class
│   └── auto_accept.py           # Auto-accept implementation
├── lcu/
│   ├── __init__.py
│   ├── api_client.py            # HTTP API wrapper
│   ├── client_finder.py         # Client detection
│   └── websocket_client.py      # WebSocket client
├── tests/
│   ├── __init__.py
│   ├── test_auto_accept.py      # Auto-accept tests
│   ├── test_client_finder.py    # Client finder tests
│   └── test_event_bus.py        # Event bus tests
├── .gitignore                   # Git ignore rules
├── build.spec                   # PyInstaller build spec
├── config.yaml                  # Default configuration
├── DEVELOPMENT.md               # This file
├── LICENSE                      # MIT License
├── main.py                      # Application entry point
├── README.md                    # User documentation (EN + ZH)
├── requirements.txt             # Runtime dependencies
└── requirements-dev.txt         # Development dependencies
```

### Commit History

1. **Initial implementation** (b814ef8)
   - Complete application code
   - Unit tests (23 tests)
   - GitHub Actions workflow
   - Bilingual README

2. **Add MIT License** (6f017dd)
   - MIT License file

### Release Process

To create a new release:

```bash
# Make changes and commit
git add .
git commit -m "Your changes"
git push origin main

# Create and push tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z

# GitHub Actions will automatically:
# - Run tests
# - Build Windows executable
# - Create GitHub Release
# - Upload LoLAutoAccept.exe asset
```

### Contact & Support

For issues, feature requests, or questions:
- Open an issue on GitHub: https://github.com/seanwunsw/league-client-minihelper/issues
- Check existing issues for known problems
- Include logs and `config.yaml` when reporting bugs

### Disclaimer

This tool is for educational and convenience purposes only. The LCU API is not officially documented or supported by Riot Games. Use at your own risk.
