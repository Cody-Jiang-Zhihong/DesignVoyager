/**
 * DesignVoyager Dashboard
 * WebSocket client, event rendering, and game replay player.
 */

// ── DOM references ──────────────────────────────────────────────────────────

const logContent    = document.getElementById('log-content');
const startBtn      = document.getElementById('start-btn');
const stopBtn       = document.getElementById('stop-btn');
const gameSelect    = document.getElementById('game-select');
const iterInput     = document.getElementById('iterations-input');
const topkInput     = document.getElementById('topk-input');
const promptInput   = document.getElementById('prompt-input');
const connDot       = document.getElementById('connection-dot');

// Mechanic info
const mechanicInfo  = document.getElementById('mechanic-info');
const mechanicName  = document.getElementById('mechanic-info-name');
const mechanicDesc  = document.getElementById('mechanic-info-desc');

// Tutorial panel
const tutorialEmptyState  = document.getElementById('tutorial-empty-state');
const tutorialContent     = document.getElementById('tutorial-content');
const tutorialMechLabel   = document.getElementById('tutorial-mech-label');
const tutorialPhaseLabel  = document.getElementById('tutorial-phase-label');
const tutorialGrid        = document.getElementById('tutorial-grid');
const tutorialCaption     = document.getElementById('tutorial-caption');
const tutorialNoTrigger   = document.getElementById('tutorial-no-trigger');

// Replay
const boardGrid     = document.getElementById('board-grid');
const cardDisplay   = document.getElementById('card-display');
const replayEmpty   = document.getElementById('replay-empty');
const replayControls= document.getElementById('replay-controls');
const replayTurn    = document.getElementById('replay-turn');
const replayWinner  = document.getElementById('replay-winner');
const replayPlay    = document.getElementById('replay-play');
const replayBack    = document.getElementById('replay-back');
const replayForward = document.getElementById('replay-forward');
const replaySpeed   = document.getElementById('replay-speed');


// ── WebSocket ───────────────────────────────────────────────────────────────

let ws = null;
let running = false;
let activeModelName = 'Model';

function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
        connDot.className = 'dot connected';
        connDot.title = 'Connected';
    };

    ws.onclose = () => {
        connDot.className = 'dot disconnected';
        connDot.title = 'Disconnected';
        running = false;
        updateButtons();
        // Auto-reconnect after 2 seconds
        setTimeout(connect, 2000);
    };

    ws.onerror = () => {
        ws.close();
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleEvent(msg.type, msg.data || {});
    };
}

connect();


// ── Controls ────────────────────────────────────────────────────────────────

startBtn.addEventListener('click', () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    // Clear previous output
    logContent.innerHTML = '';
    replayPlayer.reset();
    tutorialPlayer.reset();

    running = true;
    updateButtons();

    ws.send(JSON.stringify({
        type: 'start_run',
        data: {
            game_name:  gameSelect.value,
            iterations: parseInt(iterInput.value, 10),
            top_k:      parseInt(topkInput.value, 10),
            user_prompt: promptInput.value,
        }
    }));
});

stopBtn.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'stop_run' }));
    }
    running = false;
    updateButtons();
});

function updateButtons() {
    startBtn.classList.toggle('hidden', running);
    stopBtn.classList.toggle('hidden', !running);
    gameSelect.disabled  = running;
    iterInput.disabled   = running;
    topkInput.disabled   = running;
    promptInput.disabled = running;
}


// ── Event handler dispatch ──────────────────────────────────────────────────

function handleEvent(type, data) {
    switch (type) {
        case 'welcome':           renderWelcome(data); break;
        case 'iteration_start':   renderIterationStart(data); break;
        case 'retrieve':          renderRetrieve(data); break;
        case 'propose_start':     renderProposeStart(data); break;
        case 'propose_result':    renderProposeResult(data); break;
        case 'compile_result':    renderCompileResult(data); break;
        case 'playtest_start':    renderPlaytestStart(data); break;
        case 'playtest_result':   renderPlaytestResult(data); break;
        case 'replay_data':       replayPlayer.load(data); tutorialPlayer.load(data); break;
        case 'mechanic_accepted': libraryManager.addLive(data); break;
        case 'verify_result':     renderVerifyResult(data); break;
        case 'revision_start':    renderRevisionStart(data); break;
        case 'revision_result':   renderRevisionResult(data); break;
        case 'curriculum_advance':renderCurriculumAdvance(data); break;
        case 'run_complete':      renderRunComplete(data); break;
        case 'error':             renderError(data); break;
    }
    autoScroll();
}


// ── Render functions ────────────────────────────────────────────────────────

function renderWelcome(d) {
    activeModelName = d.model_name || activeModelName;
    const html = `
        <div class="welcome-banner">
            <h2>DesignVoyager</h2>
            <div class="info-grid">
                <span class="info-label">Game</span>
                <span>${d.game_name} (${d.game_class})</span>
                <span class="info-label">Iterations</span>
                <span>${d.iterations}</span>
                <span class="info-label">Context k</span>
                <span>${d.top_k}</span>
                <span class="info-label">Library</span>
                <span style="color:var(--cyan)">${d.library_size} mechanics</span>
                <span class="info-label">Curriculum</span>
                <span style="color:var(--yellow)">${d.curriculum_progress}</span>
            </div>
        </div>`;
    logContent.insertAdjacentHTML('beforeend', html);
}

function renderIterationStart(d) {
    const html = `
        <div class="iteration-header">
            Iteration ${d.iteration} of ${d.total}
            <span class="stage-tag">${d.stage_name}</span>
        </div>`;
    logContent.insertAdjacentHTML('beforeend', html);
}

function renderRetrieve(d) {
    const names = d.mechanic_names.length
        ? `<span class="mechanic-names">${d.mechanic_names.join(', ')}</span>`
        : 'No library context yet';
    const html = `<div class="context-line">Context from library: ${names}</div>`;
    logContent.insertAdjacentHTML('beforeend', html);
}

function renderProposeStart(d) {
    const html = `
        <div class="status-line" id="propose-spinner">
            <span class="spinner"></span>
            ${activeModelName} is designing a new mechanic (using ${d.context_count} as context)...
        </div>`;
    logContent.insertAdjacentHTML('beforeend', html);
}

function renderProposeResult(d) {
    // Remove spinner
    const spinner = document.getElementById('propose-spinner');
    if (spinner) spinner.remove();

    if (d.failed) {
        const html = `<div class="compile-line fail">Proposal failed.</div>`;
        logContent.insertAdjacentHTML('beforeend', html);
        return;
    }

    const codeId = 'code-' + Date.now();
    const html = `
        <div class="proposal-card">
            <span class="mech-name">${d.mechanic_name}</span>
            <span class="mech-type">${d.mechanic_type}</span>
            <div class="mech-desc">${d.description}</div>
            <span class="code-toggle" onclick="toggleCode('${codeId}')">Show code</span>
            <pre id="${codeId}">${escapeHtml(d.python_code)}</pre>
        </div>`;
    logContent.insertAdjacentHTML('beforeend', html);
}

function renderCompileResult(d) {
    if (d.passed) {
        logContent.insertAdjacentHTML('beforeend',
            `<div class="compile-line pass">Compile check &#10003; passed</div>`);
    } else {
        logContent.insertAdjacentHTML('beforeend',
            `<div class="compile-line fail">Compile check &#10007; failed</div>
             <div class="compile-error">${escapeHtml(d.error || '').slice(0, 120)}</div>`);
    }
}

function renderPlaytestStart(d) {
    logContent.insertAdjacentHTML('beforeend', `
        <div class="status-line" id="playtest-spinner">
            <span class="spinner"></span>
            Playtesting <strong>${d.mechanic_name}</strong>...
        </div>`);
}

function renderPlaytestResult(d) {
    const spinner = document.getElementById('playtest-spinner');
    if (spinner) spinner.remove();

    const s = d.scores;
    const balance = balanceScoreFromScores(s);

    const playGate = s.playability >= 1.0
        ? `<div class="playability-gate pass">Playability gate &#10003; passed</div>`
        : `<div class="playability-gate fail">Playability gate &#10007; failed (${(s.playability * 100).toFixed(0)}%)</div>`;

    const html = `
        <div class="scores-section">
            ${playGate}
            ${scoreBar('Balance', balance)}
            ${scoreBar('Depth', s.depth)}
            <hr class="score-divider">
            ${scoreBar('Aggregate', s.aggregate)}
        </div>`;
    logContent.insertAdjacentHTML('beforeend', html);
}

function renderVerifyResult(d) {
    const decision = d.decision;
    let title, detail;

    if (decision === 'accept') {
        const agg = d.scores && d.scores.aggregate != null
            ? `aggregate score: ${d.scores.aggregate.toFixed(2)}`
            : '';
        title = '&#10003; ACCEPTED';
        detail = agg;
    } else if (decision === 'revise') {
        title = '&rarr; REVISING';
        detail = `Sending feedback to ${activeModelName} for one revision attempt...`;
    } else {
        title = '&#10007; DISCARDED';
        detail = d.feedback || 'Could not produce a working mechanic.';
    }

    logContent.insertAdjacentHTML('beforeend', `
        <div class="verdict-panel ${decision}">
            <div class="verdict-title">${title}</div>
            <div class="verdict-detail">${detail}</div>
        </div>`);
}

function renderRevisionStart(d) {
    logContent.insertAdjacentHTML('beforeend', `
        <div class="status-line" id="revision-spinner">
            <span class="spinner"></span>
            ${activeModelName} is revising <strong>${d.mechanic_name}</strong>...
        </div>`);
}

function renderRevisionResult(d) {
    const spinner = document.getElementById('revision-spinner');
    if (spinner) spinner.remove();

    if (d.failed) {
        logContent.insertAdjacentHTML('beforeend',
            `<div class="compile-line fail">Revision failed.</div>`);
        return;
    }

    const codeId = 'code-' + Date.now();
    logContent.insertAdjacentHTML('beforeend', `
        <div class="proposal-card">
            <span class="mech-name">${d.mechanic_name}</span>
            <span class="mech-type">${d.mechanic_type}</span>
            <div class="mech-desc">${d.description}</div>
            <span class="code-toggle" onclick="toggleCode('${codeId}')">Show code</span>
            <pre id="${codeId}">${escapeHtml(d.python_code)}</pre>
        </div>`);
}

function renderCurriculumAdvance(d) {
    logContent.insertAdjacentHTML('beforeend', `
        <div class="curriculum-advance">
            &#9733; Unlocked ${d.new_stage_name}! ${activeModelName} will now propose more complex mechanics.
        </div>`);
}

function renderRunComplete(d) {
    running = false;
    updateButtons();
    tutorialPlayer._stopLoop();

    const mechList = d.mechanic_names.length
        ? d.mechanic_names.join(', ')
        : 'empty';

    logContent.insertAdjacentHTML('beforeend', `
        <div class="summary-panel">
            <h3>Run Complete</h3>
            <div class="summary-grid">
                <span class="label">Accepted</span>
                <span class="val-green">${d.accepted_count}</span>
                <span class="label">Discarded</span>
                <span class="val-red">${d.discarded_count}</span>
                <span class="label">Library</span>
                <span class="val-cyan">${d.library_size} mechanics</span>
                <span class="label">Mechanics</span>
                <span class="dim">${mechList}</span>
            </div>
        </div>`);
}

function renderError(d) {
    running = false;
    updateButtons();
    logContent.insertAdjacentHTML('beforeend', `
        <div class="verdict-panel discard">
            <div class="verdict-title">Error</div>
            <div class="verdict-detail">${escapeHtml(d.message || 'Unknown error')}</div>
        </div>`);
}


// ── Score bar helper ────────────────────────────────────────────────────────

function scoreBar(label, value) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return `
            <div class="score-row invalid">
                <span class="score-label">${label}</span>
                <div class="score-bar-container">
                    <div class="score-bar-fill invalid" style="width:0%"></div>
                </div>
                <span class="score-value">N/A</span>
            </div>`;
    }
    const pct = Math.max(0, Math.min(100, value * 100));
    const color = value >= 0.75 ? 'green' : (value >= 0.5 ? 'yellow' : 'red');
    return `
        <div class="score-row">
            <span class="score-label">${label}</span>
            <div class="score-bar-container">
                <div class="score-bar-fill ${color}" style="width:${pct}%"></div>
            </div>
            <span class="score-value">${value.toFixed(2)}</span>
        </div>`;
}


// ── Helpers ──────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function toggleCode(id) {
    const pre = document.getElementById(id);
    if (pre) pre.classList.toggle('open');
}

function autoScroll() {
    const log = document.getElementById('pipeline-log');
    log.scrollTop = log.scrollHeight;
}


// ── Mechanic Trigger Detection ──────────────────────────────────────────────
//
// Shared by both the live tutorial panel and the library card animations.
// Scans a replay move list for the first turn where the mechanic visibly fired.
// Returns a trigger object or null if no effect was detectable.
//
// Three passes in priority order:
//   1. Board cell changes   (state_before_mechanics vs state_after)
//   2. Extra turn granted   (same player appears twice in a row)
//   3. custom_state changed (consecutive turns differ on custom_state field)

function detectMechanicTrigger(moves) {
    if (!moves || moves.length === 0) return null;

    // Pass 1: cells changed by mechanic
    for (const move of moves) {
        if (!move.state_before_mechanics) continue;
        const before = move.state_before_mechanics.board;
        const after  = move.state_after.board;
        if (!before || !after) continue;
        const changes = [];
        for (let r = 0; r < before.length; r++) {
            for (let c = 0; c < before[r].length; c++) {
                if (before[r][c] !== after[r][c]) changes.push(`${r},${c}`);
            }
        }
        if (changes.length > 0) {
            return { type: 'board', before, after,
                     changes: new Set(changes), move: move.move };
        }
    }

    // Pass 2: extra turn — same player moves twice in a row
    for (let i = 0; i < moves.length - 1; i++) {
        if (moves[i].player === moves[i + 1].player) {
            return {
                type:      'extra_turn',
                before:    moves[i].state_after.board,
                after:     moves[i + 1].state_after.board,
                changes:   new Set(),
                move:      moves[i].move,
                bonusMove: moves[i + 1].move,
            };
        }
    }

    // Pass 3: custom_state changed between consecutive turns
    for (let i = 1; i < moves.length; i++) {
        const prev = moves[i - 1].state_after;
        const curr = moves[i].state_after;
        if (JSON.stringify(prev.custom_state) !== JSON.stringify(curr.custom_state)) {
            return {
                type:    'custom_state',
                before:  prev.board,
                after:   curr.board,
                changes: new Set(),
                move:    moves[i].move,
            };
        }
    }

    return null;
}


// ── Game Replay Player ──────────────────────────────────────────────────────

const replayPlayer = {
    data: null,
    currentStep: -1,   // -1 = initial state, 0..N-1 = after each move
    interval: null,
    playing: false,

    reset() {
        this.stop();
        this.data = null;
        this.currentStep = -1;
        boardGrid.classList.add('hidden');
        cardDisplay.classList.add('hidden');
        replayEmpty.classList.remove('hidden');
        replayControls.classList.add('hidden');
        mechanicInfo.classList.add('hidden');
    },

    load(d) {
        this.stop();
        this.data = d;
        this.currentStep = -1;

        replayEmpty.classList.add('hidden');
        replayControls.classList.remove('hidden');

        // Show mechanic info if present
        if (d.mechanic_name) {
            mechanicName.textContent = d.mechanic_name;
            mechanicDesc.textContent = d.mechanic_description || '';
            mechanicInfo.classList.remove('hidden');
        } else {
            mechanicInfo.classList.add('hidden');
        }

        if (d.game_type === 'board') {
            boardGrid.classList.remove('hidden');
            cardDisplay.classList.add('hidden');
            this._initBoardGrid();
        } else {
            cardDisplay.classList.remove('hidden');
            boardGrid.classList.add('hidden');
        }

        this._renderCurrentState();
        this._updateInfo();

        // Auto-play
        this.play();
    },

    play() {
        if (!this.data || this.playing) return;
        this.playing = true;
        replayPlay.innerHTML = '&#9646;&#9646;';  // pause icon

        const speed = parseInt(replaySpeed.value, 10);
        this.interval = setInterval(() => {
            if (this.currentStep < this.data.moves.length - 1) {
                this.currentStep++;
                this._renderCurrentState();
                this._updateInfo();
            } else {
                this.stop();
            }
        }, speed);
    },

    stop() {
        this.playing = false;
        replayPlay.innerHTML = '&#9654;';  // play icon
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    },

    stepForward() {
        if (!this.data) return;
        this.stop();
        if (this.currentStep < this.data.moves.length - 1) {
            this.currentStep++;
            this._renderCurrentState();
            this._updateInfo();
        }
    },

    stepBack() {
        if (!this.data) return;
        this.stop();
        if (this.currentStep >= 0) {
            this.currentStep--;
            this._renderCurrentState();
            this._updateInfo();
        }
    },

    _getCurrentState() {
        if (this.currentStep < 0) return this.data.initial_state;
        return this.data.moves[this.currentStep].state_after;
    },

    _getLastMove() {
        if (this.currentStep < 0) return null;
        return this.data.moves[this.currentStep];
    },

    _updateInfo() {
        const total = this.data.moves.length;
        const current = this.currentStep + 1;
        replayTurn.textContent = `Turn ${current} / ${total}`;

        if (this.currentStep === total - 1 && this.data.winner != null) {
            replayWinner.textContent = `Player ${this.data.winner} wins`;
            replayWinner.style.color = this.data.winner === 1 ? 'var(--cyan)' : 'var(--red)';
        } else if (this.currentStep === total - 1 && this.data.winner == null) {
            replayWinner.textContent = 'Draw';
            replayWinner.style.color = 'var(--text-dim)';
        } else {
            replayWinner.textContent = '';
        }
    },

    _renderCurrentState() {
        const state = this._getCurrentState();
        const lastMove = this._getLastMove();

        if (this.data.game_type === 'board') {
            this._renderBoardState(state, lastMove);
        } else {
            this._renderCardState(state, lastMove);
        }
    },

    // ── Mechanic diff ──────────────────────────────────────────────────────

    _getMechanicBoardChanges() {
        /**
         * Compare state_before_mechanics vs state_after for the current move.
         * Returns a Set of "r,c" strings for board cells the mechanic changed.
         */
        const changes = new Set();
        const moveData = this._getLastMove();
        if (!moveData || !moveData.state_before_mechanics) return changes;

        const before = moveData.state_before_mechanics.board;
        const after  = moveData.state_after.board;
        if (!before || !after) return changes;

        for (let r = 0; r < before.length; r++) {
            for (let c = 0; c < before[r].length; c++) {
                if (before[r][c] !== after[r][c]) {
                    changes.add(`${r},${c}`);
                }
            }
        }
        return changes;
    },

    _getMechanicScoreChanges() {
        /**
         * Compare scores in state_before_mechanics vs state_after.
         * Returns a Set of player numbers whose score the mechanic changed.
         */
        const changes = new Set();
        const moveData = this._getLastMove();
        if (!moveData || !moveData.state_before_mechanics) return changes;

        const beforeScores = moveData.state_before_mechanics.scores;
        const afterScores  = moveData.state_after.scores;
        if (!beforeScores || !afterScores) return changes;

        for (const p of [1, 2]) {
            const bKey = beforeScores[p] != null ? p : String(p);
            const aKey = afterScores[p] != null ? p : String(p);
            if (beforeScores[bKey] !== afterScores[aKey]) {
                changes.add(p);
            }
        }
        return changes;
    },

    // ── Board rendering ─────────────────────────────────────────────────────

    _initBoardGrid() {
        boardGrid.innerHTML = '';
        for (let r = 0; r < 6; r++) {
            for (let c = 0; c < 6; c++) {
                const cell = document.createElement('div');
                cell.className = 'board-cell';
                cell.dataset.row = r;
                cell.dataset.col = c;
                boardGrid.appendChild(cell);
            }
        }
    },

    _renderBoardState(state, lastMove) {
        const board = state.board;
        if (!board) return;

        // Parse the last move to highlight the placed cell
        let highlightR = -1, highlightC = -1;
        if (lastMove && typeof lastMove.move === 'string') {
            const parts = lastMove.move.split(' ');
            if (parts.length === 2) {
                const coords = parts[1].split(',');
                highlightR = parseInt(coords[0], 10);
                highlightC = parseInt(coords[1], 10);
            }
        }

        // Get cells changed by the mechanic (purple highlight)
        const mechanicChanges = this._getMechanicBoardChanges();

        const cells = boardGrid.querySelectorAll('.board-cell');
        let idx = 0;
        for (let r = 0; r < board.length; r++) {
            for (let c = 0; c < board[r].length; c++) {
                const cell = cells[idx++];
                if (!cell) continue;
                const val = board[r][c];
                cell.textContent = val === '_' ? '' : val;
                cell.className = 'board-cell';
                if (val === 'X') cell.classList.add('x');
                if (val === 'O') cell.classList.add('o');
                if (r === highlightR && c === highlightC) {
                    cell.classList.add('highlight');
                }
                if (mechanicChanges.has(`${r},${c}`)) {
                    cell.classList.add('mechanic-changed');
                }
            }
        }
    },

    // ── Card rendering ──────────────────────────────────────────────────────

    _renderCardState(state, lastMove) {
        const hands  = state.hands;
        const scores = state.scores;
        if (!hands || !scores) return;

        const lastPlayed = state.last_played;
        const lastPlayer = lastMove ? lastMove.player : null;

        // Get scores changed by the mechanic (purple highlight)
        const mechanicScoreChanges = this._getMechanicScoreChanges();

        for (const p of [1, 2]) {
            const handEl = document.querySelector(`#card-hand-${p} .hand-cards`);
            const scoreContainer = document.querySelector(`#card-hand-${p} .hand-score`);
            const scoreEl = scoreContainer.querySelector('span');

            handEl.innerHTML = '';
            const hand = hands[p] || hands[String(p)] || [];
            hand.forEach(val => {
                const chip = document.createElement('span');
                chip.className = 'card-chip';
                chip.textContent = val;
                handEl.appendChild(chip);
            });

            scoreEl.textContent = scores[p] || scores[String(p)] || 0;

            // Highlight score if the mechanic changed it
            if (mechanicScoreChanges.has(p)) {
                scoreContainer.classList.add('mechanic-changed');
            } else {
                scoreContainer.classList.remove('mechanic-changed');
            }
        }
    }
};

// ── Mechanic Tutorial Player ────────────────────────────────────────────────
//
// Finds the first turn in the replay where the mechanic actually fired
// (state_before_mechanics differs from state_after) and loops a
// BEFORE → AFTER animation in the tutorial panel.

const tutorialPlayer = {
    beforeBoard:  null,
    afterBoard:   null,
    changedCells: new Set(),   // Set of "r,c" strings affected by the mechanic
    placedCell:   null,        // "r,c" of the piece that triggered the mechanic
    phase:        'before',
    interval:     null,
    _generation:  0,           // incremented on every stop; callbacks bail if theirs is stale

    // How long to hold each phase before flipping (ms)
    BEFORE_MS: 2000,
    AFTER_MS:  2800,

    _stopLoop() {
        this._generation++;            // invalidate every in-flight callback
        clearTimeout(this.interval);
        this.interval = null;
        if (tutorialGrid) tutorialGrid.classList.remove('fading');
    },

    reset() {
        this._stopLoop();
        this.interval    = null;
        this.beforeBoard = null;
        this.afterBoard  = null;
        this.changedCells = new Set();
        this.placedCell  = null;
        this.triggerType  = 'board';
        this.bonusMove    = null;
        this.phase        = 'before';
        tutorialContent.classList.add('hidden');
        tutorialNoTrigger.classList.add('hidden');
        tutorialEmptyState.classList.remove('hidden');
        tutorialEmptyState.querySelector('span').textContent =
            'Waiting for a mechanic to compile...';
    },

    load(d) {
        // Card game: show a placeholder for now (board grid only)
        if (d.game_type !== 'board') {
            tutorialEmptyState.classList.remove('hidden');
            tutorialEmptyState.querySelector('span').textContent =
                'Tutorial view is available for the board game.';
            tutorialContent.classList.add('hidden');
            return;
        }

        // Scan the replay for the first turn where the mechanic had a visible effect.
        // Three passes in priority order:
        //
        //  Pass 1 — board cells changed (e.g. flip, capture)
        //           Compare state_before_mechanics vs state_after for each move.
        //
        //  Pass 2 — extra turn granted (e.g. bonus turn on center placement)
        //           extra_turn is always reset to False in get_state(), so it's
        //           invisible in state diffs. The reliable signal is in the replay
        //           itself: the same player appears twice in a row in the move list.
        //
        //  Pass 3 — custom_state changed between consecutive turns
        //           Compare state_after[i-1].custom_state vs state_after[i].custom_state.

        const trigger = detectMechanicTrigger(d.moves);

        // Show mechanic name + description header
        tutorialEmptyState.classList.add('hidden');
        tutorialContent.classList.remove('hidden');
        tutorialMechLabel.textContent = d.mechanic_name || '';
        tutorialCaption.textContent   = d.mechanic_description || '';

        if (!trigger) {
            // Mechanic compiled and ran but never visibly changed the board.
            // Stop any loop that was running for the previous mechanic.
            this._stopLoop();
            tutorialPhaseLabel.classList.add('hidden');
            tutorialNoTrigger.classList.remove('hidden');
            const triggerCount = d.trigger_count || 0;
            const stateChangeCount = d.state_changed_by_mechanic_count || 0;
            if (triggerCount > 0 || stateChangeCount > 0) {
                tutorialNoTrigger.textContent =
                    `No clear visual before/after was found in the selected replay, ` +
                    `but the mechanic triggered ${triggerCount} time(s)` +
                    (stateChangeCount > 0
                        ? ` and changed game state ${stateChangeCount} time(s).`
                        : '.');
            } else {
                tutorialNoTrigger.textContent =
                    'No visible mechanic effect was found in the selected replay, and no internal trigger was recorded.';
            }
            tutorialGrid.innerHTML = '';
            return;
        }

        tutorialPhaseLabel.classList.remove('hidden');

        tutorialNoTrigger.classList.add('hidden');

        this.beforeBoard  = trigger.before;
        this.afterBoard   = trigger.after;
        this.changedCells = new Set(trigger.changes);
        this.triggerType  = trigger.type;   // 'board' | 'extra_turn' | 'custom_state'
        this.bonusMove    = trigger.bonusMove || null;  // second placement for extra_turn

        // Parse the placed cell from the move string (e.g. "X 2,3" → "2,3")
        this.placedCell = this._parseMovePos(trigger.move);

        this._initGrid();
        this._stopLoop();         // cancel any loop still running from the last mechanic
        this.phase = 'before';
        this._renderPhase();
        this._startLoop();
    },

    // Parse a board-game move string like "X 2,3" → "2,3", or null if unparseable
    _parseMovePos(moveStr) {
        if (typeof moveStr !== 'string') return null;
        const parts = moveStr.split(' ');
        if (parts.length === 2) return parts[1];
        return null;
    },

    _initGrid() {
        tutorialGrid.innerHTML = '';
        for (let r = 0; r < 6; r++) {
            for (let c = 0; c < 6; c++) {
                const cell = document.createElement('div');
                cell.className    = 'tutorial-cell';
                cell.dataset.pos  = `${r},${c}`;
                tutorialGrid.appendChild(cell);
            }
        }
    },

    _renderPhase() {
        const board = this.phase === 'before' ? this.beforeBoard : this.afterBoard;

        // Update phase label — non-board triggers get a more descriptive "after" label
        if (this.phase === 'before') {
            tutorialPhaseLabel.textContent = 'BEFORE';
            tutorialPhaseLabel.className   = 'tutorial-phase-label phase-before';
        } else {
            const afterLabel = {
                board:        'AFTER MECHANIC',
                extra_turn:   'EXTRA TURN GRANTED',
                custom_state: 'STATE UPDATED',
            }[this.triggerType] || 'AFTER MECHANIC';
            tutorialPhaseLabel.textContent = afterLabel;
            tutorialPhaseLabel.className   = 'tutorial-phase-label phase-after';
        }

        const cells = tutorialGrid.querySelectorAll('.tutorial-cell');
        let idx = 0;
        for (let r = 0; r < board.length; r++) {
            for (let c = 0; c < board[r].length; c++) {
                const cell = cells[idx++];
                if (!cell) continue;
                const val = board[r][c];
                const pos = `${r},${c}`;

                cell.textContent = val === '_' ? '' : val;
                cell.className   = 'tutorial-cell';
                if (val === 'X') cell.classList.add('x');
                if (val === 'O') cell.classList.add('o');

                // "Before" phase: highlight the piece that was just placed
                if (this.phase === 'before' && pos === this.placedCell) {
                    cell.classList.add('highlight');
                }

                if (this.phase === 'after') {
                    if (this.triggerType === 'board' && this.changedCells.has(pos)) {
                        // Board-changing mechanic: highlight the affected cells
                        cell.classList.add('mechanic-changed');
                    } else if (this.triggerType === 'extra_turn' && pos === this._parseMovePos(this.bonusMove)) {
                        // Extra-turn mechanic: pulse the bonus placement
                        cell.classList.add('mechanic-changed');
                    } else if (this.triggerType === 'custom_state' && pos === this.placedCell) {
                        // Custom-state mechanic: pulse the triggering piece
                        cell.classList.add('mechanic-changed');
                    }
                }
            }
        }
    },

    _startLoop() {
        const self = this;
        const gen = ++self._generation;   // capture this loop's generation number

        const schedule = () => {
            if (gen !== self._generation) return;   // a newer loop has taken over
            const holdMs = self.phase === 'before' ? self.BEFORE_MS : self.AFTER_MS;
            self.interval = setTimeout(() => {
                if (gen !== self._generation) return;
                // Fade out
                tutorialGrid.classList.add('fading');
                setTimeout(() => {
                    if (gen !== self._generation) {
                        // Stopped mid-fade — restore visibility and exit
                        tutorialGrid.classList.remove('fading');
                        return;
                    }
                    // Flip phase and render
                    self.phase = self.phase === 'before' ? 'after' : 'before';
                    self._renderPhase();
                    // Fade back in
                    tutorialGrid.classList.remove('fading');
                    // Schedule next flip
                    schedule();
                }, 260);   // matches the CSS transition duration
            }, holdMs);
        };
        schedule();
    },
};


// ── Library Manager ─────────────────────────────────────────────────────────
//
// Manages the Library tab: fetches saved cards on load, adds new ones live
// when a mechanic_accepted event arrives, handles card expand/collapse, and
// runs a per-card nano tutorial animation when a card is expanded.

const libraryManager = {
    cards: [],
    expandedId: null,
    _animations: {},

    get _analyticsEl() { return document.getElementById('library-analytics'); },
    get _emptyEl() { return document.getElementById('library-empty'); },
    get _gridEl() { return document.getElementById('library-grid'); },

    async init() {
        try {
            const res = await fetch('/api/library-cards');
            if (!res.ok) return;
            const cards = await res.json();
            cards.forEach(card => this._addCard(card, false));
            this._renderAll();
        } catch (e) { /* server may not be running yet */ }
    },

    addLive(card) {
        this._addCard(card, true);
    },

    _addCard(card, rerender = true) {
        this.cards.push(this._enrichCard(card));
        this.cards.sort((a, b) => {
            const diff = (b.scores?.aggregate ?? 0) - (a.scores?.aggregate ?? 0);
            return diff !== 0 ? diff : (a.mechanic_name || '').localeCompare(b.mechanic_name || '');
        });
        if (rerender) this._renderAll();
    },

    _renderAll() {
        this._stopAllAnimations();
        this.expandedId = null;
        this._gridEl.innerHTML = '';

        if (this.cards.length === 0) {
            this._emptyEl.classList.remove('hidden');
            this._analyticsEl.innerHTML = '';
            return;
        }

        this._emptyEl.classList.add('hidden');
        this._renderAnalytics();
        this.cards.forEach((card, index) => this._renderCard(index, card));
    },

    _renderAnalytics() {
        this._renderRobustnessAnalytics();
        return;
    },

    _renderRobustnessAnalytics() {
        const analytics = this._buildAnalytics();
        this._analyticsEl.innerHTML = buildLibraryAnalyticsHtml(analytics);
        return;
        const familyCards = analytics.familyStats.map(stat => `
            <div class="family-row-card ${stat.robustRate >= 0.5 ? 'strong' : ''}">
                <div class="family-row-top">
                    <div class="family-row-title">
                        <span class="family-icon">${familyIcon(stat.label)}</span>
                        <span>${escapeHtml(stat.label)}</span>
                    </div>
                    <div class="family-row-count">${stat.count}</div>
                </div>
                <div class="family-row-bars">
                    ${miniMetricBar('B', stat.avgBalance, 'green')}
                    ${miniMetricBar('D', stat.avgDepth, 'blue')}
                    ${miniMetricBar('A', stat.avgAggregate, 'purple')}
                    ${miniMetricBar('R', stat.robustRate, 'robust')}
                </div>
                <div class="family-row-foot">
                    <span>${stat.robustCount} robust</span>
                    <span>${stat.contextCount} context</span>
                    <span>${stat.nonRobustCount} fail</span>
                </div>
            </div>
        `).join('');

        const patternCards = analytics.patternStats.map(stat => `
            <div class="pattern-chip">
                <span class="pattern-icon">${patternIcon(stat.label)}</span>
                <span>${escapeHtml(stat.label)}</span>
                <span class="pattern-chip-meta">${stat.count}</span>
            </div>
        `).join('');

        const bestCards = analytics.bestOverall.map(card => `
            <div class="analytics-best-row">
                <div>
                    <div class="analytics-best-name">${escapeHtml(card.mechanic_name)}</div>
                    <div class="analytics-best-sub">${escapeHtml(card.meta.effectFamily)} · ${escapeHtml(robustnessTitle(card.robustnessLabel))}</div>
                </div>
                <div class="analytics-best-right">
                    <span class="robustness-pill ${robustnessClass(card.robustnessLabel)}">${escapeHtml(robustnessTitle(card.robustnessLabel))}</span>
                    <span class="analytics-best-meta">${card.scores.aggregate.toFixed(2)}</span>
                </div>
            </div>
        `).join('');

        const insightChips = analytics.insights.map(insight => `
            <div class="insight-chip">
                <span class="insight-icon">${insight.icon}</span>
                <span class="insight-text">${escapeHtml(insight.text)}</span>
            </div>
        `).join('');

        this._analyticsEl.innerHTML = `
            <section class="library-analytics-panel">
                <div class="analytics-overview-grid">
                    <div class="analytics-stat-card">
                        <div class="analytics-stat-icon">◎</div>
                        <div class="analytics-stat-label">Accepted</div>
                        <div class="analytics-stat-value">${analytics.overview.total}</div>
                        <div class="analytics-stat-sub">${analytics.overview.boardCount} board · ${analytics.overview.cardCount} card</div>
                    </div>
                    <div class="analytics-stat-card">
                        <div class="analytics-stat-icon">◔</div>
                        <div class="analytics-stat-label">Avg Aggregate</div>
                        <div class="analytics-stat-value">${analytics.overview.avgAggregate.toFixed(2)}</div>
                        <div class="analytics-stat-sub">library mean</div>
                    </div>
                    <div class="analytics-stat-card">
                        <div class="analytics-stat-icon">▲</div>
                        <div class="analytics-stat-label">High Depth</div>
                        <div class="analytics-stat-value">${analytics.overview.highDepthCount}</div>
                        <div class="analytics-stat-sub">depth ≥ 0.80</div>
                    </div>
                    <div class="analytics-stat-card">
                        <div class="analytics-stat-icon">◌</div>
                        <div class="analytics-stat-label">Most Fair</div>
                        <div class="analytics-stat-value small">${escapeHtml(analytics.overview.mostFairFamily)}</div>
                        <div class="analytics-stat-sub">best balance family</div>
                    </div>
                </div>

                <div class="analytics-sections">
                    <section class="analytics-section">
                        <div class="analytics-section-header">
                            <h3>Top Families</h3>
                            <span>B / D / A</span>
                        </div>
                        <div class="analytics-type-grid">${familyCards}</div>
                    </section>

                    <section class="analytics-section analytics-side-section">
                        <div class="analytics-section-header">
                            <h3>Top Mechanics</h3>
                            <span>aggregate rank</span>
                        </div>
                        <div class="analytics-best-list">${bestCards}</div>
                        <div class="analytics-section-header secondary">
                            <h3>Patterns</h3>
                            <span>common motifs</span>
                        </div>
                        <div class="analytics-mini-grid">${patternCards}</div>
                    </section>
                </div>

                <section class="analytics-section">
                    <div class="analytics-section-header">
                        <h3>Quick Read</h3>
                        <span>at a glance</span>
                    </div>
                    <div class="analytics-insight-grid">${insightChips}</div>
                </section>
            </section>`;
    },

    _renderCard(id, card) {
        const el = document.createElement('div');
        el.className = 'lib-card';
        el.dataset.id = id;

        el.innerHTML = `
            <div class="lib-card-header">
                <div class="lib-card-header-main">
                    <span class="lib-card-name">${escapeHtml(card.mechanic_name || '')}</span>
                    <div class="lib-card-subtitle">
                        <span class="lib-badge game">${escapeHtml(card.game_type || '')}</span>
                        <span class="lib-card-summary">${escapeHtml(card.meta.effectFamily)}</span>
                    </div>
                    <div class="lib-card-badges">
                        <span class="lib-badge quality ${card.meta.qualityClass}">${escapeHtml(card.meta.qualityLabel)}</span>
                        <span class="robustness-pill ${robustnessClass(card.robustnessLabel)}">${escapeHtml(robustnessTitle(card.robustnessLabel))}</span>
                        <span class="lib-badge neutral">${escapeHtml(card.meta.designPattern)}</span>
                    </div>
                </div>
                <span class="lib-card-chevron">&#9660;</span>
            </div>
            <div class="lib-card-scores">
                ${scoreBar('Balance', balanceScoreFromScores(card.scores))}
                ${scoreBar('Depth', card.scores?.depth ?? 0)}
                <hr class="score-divider">
                ${scoreBar('Aggregate', card.scores?.aggregate ?? 0)}
            </div>
            <div class="lib-card-expanded-content hidden">
                <div class="lib-card-meta-grid">
                    <div class="lib-meta-card"><span class="lib-meta-label">Timing</span><span class="lib-meta-value">${escapeHtml(card.meta.timing)}</span></div>
                    <div class="lib-meta-card"><span class="lib-meta-label">Scope</span><span class="lib-meta-value">${escapeHtml(card.meta.interactionScope)}</span></div>
                    <div class="lib-meta-card"><span class="lib-meta-label">Pattern</span><span class="lib-meta-value">${escapeHtml(card.meta.designPattern)}</span></div>
                    <div class="lib-meta-card"><span class="lib-meta-label">Iteration</span><span class="lib-meta-value">${card.iteration ?? 'n/a'}</span></div>
                </div>
                <div class="lib-robustness-panel">
                    <div class="lib-robustness-head">
                        <span class="robustness-pill ${robustnessClass(card.robustnessLabel)}">${escapeHtml(robustnessTitle(card.robustnessLabel))}</span>
                        <span>${escapeHtml(card.robustnessSummary)}</span>
                    </div>
                    <div class="lib-compat-row">
                        <span>Compatible: ${compatPills(card.compatibleGameTypes, 'ok')}</span>
                        <span>Failed: ${compatPills(card.failedGameTypes, 'fail')}</span>
                    </div>
                    <div class="lib-game-result-grid">${gameResultChips(card)}</div>
                </div>
                <div class="lib-quality-line">
                    <span class="lib-quality-title">${escapeHtml(card.meta.qualityLabel)}</span>
                    <span class="lib-quality-copy">Balance ${formatNullableScore(balanceScoreFromScores(card.scores))} · Depth ${formatScore(card.scores?.depth ?? 0)} · Aggregate ${formatScore(card.scores?.aggregate ?? 0)}</span>
                </div>
                <div class="lib-card-desc">${escapeHtml(card.description || '')}</div>
                <div class="lib-card-tutorial">
                    <div class="lib-phase-label phase-before">BEFORE</div>
                    <div class="lib-tutorial-grid"></div>
                </div>
            </div>`;

        el.addEventListener('click', () => this._toggleCard(id));
        this._gridEl.appendChild(el);
    },

    _toggleCard(id) {
        if (this.expandedId === id) {
            this._collapseCard(id);
            this.expandedId = null;
            return;
        }
        if (this.expandedId !== null) this._collapseCard(this.expandedId);
        this._expandCard(id);
        this.expandedId = id;
    },

    _expandCard(id) {
        const el = document.querySelector(`.lib-card[data-id="${id}"]`);
        if (!el) return;
        el.classList.add('expanded');
        el.querySelector('.lib-card-expanded-content').classList.remove('hidden');
        this._startAnimation(id, el);
    },

    _collapseCard(id) {
        const el = document.querySelector(`.lib-card[data-id="${id}"]`);
        if (!el) return;
        el.classList.remove('expanded');
        el.querySelector('.lib-card-expanded-content').classList.add('hidden');
        this._stopAnimation(id);
    },

    _stopAnimation(id) {
        const anim = this._animations[id];
        if (!anim) return;
        anim.generation++;
        clearTimeout(anim.timeout);
        const gridEl = document.querySelector(`.lib-card[data-id="${id}"] .lib-tutorial-grid`);
        if (gridEl) gridEl.classList.remove('fading');
        delete this._animations[id];
    },

    _stopAllAnimations() {
        Object.keys(this._animations).forEach(id => this._stopAnimation(id));
    },

    _startAnimation(id, cardEl) {
        const card = this.cards[id];
        if (!card) return;

        const gridEl = cardEl.querySelector('.lib-tutorial-grid');
        const phaseLabelEl = cardEl.querySelector('.lib-phase-label');

        if (!card.replay) {
            phaseLabelEl.textContent = 'NO REPLAY';
            phaseLabelEl.className = 'lib-phase-label phase-before';
            gridEl.innerHTML = '<div class="lib-no-trigger">Accepted mechanic with no saved replay metadata yet</div>';
            return;
        }

        const trigger = detectMechanicTrigger(card.replay.moves);
        if (!trigger) {
            gridEl.innerHTML = '<div class="lib-no-trigger">Not triggered in this replay</div>';
            return;
        }

        gridEl.innerHTML = '';
        for (let r = 0; r < 6; r++) {
            for (let c = 0; c < 6; c++) {
                const cell = document.createElement('div');
                cell.className = 'lib-cell';
                cell.dataset.pos = `${r},${c}`;
                gridEl.appendChild(cell);
            }
        }

        const anim = { generation: 0, timeout: null, phase: 'before', BEFORE_MS: 2000, AFTER_MS: 2800 };
        this._animations[id] = anim;

        const renderPhase = () => {
            const board = anim.phase === 'before' ? trigger.before : trigger.after;
            if (anim.phase === 'before') {
                phaseLabelEl.textContent = 'BEFORE';
                phaseLabelEl.className = 'lib-phase-label phase-before';
            } else {
                const labels = { board: 'AFTER MECHANIC', extra_turn: 'EXTRA TURN', custom_state: 'STATE UPDATED' };
                phaseLabelEl.textContent = labels[trigger.type] || 'AFTER MECHANIC';
                phaseLabelEl.className = 'lib-phase-label phase-after';
            }

            const cells = gridEl.querySelectorAll('.lib-cell');
            let idx = 0;
            for (let r = 0; r < board.length; r++) {
                for (let c = 0; c < board[r].length; c++) {
                    const cell = cells[idx++];
                    if (!cell) continue;
                    const val = board[r][c];
                    const pos = `${r},${c}`;
                    cell.textContent = val === '_' ? '' : val;
                    cell.className = 'lib-cell';
                    if (val === 'X') cell.classList.add('x');
                    if (val === 'O') cell.classList.add('o');
                    if (anim.phase === 'before' && pos === this._parseMovePos(trigger.move)) {
                        cell.classList.add('highlight');
                    }
                    if (anim.phase === 'after') {
                        if (trigger.type === 'board' && trigger.changes.has(pos)) {
                            cell.classList.add('mechanic-changed');
                        } else if (trigger.type === 'extra_turn' && pos === this._parseMovePos(trigger.bonusMove)) {
                            cell.classList.add('mechanic-changed');
                        } else if (trigger.type === 'custom_state' && pos === this._parseMovePos(trigger.move)) {
                            cell.classList.add('mechanic-changed');
                        }
                    }
                }
            }
        };

        renderPhase();
        const schedule = (gen) => {
            if (gen !== anim.generation) return;
            const holdMs = anim.phase === 'before' ? anim.BEFORE_MS : anim.AFTER_MS;
            anim.timeout = setTimeout(() => {
                if (gen !== anim.generation) return;
                gridEl.classList.add('fading');
                setTimeout(() => {
                    if (gen !== anim.generation) {
                        gridEl.classList.remove('fading');
                        return;
                    }
                    anim.phase = anim.phase === 'before' ? 'after' : 'before';
                    renderPhase();
                    gridEl.classList.remove('fading');
                    schedule(gen);
                }, 260);
            }, holdMs);
        };
        schedule(anim.generation);
    },

    _parseMovePos(moveStr) {
        if (typeof moveStr !== 'string') return null;
        const parts = moveStr.split(' ');
        return parts.length === 2 ? parts[1] : null;
    },

    _enrichCard(card) {
        const robustness = normalizeRobustness(card.robustness);
        return {
            ...card,
            robustness,
            robustnessLabel: robustness.label,
            compatibleGameTypes: robustness.compatible_game_types,
            failedGameTypes: robustness.failed_game_types,
            robustnessSummary: robustnessSummary(robustness),
            meta: classifyMechanic(card),
        };
    },

    _buildAnalytics() {
        const total = this.cards.length;
        const boardCards = this.cards.filter(card => card.game_type === 'board');
        const cardCards = this.cards.filter(card => card.game_type === 'card');
        const avgAggregate = average(this.cards.map(card => card.scores?.aggregate ?? 0));
        const highDepthCount = this.cards.filter(card => (card.scores?.depth ?? 0) >= 0.8).length;
        const boardAgg = average(boardCards.map(card => card.scores?.aggregate ?? 0));
        const cardAgg = average(cardCards.map(card => card.scores?.aggregate ?? 0));

        const familyStats = summarizeBy(this.cards, card => card.meta.effectFamily)
            .map(toMetricSummary)
            .sort((a, b) => b.avgAggregate - a.avgAggregate || b.count - a.count)
            .slice(0, 6);

        const patternStats = summarizeBy(this.cards, card => card.meta.designPattern)
            .map(toMetricSummary)
            .sort((a, b) => b.count - a.count || b.avgAggregate - a.avgAggregate)
            .slice(0, 4);

        const bestOverall = [...this.cards]
            .sort((a, b) => (b.scores?.aggregate ?? 0) - (a.scores?.aggregate ?? 0))
            .slice(0, 3);

        const fairestFamily = familyStats.slice().sort((a, b) => b.avgBalance - a.avgBalance)[0];
        const robustnessStats = summarizeRobustness(this.cards);

        return {
            overview: {
                total,
                boardCount: boardCards.length,
                cardCount: cardCards.length,
                avgAggregate,
                highDepthCount,
                mostFairFamily: fairestFamily ? fairestFamily.label : 'n/a',
                bestGameType: boardAgg >= cardAgg ? `Board (${boardAgg.toFixed(2)})` : `Card (${cardAgg.toFixed(2)})`,
            },
            robustnessStats,
            familyStats,
            patternStats,
            bestOverall,
            insights: buildInsights(this.cards, familyStats, patternStats, boardCards, cardCards),
        };
    },
};

function buildLibraryAnalyticsHtml(analytics) {
    const robustnessCards = analytics.robustnessStats.map(stat => `
        <div class="robustness-stat-card ${robustnessClass(stat.label)}">
            <div class="robustness-stat-icon">${robustnessIcon(stat.label)}</div>
            <div>
                <div class="robustness-stat-label">${escapeHtml(robustnessTitle(stat.label))}</div>
                <div class="robustness-stat-value">${stat.count}</div>
                <div class="robustness-stat-sub">${stat.percent.toFixed(0)}% of library</div>
            </div>
        </div>
    `).join('');

    const robustnessBar = analytics.robustnessStats.map(stat => `
        <div class="robustness-bar-segment ${robustnessClass(stat.label)}" style="width:${stat.percent}%"></div>
    `).join('');

    const familyCards = analytics.familyStats.map(stat => `
        <div class="family-row-card ${stat.robustRate >= 0.5 ? 'strong' : ''}">
            <div class="family-row-top">
                <div class="family-row-title">
                    <span class="family-icon">${familyIcon(stat.label)}</span>
                    <span>${escapeHtml(stat.label)}</span>
                </div>
                <div class="family-row-count">${stat.count}</div>
            </div>
            <div class="family-row-bars">
                ${miniMetricBar('B', stat.avgBalance, 'green')}
                ${miniMetricBar('D', stat.avgDepth, 'blue')}
                ${miniMetricBar('A', stat.avgAggregate, 'purple')}
                ${miniMetricBar('R', stat.robustRate, 'robust')}
            </div>
            <div class="family-row-foot">
                <span>${stat.robustCount} robust</span>
                <span>${stat.contextCount} context</span>
                <span>${stat.nonRobustCount} fail</span>
            </div>
        </div>
    `).join('');

    const bestCards = analytics.bestOverall.map(card => `
        <div class="analytics-best-row">
            <div>
                <div class="analytics-best-name">${escapeHtml(card.mechanic_name)}</div>
                <div class="analytics-best-sub">${escapeHtml(card.meta.effectFamily)} · ${escapeHtml(robustnessTitle(card.robustnessLabel))}</div>
            </div>
            <div class="analytics-best-right">
                <span class="robustness-pill ${robustnessClass(card.robustnessLabel)}">${escapeHtml(robustnessTitle(card.robustnessLabel))}</span>
                <span class="analytics-best-meta">${formatScore(card.scores?.aggregate ?? 0)}</span>
            </div>
        </div>
    `).join('');

    const patternCards = analytics.patternStats.map(stat => `
        <div class="pattern-chip">
            <span class="pattern-icon">${patternIcon(stat.label)}</span>
            <span>${escapeHtml(stat.label)}</span>
            <span class="pattern-chip-meta">${stat.count}</span>
        </div>
    `).join('');

    const insightChips = analytics.insights.map(insight => `
        <div class="insight-chip">
            <span class="insight-icon">${insight.icon}</span>
            <span class="insight-text">${escapeHtml(insight.text)}</span>
        </div>
    `).join('');

    return `
        <section class="library-analytics-panel">
            <div class="library-analytics-hero">
                <div class="analytics-title-block">
                    <div class="analytics-kicker">Library Analytics</div>
                    <h2>Accepted Mechanic Overview</h2>
                    <p>Robustness, family performance, and cross-game compatibility at a glance.</p>
                </div>
                <div class="analytics-score-ring">
                    <div class="score-ring-value">${analytics.overview.avgAggregate.toFixed(2)}</div>
                    <div class="score-ring-label">Avg Aggregate</div>
                </div>
            </div>

            <div class="analytics-overview-grid">
                <div class="analytics-stat-card primary">
                    <div class="analytics-stat-icon">#</div>
                    <div class="analytics-stat-label">Accepted</div>
                    <div class="analytics-stat-value">${analytics.overview.total}</div>
                    <div class="analytics-stat-sub">${analytics.overview.boardCount} board · ${analytics.overview.cardCount} card</div>
                </div>
                <div class="analytics-stat-card">
                    <div class="analytics-stat-icon">D</div>
                    <div class="analytics-stat-label">High Depth</div>
                    <div class="analytics-stat-value">${analytics.overview.highDepthCount}</div>
                    <div class="analytics-stat-sub">depth >= 0.80</div>
                </div>
                <div class="analytics-stat-card">
                    <div class="analytics-stat-icon">F</div>
                    <div class="analytics-stat-label">Most Fair Family</div>
                    <div class="analytics-stat-value small">${escapeHtml(analytics.overview.mostFairFamily)}</div>
                    <div class="analytics-stat-sub">highest avg balance</div>
                </div>
                <div class="analytics-stat-card">
                    <div class="analytics-stat-icon">G</div>
                    <div class="analytics-stat-label">Best Game Type</div>
                    <div class="analytics-stat-value small">${escapeHtml(analytics.overview.bestGameType)}</div>
                    <div class="analytics-stat-sub">higher avg aggregate</div>
                </div>
            </div>

            <section class="analytics-section robustness-section">
                <div class="analytics-section-header">
                    <h3>Robustness Distribution</h3>
                    <span>cross-game verifier labels</span>
                </div>
                <div class="robustness-stat-grid">${robustnessCards}</div>
                <div class="robustness-bar">${robustnessBar}</div>
            </section>

            <div class="analytics-sections">
                <section class="analytics-section">
                    <div class="analytics-section-header">
                        <h3>Family Performance</h3>
                        <span>B / D / A / R</span>
                    </div>
                    <div class="analytics-type-grid">${familyCards}</div>
                </section>

                <section class="analytics-section analytics-side-section">
                    <div class="analytics-section-header">
                        <h3>Top Mechanics</h3>
                        <span>aggregate rank</span>
                    </div>
                    <div class="analytics-best-list">${bestCards}</div>
                    <div class="analytics-section-header secondary">
                        <h3>Patterns</h3>
                        <span>common motifs</span>
                    </div>
                    <div class="analytics-mini-grid">${patternCards}</div>
                </section>
            </div>

            <section class="analytics-section">
                <div class="analytics-section-header">
                    <h3>Quick Read</h3>
                    <span>generated from current library</span>
                </div>
                <div class="analytics-insight-grid">${insightChips}</div>
            </section>
        </section>`;
}

function classifyMechanic(card) {
    const text = `${card.mechanic_name || ''} ${card.description || ''}`.toLowerCase();
    const effectFamily = matchFirst(text, [
        [['extra turn', 'lockstep', 'pause', 'tempo'], 'Tempo / Turn Control'],
        [['capture', 'remove', 'blast', 'destroy'], 'Capture / Removal'],
        [['flip', 'mirror'], 'Flip / Conversion'],
        [['freeze', 'stun', 'lock'], 'Freeze / Denial'],
        [['block', 'guard', 'shield'], 'Block / Protection'],
        [['swap'], 'Swap / Position Shift'],
        [['score', 'bonus', 'point'], 'Scoring Bonus'],
        [['parity', 'threshold', 'hand', 'choice'], 'Hand / Conditional Rule'],
        [['link', 'combo', 'synergy', 'line'], 'Combo / Synergy'],
    ], 'Board Interaction');

    const timing = matchFirst(text, [
        [['on capture', 'capture'], 'On Capture'],
        [['after placing', 'on placement', 'placement'], 'On Placement'],
        [['extra turn', 'turn'], 'Turn-Based Trigger'],
        [['if', 'when', 'threshold', 'parity'], 'Conditional Trigger'],
    ], 'Immediate Trigger');

    const interactionScope = matchFirst(text, [
        [['adjacent', 'orthogonally adjacent'], 'Adjacent Local'],
        [['diagonal'], 'Diagonal Local'],
        [['line', 'row', 'column', '4-in-a-row'], 'Line / Pattern'],
        [['hand', 'card'], 'Hand / Card State'],
        [['center', 'corner'], 'Board Region'],
    ], 'General State');

    const designPattern = matchFirst(text, [
        [['extra turn', 'tempo', 'lockstep', 'pause'], 'Tempo Advantage'],
        [['score', 'bonus', 'choice'], 'Risk / Reward'],
        [['block', 'freeze', 'shield', 'guard'], 'Counterplay'],
        [['link', 'combo', 'synergy'], 'Synergy / Combo'],
        [['adjacent', 'diagonal', 'line', 'corner', 'center'], 'Spatial Tension'],
        [['threshold', 'parity', 'hand'], 'Conditional Planning'],
    ], 'Direct Interaction');

    const balance = balanceScoreFromScores(card.scores) ?? 0;
    const depth = card.scores?.depth ?? 0;
    const aggregate = card.scores?.aggregate ?? 0;

    let qualityLabel = 'Promising';
    let qualityClass = 'promising';
    if (aggregate >= 0.9 && balance >= 0.85 && depth >= 0.8) {
        qualityLabel = 'Elite';
        qualityClass = 'elite';
    } else if (balance >= 0.95 && depth >= 0.75) {
        qualityLabel = 'Fair + Deep';
        qualityClass = 'fairdeep';
    } else if (balance >= 0.95) {
        qualityLabel = 'Very Fair';
        qualityClass = 'fair';
    } else if (depth >= 0.85) {
        qualityLabel = 'High Depth';
        qualityClass = 'depth';
    } else if (aggregate < 0.76) {
        qualityLabel = 'Needs Work';
        qualityClass = 'risky';
    }

    return {
        effectFamily,
        timing,
        interactionScope,
        designPattern,
        qualityLabel,
        qualityClass,
        qualitySummary: `${qualityLabel} · balance ${balance.toFixed(2)} · depth ${depth.toFixed(2)} · agg ${aggregate.toFixed(2)}`,
    };
}

function matchFirst(text, rules, fallback) {
    for (const [keywords, label] of rules) {
        if (keywords.some(keyword => text.includes(keyword))) return label;
    }
    return fallback;
}

function average(values) {
    if (!values.length) return 0;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatScore(value) {
    return Number(value || 0).toFixed(2);
}

function formatNullableScore(value) {
    return value === null || value === undefined || Number.isNaN(value)
        ? 'N/A'
        : Number(value).toFixed(2);
}

function balanceScoreFromScores(scores) {
    if (!scores) return null;
    if (scores.balance_score !== undefined) return scores.balance_score;
    if ((scores.playability ?? 1) <= 0) return null;
    if (scores.balance_gap === undefined || scores.balance_gap === null) return null;
    return Math.round((1 - scores.balance_gap) * 1000) / 1000;
}

function summarizeBy(cards, keyFn) {
    const groups = new Map();
    cards.forEach(card => {
        const key = keyFn(card);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(card);
    });
    return [...groups.entries()].map(([label, groupedCards]) => ({ label, cards: groupedCards }));
}

function toMetricSummary(group) {
    const robustCount = group.cards.filter(card => card.robustnessLabel === 'robust').length;
    const contextCount = group.cards.filter(card => card.robustnessLabel === 'context_sensitive').length;
    const nonRobustCount = group.cards.filter(card => card.robustnessLabel === 'non_robust').length;
    const testedCount = group.cards.filter(card => card.robustnessLabel !== 'untested').length;
    return {
        label: group.label,
        count: group.cards.length,
        avgBalance: average(group.cards.map(card => balanceScoreFromScores(card.scores)).filter(value => value !== null && value !== undefined && !Number.isNaN(value))),
        avgDepth: average(group.cards.map(card => card.scores?.depth ?? 0)),
        avgAggregate: average(group.cards.map(card => card.scores?.aggregate ?? 0)),
        robustCount,
        contextCount,
        nonRobustCount,
        testedCount,
        robustRate: testedCount ? robustCount / testedCount : 0,
    };
}

function normalizeRobustness(raw) {
    const knownLabels = new Set(['robust', 'context_sensitive', 'non_robust']);
    const source = raw && typeof raw === 'object' ? raw : {};
    const label = knownLabels.has(source.label) ? source.label : 'untested';
    return {
        label,
        compatible_game_types: Array.isArray(source.compatible_game_types) ? source.compatible_game_types : [],
        failed_game_types: Array.isArray(source.failed_game_types) ? source.failed_game_types : [],
        per_game: source.per_game && typeof source.per_game === 'object' ? source.per_game : {},
        tested_games: Number(source.tested_games || 0),
    };
}

function robustnessTitle(label) {
    const titles = {
        robust: 'Robust',
        context_sensitive: 'Context-sensitive',
        non_robust: 'Non-robust',
        untested: 'Untested',
    };
    return titles[label] || 'Untested';
}

function robustnessClass(label) {
    return (label || 'untested').replace(/_/g, '-');
}

function robustnessIcon(label) {
    if (label === 'robust') return 'R';
    if (label === 'context_sensitive') return 'C';
    if (label === 'non_robust') return '!';
    return '?';
}

function robustnessSummary(robustness) {
    if (!robustness || robustness.label === 'untested') return 'No cross-game robustness pass yet';
    const ok = robustness.compatible_game_types.length;
    const fail = robustness.failed_game_types.length;
    return `${ok} compatible · ${fail} failed · ${robustness.tested_games || ok + fail} tested`;
}

function summarizeRobustness(cards) {
    const order = ['robust', 'context_sensitive', 'non_robust', 'untested'];
    const total = cards.length || 1;
    return order.map(label => {
        const count = cards.filter(card => card.robustnessLabel === label).length;
        return {
            label,
            count,
            percent: (count / total) * 100,
        };
    });
}

function compatPills(items, tone) {
    if (!items || !items.length) return '<span class="mini-pill muted">none</span>';
    return items.map(item => `<span class="mini-pill ${tone}">${escapeHtml(item)}</span>`).join('');
}

function gameResultChips(card) {
    const perGame = card.robustness?.per_game || {};
    const keys = Object.keys(perGame).sort();
    if (!keys.length) return '<div class="game-result-chip muted">No per-game verifier data</div>';
    return keys.map(game => {
        const result = perGame[game] || {};
        const decision = result.decision || 'unknown';
        const cls = decision === 'accept' ? 'ok' : 'fail';
        const reason = result.reason || 'no reason';
        return `
            <div class="game-result-chip ${cls}">
                <span>${escapeHtml(game)}</span>
                <strong>${escapeHtml(decision)}</strong>
                <small>${escapeHtml(reason)}</small>
            </div>`;
    }).join('');
}

function buildInsights(allCards, familyStats, patternStats, boardCards, cardCards) {
    if (!allCards.length) return [];
    const insights = [];
    const topFamily = familyStats[0];
    if (topFamily) {
        insights.push({ icon: '★', text: `${topFamily.label} leads aggregate at ${topFamily.avgAggregate.toFixed(2)}` });
    }
    const riskiestFamily = familyStats.slice().sort((a, b) => a.avgBalance - b.avgBalance)[0];
    if (riskiestFamily) {
        insights.push({ icon: '⚠', text: `${riskiestFamily.label} is the riskiest family` });
    }
    const topPattern = patternStats[0];
    if (topPattern) {
        insights.push({ icon: '◆', text: `${topPattern.label} is the most common pattern` });
    }
    if (boardCards.length && cardCards.length) {
        const boardAgg = average(boardCards.map(card => card.scores?.aggregate ?? 0));
        const cardAgg = average(cardCards.map(card => card.scores?.aggregate ?? 0));
        const stronger = boardAgg >= cardAgg ? 'Board' : 'Card';
        insights.push({ icon: '◈', text: `${stronger} mechanics score better on average` });
    }
    const highDepth = allCards.filter(card => (card.scores?.depth ?? 0) >= 0.8).length;
    insights.push({ icon: '▲', text: `${highDepth} mechanics qualify as high-depth` });
    return insights.slice(0, 4);
}

function familyIcon(label) {
    if (label.includes('Capture')) return '✦';
    if (label.includes('Flip')) return '◇';
    if (label.includes('Freeze')) return '❄';
    if (label.includes('Block')) return '■';
    if (label.includes('Swap')) return '⇄';
    if (label.includes('Tempo')) return '⟳';
    if (label.includes('Scoring')) return '＋';
    if (label.includes('Hand')) return '▣';
    if (label.includes('Combo')) return '⟡';
    return '●';
}

function patternIcon(label) {
    if (label.includes('Tempo')) return '⟳';
    if (label.includes('Risk')) return '⚑';
    if (label.includes('Counter')) return '⛨';
    if (label.includes('Synergy')) return '⟡';
    if (label.includes('Spatial')) return '▦';
    if (label.includes('Conditional')) return '◇';
    return '●';
}

function miniMetricBar(label, value, tone) {
    return `
        <div class="mini-metric">
            <span class="mini-metric-label">${label}</span>
            <div class="mini-metric-track">
                <div class="mini-metric-fill ${tone}" style="width:${Math.max(0, Math.min(100, value * 100))}%"></div>
            </div>
            <span class="mini-metric-value">${value.toFixed(2)}</span>
        </div>
    `;
}


// Wire up replay buttons
replayPlay.addEventListener('click', () => {
    if (replayPlayer.playing) replayPlayer.stop();
    else replayPlayer.play();
});
replayBack.addEventListener('click', () => replayPlayer.stepBack());
replayForward.addEventListener('click', () => replayPlayer.stepForward());
replaySpeed.addEventListener('input', () => {
    if (replayPlayer.playing) {
        replayPlayer.stop();
        replayPlayer.play();
    }
});


// ── Tab Switching ────────────────────────────────────────────────────────────

const mainLayout   = document.getElementById('main-layout');
const libraryView  = document.getElementById('library-view');
const tabPipeline  = document.getElementById('tab-pipeline');
const tabLibrary   = document.getElementById('tab-library');

function switchTab(tab) {
    if (tab === 'pipeline') {
        mainLayout.classList.remove('hidden');
        libraryView.classList.add('hidden');
        tabPipeline.classList.add('active');
        tabLibrary.classList.remove('active');
        // Collapse any open library card so its animation stops
        if (libraryManager.expandedId !== null) {
            libraryManager._collapseCard(libraryManager.expandedId);
            libraryManager.expandedId = null;
        }
    } else {
        mainLayout.classList.add('hidden');
        libraryView.classList.remove('hidden');
        tabLibrary.classList.add('active');
        tabPipeline.classList.remove('active');
    }
}

tabPipeline.addEventListener('click', () => switchTab('pipeline'));
tabLibrary.addEventListener('click',  () => switchTab('library'));


// ── Startup ──────────────────────────────────────────────────────────────────

libraryManager.init();
