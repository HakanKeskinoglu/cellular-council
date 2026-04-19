// CCA Dashboard App

const DOM = {
    status: document.getElementById('connection-status'),
    timeline: document.getElementById('event-timeline'),
    cellGrid: document.getElementById('cell-grid'),
    valRound: document.getElementById('val-round'),
    valCells: document.getElementById('val-cells'),
    valMsgs: document.getElementById('val-msgs'),
    councilInfo: document.getElementById('council-info'),
    decisionPanel: document.getElementById('decision-panel'),
};

let state = {
    msgCount: 0,
    cells: new Set(),
    activeSession: null
};

// WebSocket Connection
function connect() {
    // Assuming backend is running on the same host, port 8765
    const wsUrl = `ws://${window.location.hostname}:8765`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        DOM.status.textContent = 'Connected (Live)';
        DOM.status.className = 'status-connected';
    };

    ws.onclose = () => {
        DOM.status.textContent = 'Disconnected (Retrying...)';
        DOM.status.className = 'status-disconnected';
        setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleSynapseEvent(data);
    };
}

function handleSynapseEvent(event) {
    state.msgCount++;
    DOM.valMsgs.textContent = state.msgCount;
    DOM.valRound.textContent = event.round_number || '-';

    // Track cells dynamically based on senders
    if (event.sender_id && !event.sender_id.startsWith('sys-')) {
        if (!state.cells.has(event.sender_id)) {
            state.cells.add(event.sender_id);
            addCellToGrid(event.sender_id, event.payload?.cell_role || 'unknown');
            DOM.valCells.textContent = state.cells.size;
        }
    }

    appendEventToTimeline(event);
    
    // Animate the cell node if it exists
    animateCellActivity(event.sender_id);
    
    // Check if it's the final decision
    if (event.message_type === 'control' && event.payload?.decision) {
        showFinalDecision(event.payload);
    }
}

function addCellToGrid(id, role) {
    const el = document.createElement('div');
    el.className = 'cell-node';
    el.id = `cell-${id}`;
    el.innerHTML = `
        <span class="role">${role.toUpperCase()}</span>
        <span class="id">${id}</span>
    `;
    DOM.cellGrid.appendChild(el);
}

function animateCellActivity(id) {
    const el = document.getElementById(`cell-${id}`);
    if (el) {
        el.classList.add('active');
        setTimeout(() => el.classList.remove('active'), 500);
    }
}

function appendEventToTimeline(event) {
    const el = document.createElement('div');
    el.className = 'event';
    
    const timeStr = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : 'now';
    let preview = '';
    
    // Extract a preview depending on what the message is
    if (event.payload?.analysis) preview = event.payload.analysis.substring(0, 100) + '...';
    else if (event.payload?.decision) preview = 'Consensus reached.';
    else preview = JSON.stringify(event.payload).substring(0, 80) + '...';

    el.innerHTML = `
        <span class="event-time">${timeStr}</span>
        <span class="event-sender">${event.sender_id}</span>
        <span class="event-type type-${event.message_type.toLowerCase()}">${event.message_type}</span>
        <div class="payload-preview">${preview}</div>
    `;
    
    DOM.timeline.prepend(el);
}

function showFinalDecision(payload) {
    DOM.decisionPanel.innerHTML = `
        <div class="decision">${payload.decision}</div>
        <div class="rationale">${payload.rationale}</div>
        <div style="margin-top: 10px; font-size: 0.9em; color: var(--text-muted);">
            Score: ${(payload.consensus_score * 100).toFixed(0)}% | 
            Confidence: ${(payload.overall_confidence * 100).toFixed(0)}%
        </div>
    `;
}

// Start
connect();
