# League of Legends Auto-Accept Helper

A lightweight Windows desktop helper that automatically accepts League of Legends matchmaking ready checks using the League Client Update (LCU) API.

## Features

- **Auto-accepts ready checks** instantly using the official League Client local API
- **Real-time WebSocket connection** for instant response (with HTTP polling fallback)
- **Automatic client detection** via lockfile or running process
- **Handles client restarts** - automatically reconnects when the client restarts
- **Configurable delay** - optionally add a delay before accepting
- **System tray integration** - runs quietly in the background with status indicators
- **Easy to use** - just double-click and go!

## Download

Download the latest version from [Releases](../../releases). Get the `LoLAutoAccept.exe` file.

## Installation & Usage

1. **Download** `LoLAutoAccept.exe` from the Releases page
2. **(Optional)** Place it in a dedicated folder (it will create a `config.yaml` file on first run)
3. **Run** the executable by double-clicking it
4. **Wait** for the League Client to open (or open it after starting the helper)
5. The helper will automatically connect and start accepting ready checks

### System Tray

Once running, you'll see an icon in your system tray (bottom-right of Windows taskbar). Right-click it to:

- Check status
- Toggle auto-accept on/off
- Quit the application

### Configuration

On first run, a `config.yaml` file is created in the same folder as the executable. You can edit it to customize behavior:

```yaml
# Enable or disable auto-accept feature
auto_accept_enabled: true

# Random delay range before accepting (in seconds)
# The actual delay will be randomly chosen between min and max for each ready check
# This helps avoid appearing robotic and gives you time to manually decline if desired
accept_delay_min_seconds: 1
accept_delay_max_seconds: 4

# Legacy config (backward compatible):
# If you prefer a fixed delay, uncomment this line and comment out the min/max above:
# accept_delay_seconds: 2

# Logging level (DEBUG, INFO, WARNING, ERROR)
log_level: INFO
```

**Config Options:**

- `auto_accept_enabled`: Turn auto-accept on/off (default: `true`)
- `accept_delay_min_seconds` / `accept_delay_max_seconds`: Random delay range before accepting (default: 1-4 seconds). Each ready check gets a new random delay in this range.
- `accept_delay_seconds`: (Legacy) Fixed delay before accepting. If present, overrides min/max settings.
- `log_level`: Logging verbosity - `DEBUG`, `INFO`, `WARNING`, or `ERROR` (default: `INFO`)

**Why random delay?**
- Avoids appearing robotic (instant accepts look suspicious)
- Gives you 1-4 seconds to manually decline if you change your mind
- Makes timing less predictable

After editing, restart the helper for changes to take effect.

## Windows SmartScreen Notice

Since this is an unsigned executable, Windows SmartScreen may show a warning when you first run it:

1. Click "More info"
2. Click "Run anyway"

This is normal for any unsigned Windows application. If you're concerned, you can check the source code in this repository and build it yourself (see Development section below).

## How It Works

The helper uses the League Client's built-in local API:

1. **Finds the client** by reading the `lockfile` or detecting the running `LeagueClientUx.exe` process
2. **Authenticates** using the client's local credentials (Basic auth with `riot:<password>`)
3. **Connects via WebSocket** to receive real-time events
4. **Listens for ready check events** (`OnJsonApiEvent_lol-matchmaking_v1_ready-check`)
5. **Accepts automatically** when a ready check is detected and you haven't responded yet

All communication happens locally on your computer (`127.0.0.1`) - nothing is sent over the internet.

## Development

### Prerequisites

- Python 3.9 or higher
- Windows OS (for testing with actual League Client)

### Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd <repo-name>

# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run the application
python main.py
```

### Building

To build the executable yourself:

```bash
# Build with PyInstaller
pyinstaller build.spec

# The executable will be in dist/LoLAutoAccept.exe
```

### Project Structure

```
.
├── lcu/                    # League Client API integration
│   ├── client_finder.py    # Find and authenticate with client
│   ├── api_client.py       # HTTP API wrapper
│   └── websocket_client.py # WebSocket event streaming
├── core/
│   └── event_bus.py        # Event dispatching system
├── features/               # Modular features
│   ├── base_feature.py     # Base feature class
│   └── auto_accept.py      # Auto-accept implementation
├── tests/                  # Unit tests
├── main.py                 # Application entry point
├── config.yaml             # Configuration file
└── build.spec              # PyInstaller build configuration
```

## Troubleshooting

### "Waiting for League Client..."

The helper can't find your League Client. Make sure:

- League of Legends is running
- The client is fully loaded (not just the launcher)
- You have appropriate permissions to read process information

### "Connection failed, retrying..."

The helper found the client but can't connect. Try:

- Restarting the League Client
- Restarting the helper
- Checking if antivirus/firewall is blocking local connections

### Ready checks aren't being accepted

- Check that auto-accept is enabled (right-click system tray icon)
- Check the console output for errors
- Try setting `log_level: DEBUG` in `config.yaml` for more detailed logs

## Disclaimer

⚠️ **Important**: This tool uses the League Client's local API, which is not officially documented or supported by Riot Games. Use at your own risk.

- This tool does **not** modify game files or memory
- This tool does **not** provide any competitive advantage
- This tool only automates clicking the "Accept" button during matchmaking
- Riot Games may change their API at any time, which could break this tool

The developers are not responsible for any consequences of using this tool, including but not limited to account restrictions or bans.

## License

MIT License - see LICENSE file for details

---

# 簡介 (Traditional Chinese)

League of Legends 自動接受對戰工具，使用英雄聯盟客戶端的本地 API 自動接受配對準備檢查。

## 主要功能

- **自動接受準備檢查** - 使用官方客戶端本地 API 即時回應
- **即時 WebSocket 連接** - 無延遲響應
- **自動偵測客戶端** - 透過 lockfile 或執行中的程序
- **自動重新連接** - 當客戶端重新啟動時自動重連
- **可設定延遲** - 可選擇延遲接受時間
- **系統托盤圖示** - 在背景安靜執行並顯示狀態

## 下載與使用

1. 從 [Releases](../../releases) 下載 `LoLAutoAccept.exe`
2. 雙擊執行檔案
3. 開啟英雄聯盟客戶端
4. 工具會自動連接並開始接受配對

## 配置檔案

首次執行會自動建立 `config.yaml` 設定檔，可編輯自訂行為：

- `auto_accept_enabled`: 啟用/停用自動接受功能
- `accept_delay_seconds`: 延遲接受秒數（0 表示立即）
- `log_level`: 記錄等級（DEBUG, INFO, WARNING, ERROR）

## Windows SmartScreen 提示

由於這是未簽署的執行檔，Windows SmartScreen 可能會顯示警告：

1. 點擊「更多資訊」
2. 點擊「仍要執行」

這對任何未簽署的 Windows 應用程式都是正常的。如有疑慮，您可以檢查本儲存庫的原始碼並自行編譯。

## 免責聲明

⚠️ **重要**：本工具使用英雄聯盟客戶端的本地 API，這不是 Riot Games 官方支援的功能。使用風險自負。

- 本工具**不會**修改遊戲檔案或記憶體
- 本工具**不會**提供任何競技優勢
- 本工具僅自動化配對時點擊「接受」按鈕的動作
- Riot Games 可能隨時變更其 API，導致本工具無法使用

開發者不對使用本工具的任何後果負責，包括但不限於帳號限制或封禁。
