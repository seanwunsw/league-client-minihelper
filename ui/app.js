// UI State Management
let state = {
    connection_state: 'disconnected',
    gameflow_phase: 'None',
    features: []
};

let logs = [];
const MAX_LOGS = 100;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Setup event listeners
    document.getElementById('auto-accept-toggle').addEventListener('change', (e) => {
        window.pywebview.api.toggle_feature('Auto-Accept');
    });
    
    document.getElementById('delay-min').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Auto-Accept', 'accept_delay_min_seconds', e.target.value);
    });
    
    document.getElementById('delay-max').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Auto-Accept', 'accept_delay_max_seconds', e.target.value);
    });
    
    document.getElementById('clear-log').addEventListener('click', () => {
        logs = [];
        renderLogs();
    });
    
    // Start polling for state updates
    setInterval(updateState, 1000);
    updateState();
});

// Update state from backend
function updateState() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    window.pywebview.api.get_state().then(newState => {
        state = newState;
        render();
    }).catch(err => {
        addLog('error', 'Failed to get state: ' + err);
    });
}

// Render UI
function render() {
    // Connection status
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    
    statusDot.className = 'status-dot ' + state.connection_state;
    statusText.textContent = state.connection_state.charAt(0).toUpperCase() + state.connection_state.slice(1);
    
    // Gameflow phase
    const phaseDisplay = document.getElementById('gameflow-phase');
    phaseDisplay.textContent = state.gameflow_phase === 'None' ? 'No Active Session' : state.gameflow_phase;
    
    // Features
    const autoAccept = state.features.find(f => f.name === 'Auto-Accept');
    if (autoAccept) {
        document.getElementById('auto-accept-toggle').checked = autoAccept.enabled;
        
        if (autoAccept.settings) {
            document.getElementById('delay-min').value = autoAccept.settings.accept_delay_min_seconds || 1;
            document.getElementById('delay-max').value = autoAccept.settings.accept_delay_max_seconds || 4;
        }
        
        // History
        if (autoAccept.status && autoAccept.status.accept_history) {
            renderHistory(autoAccept.status.accept_history);
        }
    }
}

// Render accept history
function renderHistory(history) {
    const historyEl = document.getElementById('accept-history');
    
    if (!history || history.length === 0) {
        historyEl.innerHTML = 'No recent accepts';
        return;
    }
    
    historyEl.innerHTML = history.map(item => {
        const time = new Date(item.timestamp).toLocaleTimeString();
        return `<div class="history-item">${time} - Delay: ${item.delay.toFixed(2)}s</div>`;
    }).reverse().join('');
}

// Add log entry
function addLog(level, message) {
    logs.push({ level, message, timestamp: new Date().toLocaleTimeString() });
    if (logs.length > MAX_LOGS) logs.shift();
    renderLogs();
}

// Render logs
function renderLogs() {
    const logView = document.getElementById('log-view');
    if (logs.length === 0) {
        logView.innerHTML = '<div class="log-entry">No logs yet</div>';
        return;
    }
    
    logView.innerHTML = logs.map(log => 
        `<div class="log-entry ${log.level}">[${log.timestamp}] ${log.message}</div>`
    ).join('');
    
    logView.scrollTop = logView.scrollHeight;
}

// Expose addLog for Python
window.addLog = addLog;
