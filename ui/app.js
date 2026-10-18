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
    
    document.getElementById('auto-pick-toggle').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'auto_pick_enabled', e.target.checked);
    });
    
    document.getElementById('pick-mode').addEventListener('change', (e) => {
        window.pywebview.api.update_setting('Champion Select', 'pick_mode', e.target.value);
    });
    
    // Role tabs
    document.querySelectorAll('.role-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const role = e.target.dataset.role;
            switchRole(role);
        });
    });
    
    // Champion select dropdowns
    document.querySelectorAll('.champ-select').forEach(select => {
        select.addEventListener('change', (e) => {
            saveRolePreferences();
        });
    });
    
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
    
    // Call custom method to get champion list from feature
    const champSelectFeature = state.features.find(f => f.name === 'Champion Select');
    if (champSelectFeature && champSelectFeature.status && champSelectFeature.status.champions) {
        champions = champSelectFeature.status.champions;
        updateChampionDropdowns();
    }
}

// Update all champion dropdowns
function updateChampionDropdowns() {
    document.querySelectorAll('.champ-select').forEach(select => {
        const currentValue = select.value;
        select.innerHTML = '<option value="">None</option>';
        
        champions.forEach(champ => {
            const option = document.createElement('option');
            option.value = champ.id;
            option.textContent = champ.name;
            select.appendChild(option);
        });
        
        // Restore previous selection if valid
        if (currentValue) {
            select.value = currentValue;
        }
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
    
    // Update ban dropdowns
    const banSelects = document.querySelectorAll('.champ-select[data-type="ban"]');
    banSelects.forEach((select, index) => {
        const priority = index + 1;
        if (prefs.bans && prefs.bans[index]) {
            select.value = prefs.bans[index];
        } else {
            select.value = '';
        }
    });
    
    // Update pick dropdowns
    const pickSelects = document.querySelectorAll('.champ-select[data-type="pick"]');
    pickSelects.forEach((select, index) => {
        const priority = index + 1;
        if (prefs.picks && prefs.picks[index]) {
            select.value = prefs.picks[index];
        } else {
            select.value = '';
        }
    });
}

// Save role preferences
function saveRolePreferences() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    const champSelectFeature = state.features.find(f => f.name === 'Champion Select');
    if (!champSelectFeature || !champSelectFeature.settings.role_preferences) return;
    
    const rolePrefs = JSON.parse(JSON.stringify(champSelectFeature.settings.role_preferences));
    
    // Get current role prefs
    const bans = [];
    document.querySelectorAll('.champ-select[data-type="ban"]').forEach(select => {
        const value = parseInt(select.value);
        if (value) bans.push(value);
    });
    
    const picks = [];
    document.querySelectorAll('.champ-select[data-type="pick"]').forEach(select => {
        const value = parseInt(select.value);
        if (value) picks.push(value);
    });
    
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
