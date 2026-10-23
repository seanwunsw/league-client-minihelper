LoL Auto-Accept Helper
=======================

Thank you for downloading LoL Auto-Accept Helper v0.3.0!

QUICK START
-----------
1. Extract all files from this ZIP to a folder
2. Double-click LoLAutoAccept.exe to run
3. A config.yaml file will be created on first run
4. The helper will automatically connect when League Client is open

REQUIREMENTS
------------
- Windows 10/11
- Microsoft Edge WebView2 Runtime (pre-installed on most systems)
  If missing, you'll be prompted to download it on first run

FEATURES
--------
AUTO-ACCEPT (v0.2.0+)
- Automatically accepts League of Legends matchmaking ready checks
- Configurable random delays (1-4s default)
- Real-time WebSocket connection with HTTP polling fallback

CHAMPION SELECT (v0.3.0+)
- Auto-ban: Configure up to 3 ban champions per role with priority fallback
- Auto-pick/hover: Configure up to 3 pick champions per role with priority fallback
- Per-role preferences: Different settings for Top, Jungle, Mid, Bot, Support, Default
- Smart filtering: Skips banned/picked champions and teammate intents
- Hover or Lock mode: Choose whether to just hover or auto-lock picks

⚠️ WARNING: Auto-ban/pick features may violate Riot's Terms of Service.
   Use at your own risk. Developers are not responsible for any consequences.

UI & GENERAL
- Desktop UI with real-time status and settings
- System tray integration - runs quietly in background
- Live log view - monitor actions in real-time
- Accept history tracking

CHAMPION SELECT SETUP
---------------------
1. Open the UI and scroll to "Champion Select" section
2. Enable auto-ban and/or auto-pick using toggles
3. Select pick mode: "Hover" (safer) or "Lock" (auto-locks)
4. Click a role tab (Default, Top, Jungle, Mid, Bot, Sup)
5. Choose champions from dropdowns for each priority (1st, 2nd, 3rd)
   - Bans: Champions you want to ban
   - Picks: Champions you want to pick/hover
6. Repeat for each role you play

The app automatically:
- Uses correct preferences based on your assigned position
- Falls back to next priority if champion unavailable
- Skips teammate hover/intent champions when banning
- Uses "Default" preferences for blind pick

CONFIGURATION
-------------
Edit config.yaml in the same folder as the exe to customize:
- Enable/disable auto-accept, auto-ban, auto-pick
- Adjust delay ranges (min/max seconds)
- Set pick mode (hover/lock)
- Configure per-role champion preferences (easier via UI)
- Change log level
- Start minimized to tray
- close_action: exit (default) or tray
- start_with_windows: true/false (default false; packaged exe only)

SETTINGS (gear icon)
--------------------
- When closing the window: Exit app (default) or Minimise to tray
- Start with Windows (minimised to tray), off by default

The window X button exits the app unless you choose Minimise to tray.
The minimise button still minimises. Tray menu Quit still exits.

START WITH WINDOWS
------------------
Off by default. Turn it on in Settings, or set start_with_windows: true.

This build does not request administrator rights (build.spec does not set
uac_admin, and there is no requireAdministrator manifest). Windows starts
it at logon with the current-user Run key:

  HKCU\Software\Microsoft\Windows\CurrentVersion\Run
  Name:  LoLAutoAccept
  Value: "<path-to-this-exe>" --minimized

--minimized starts the app in the tray. Double-clicking the exe yourself
still opens the window.

If you move the exe, the next launch updates the registered path while the
setting is on. Turning the setting off removes the Run value.

A Run key cannot elevate silently. A future build that requires
administrator rights must set REQUIRES_ADMIN_ELEVATION = True in
core/windows_startup.py so startup is a Task Scheduler logon task with
highest privileges (schtasks /RL HIGHEST) instead of the Run key.

Running from source cannot register startup; the checkbox is disabled.

SYSTEM TRAY
-----------
- Close window (X) → exits the app (default). Settings can change this to hide-to-tray
- Minimise button → minimises the window, app keeps running
- Right-click tray icon → Open / Toggle / Quit
- Tray-only mode uses ~30-50 MB RAM
- With UI open: ~80-120 MB RAM (WebView2)

GETTING HELP
------------
For issues, updates, and documentation visit:
https://github.com/seanwunsw/league-client-minihelper

DISCLAIMER
----------
⚠️ This tool uses the League Client's local API, which is not officially
   supported by Riot Games. Use at your own risk.

- Does NOT modify game files or memory
- Auto-accept only automates clicking "Accept" button
- Auto-ban/pick features may be considered automation of gameplay actions
- Could potentially violate Riot's Terms of Service
- Developers not responsible for account restrictions or bans

LICENSE
-------
This software is provided as-is. See the GitHub repository for license details.
