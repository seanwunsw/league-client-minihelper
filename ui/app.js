// UI State Management
let state = {
    connection_state: 'disconnected',
    gameflow_phase: 'None',
    features: []
};

let logs = [];
const MAX_LOGS = 100;
let currentRole = 'default';
let champions = [];
let comboboxes = {}; // Store combobox instances by key

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Setup event listeners for auto-accept
    document.getElementById('auto-accept-toggle').addEventListener('change', (e) => {
        window.pywebview.api.toggle_feature('Auto-Accept');
    });
    
    document.getElementById('delay-min').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Auto-Accept', 'accept_delay_min_seconds', e.target.value);
    });
    
    document.getElementById('delay-max').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Auto-Accept', 'accept_delay_max_seconds', e.target.value);
    });
    
    // Setup event listeners for champion select
    document.getElementById('auto-ban-toggle').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'auto_ban_enabled', e.target.checked);
    });
    
    document.getElementById('ban-delay-min').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'ban_delay_min_seconds', e.target.value);
    });
    
    document.getElementById('ban-delay-max').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'ban_delay_max_seconds', e.target.value);
    });
    
    document.getElementById('auto-pick-toggle').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'auto_pick_enabled', e.target.checked);
    });
    
    document.getElementById('pick-mode').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'pick_mode', e.target.value);
    });
    
    document.getElementById('pick-delay-min').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'pick_delay_min_seconds', e.target.value);
    });
    
    document.getElementById('pick-delay-max').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'pick_delay_max_seconds', e.target.value);
    });
    
    // Role tabs
    document.querySelectorAll('.role-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const role = e.target.dataset.role;
            switchRole(role);
        });
    });
    
    // Initialize comboboxes
    initializeComboboxes();
    
    // Clear log button
    document.getElementById('clear-log').addEventListener('click', () => {
        logs = [];
        renderLogs();
    });
    
    // Load initial logs from backend
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_logs().then(backendLogs => {
            logs = backendLogs;
            renderLogs();
        }).catch(() => {});
    }
    
    // Start polling for state updates
    setInterval(updateState, 1000);
    updateState();
});

// Initialize comboboxes
function initializeComboboxes() {
    document.querySelectorAll('.combobox-container').forEach(container => {
        const type = container.dataset.type;
        const priority = container.dataset.priority;
        const key = `${type}-${priority}`;
        
        const combobox = new Combobox(container, {
            placeholder: `${type.charAt(0).toUpperCase() + type.slice(1)} #${priority}`,
            options: [],
            onChange: (value) => {
                saveRolePreferences();
            }
        });
        
        comboboxes[key] = combobox;
    });
}

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
    }
    
    // Champion Select
    const champSelect = state.features.find(f => f.name === 'Champion Select');
    if (champSelect) {
        document.getElementById('auto-ban-toggle').checked = champSelect.settings.auto_ban_enabled || false;
        document.getElementById('auto-pick-toggle').checked = champSelect.settings.auto_pick_enabled || false;
        document.getElementById('pick-mode').value = champSelect.settings.pick_mode || 'hover';
        
        // Delay settings
        document.getElementById('ban-delay-min').value = champSelect.settings.ban_delay_min_seconds || 1;
        document.getElementById('ban-delay-max').value = champSelect.settings.ban_delay_max_seconds || 3;
        document.getElementById('pick-delay-min').value = champSelect.settings.pick_delay_min_seconds || 1;
        document.getElementById('pick-delay-max').value = champSelect.settings.pick_delay_max_seconds || 3;
        
        // Load champion list if not loaded
        if (champions.length === 0) {
            loadChampions();
        }
        
        // Render role preferences
        renderRolePreferences(champSelect.settings.role_preferences);
    }
}

// Load champion list
function loadChampions() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    // Get champions from feature status
    const champSelectFeature = state.features.find(f => f.name === 'Champion Select');
    if (champSelectFeature && champSelectFeature.status && champSelectFeature.status.champions) {
        champions = champSelectFeature.status.champions;
        updateComboboxOptions();
        
        // Also render preferences after champions are loaded
        if (champSelectFeature.settings && champSelectFeature.settings.role_preferences) {
            renderRolePreferences(champSelectFeature.settings.role_preferences);
        }
    }
}

// Update combobox options
function updateComboboxOptions() {
    const options = champions.map(champ => ({
        value: champ.id,
        label: champ.name
    }));
    
    // Update all comboboxes
    Object.values(comboboxes).forEach(combobox => {
        combobox.setOptions(options);
    });
}

// Switch role
function switchRole(role) {
    currentRole = role;
    
    // Update tab styles
    document.querySelectorAll('.role-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.role === role);
    });
    
    // Reload dropdowns for this role
    const champSelectFeature = state.features.find(f => f.name === 'Champion Select');
    if (champSelectFeature && champSelectFeature.settings.role_preferences) {
        renderRolePreferences(champSelectFeature.settings.role_preferences);
    }
}

// Render role preferences
function renderRolePreferences(rolePrefs) {
    if (!rolePrefs || !rolePrefs[currentRole]) return;
    
    const prefs = rolePrefs[currentRole];
    
    // Update ban comboboxes
    for (let i = 1; i <= 3; i++) {
        const key = `ban-${i}`;
        const combobox = comboboxes[key];
        if (combobox) {
            const value = prefs.bans && prefs.bans[i - 1] ? prefs.bans[i - 1] : null;
            combobox.setValue(value);
        }
    }
    
    // Update pick comboboxes
    for (let i = 1; i <= 3; i++) {
        const key = `pick-${i}`;
        const combobox = comboboxes[key];
        if (combobox) {
            const value = prefs.picks && prefs.picks[i - 1] ? prefs.picks[i - 1] : null;
            combobox.setValue(value);
        }
    }
}

// Save role preferences
function saveRolePreferences() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    const champSelectFeature = state.features.find(f => f.name === 'Champion Select');
    if (!champSelectFeature || !champSelectFeature.settings.role_preferences) return;
    
    const rolePrefs = JSON.parse(JSON.stringify(champSelectFeature.settings.role_preferences));
    
    // Get current role prefs from comboboxes
    const bans = [];
    for (let i = 1; i <= 3; i++) {
        const value = comboboxes[`ban-${i}`]?.getValue();
        if (value) bans.push(value);
    }
    
    const picks = [];
    for (let i = 1; i <= 3; i++) {
        const value = comboboxes[`pick-${i}`]?.getValue();
        if (value) picks.push(value);
    }
    
    rolePrefs[currentRole] = { bans, picks };
    
    // Save to backend
    window.pywebview.api.update_setting('Champion Select', 'role_preferences', rolePrefs);
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
