/* DebugLab interview timer: client-side, persisted in localStorage.
 * Never auto-submits or touches candidate code on expiry. */
(function () {
    "use strict";

    const STORAGE_KEY = "debuglab:timer";
    const DEFAULT_DURATION_SECONDS = 90 * 60;

    const display = document.getElementById("timer-display");
    const toggleBtn = document.getElementById("timer-toggle");
    const resetBtn = document.getElementById("timer-reset");
    const widget = document.getElementById("timer-widget");

    if (!display || !toggleBtn || !resetBtn) {
        return;
    }

    function readState() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === "object" && parsed.status) {
                    return parsed;
                }
            }
        } catch (_err) {
            /* fall through to default */
        }
        return {
            status: "idle",
            durationSeconds: DEFAULT_DURATION_SECONDS,
            remainingSeconds: DEFAULT_DURATION_SECONDS,
            endAt: null,
        };
    }

    function writeState(state) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (_err) {
            /* ignore quota errors */
        }
    }

    let state = readState();

    function remainingSeconds() {
        if (state.status === "running") {
            return Math.ceil((state.endAt - Date.now()) / 1000);
        }
        return state.remainingSeconds;
    }

    function formatTime(totalSeconds) {
        const clamped = Math.max(0, totalSeconds);
        const minutes = Math.floor(clamped / 60);
        const seconds = clamped % 60;
        return (
            String(minutes).padStart(2, "0") +
            ":" +
            String(seconds).padStart(2, "0")
        );
    }

    function render() {
        const remaining = remainingSeconds();
        if (state.status === "running" && remaining <= 0) {
            state = {
                status: "expired",
                durationSeconds: state.durationSeconds,
                remainingSeconds: 0,
                endAt: null,
            };
            writeState(state);
        }
        const isExpired = state.status === "expired";
        display.textContent = isExpired ? "Time expired" : formatTime(remaining);
        display.classList.toggle(
            "timer__display--warning",
            !isExpired && state.status === "running" && remaining <= 300
        );
        display.classList.toggle("timer__display--expired", isExpired);
        if (widget) {
            widget.classList.toggle("timer--expired", isExpired);
        }
        if (isExpired) {
            toggleBtn.textContent = "Start";
            toggleBtn.disabled = true;
        } else {
            toggleBtn.disabled = false;
            toggleBtn.textContent = state.status === "running" ? "Pause" : "Start";
        }
    }

    toggleBtn.addEventListener("click", function () {
        if (state.status === "running") {
            state = {
                status: "paused",
                durationSeconds: state.durationSeconds,
                remainingSeconds: Math.max(0, remainingSeconds()),
                endAt: null,
            };
        } else {
            const remaining =
                state.remainingSeconds > 0
                    ? state.remainingSeconds
                    : state.durationSeconds;
            state = {
                status: "running",
                durationSeconds: state.durationSeconds,
                remainingSeconds: remaining,
                endAt: Date.now() + remaining * 1000,
            };
        }
        writeState(state);
        render();
    });

    resetBtn.addEventListener("click", function () {
        state = {
            status: "idle",
            durationSeconds: DEFAULT_DURATION_SECONDS,
            remainingSeconds: DEFAULT_DURATION_SECONDS,
            endAt: null,
        };
        writeState(state);
        render();
    });

    setInterval(render, 500);
    render();
})();
