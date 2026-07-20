/* DebugLab resizable panes: drag the gutters like LeetCode/HackerRank.
 * Sizes persist in localStorage; double-click a gutter to reset. */
(function () {
    "use strict";

    const SPLIT_KEY = "debuglab:layout:split-px";
    const RESULTS_KEY = "debuglab:layout:results-px";

    const workspace = document.getElementById("workspace");
    const splitGutter = document.getElementById("split-gutter");
    const resultsGutter = document.getElementById("results-gutter");
    const resultsConsole = document.getElementById("results-console");

    if (!workspace || !splitGutter || !resultsGutter || !resultsConsole) {
        return;
    }

    function readPx(key) {
        try {
            const value = parseFloat(localStorage.getItem(key));
            return Number.isFinite(value) && value > 0 ? value : null;
        } catch (_err) {
            return null;
        }
    }

    function writePx(key, value) {
        try {
            localStorage.setItem(key, String(Math.round(value)));
        } catch (_err) {
            /* ignore quota errors */
        }
    }

    function removeKey(key) {
        try {
            localStorage.removeItem(key);
        } catch (_err) {
            /* ignore */
        }
    }

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function relayoutEditor() {
        if (window.debuglabEditor) {
            window.debuglabEditor.layout();
        }
    }

    /* ---- restore persisted sizes ---- */

    const savedSplit = readPx(SPLIT_KEY);
    if (savedSplit) {
        workspace.style.setProperty("--split-left", savedSplit + "px");
    }
    function applyResultsHeight(height) {
        // Override the default content-sized max-height once the user
        // has chosen an explicit height.
        resultsConsole.style.height = height + "px";
        resultsConsole.style.maxHeight = height + "px";
    }

    const savedResults = readPx(RESULTS_KEY);
    if (savedResults) {
        applyResultsHeight(savedResults);
    }

    /* ---- generic drag wiring ---- */

    function makeDraggable(gutter, cursorClass, onMove, onReset) {
        gutter.addEventListener("pointerdown", function (event) {
            event.preventDefault();
            gutter.setPointerCapture(event.pointerId);
            document.body.classList.add("is-resizing", cursorClass);

            function handleMove(moveEvent) {
                onMove(moveEvent);
            }

            function handleUp() {
                gutter.removeEventListener("pointermove", handleMove);
                gutter.removeEventListener("pointerup", handleUp);
                gutter.removeEventListener("pointercancel", handleUp);
                document.body.classList.remove("is-resizing", cursorClass);
                relayoutEditor();
            }

            gutter.addEventListener("pointermove", handleMove);
            gutter.addEventListener("pointerup", handleUp);
            gutter.addEventListener("pointercancel", handleUp);
        });
        gutter.addEventListener("dblclick", function () {
            onReset();
            relayoutEditor();
        });
    }

    /* ---- vertical split: problem pane | editor pane ---- */

    makeDraggable(
        splitGutter,
        "is-resizing--col",
        function (event) {
            const rect = workspace.getBoundingClientRect();
            const width = clamp(
                event.clientX - rect.left - splitGutter.offsetWidth / 2,
                280,
                rect.width * 0.75
            );
            workspace.style.setProperty("--split-left", width + "px");
            writePx(SPLIT_KEY, width);
        },
        function () {
            workspace.style.removeProperty("--split-left");
            removeKey(SPLIT_KEY);
        }
    );

    /* ---- horizontal split: editor | results console ---- */

    makeDraggable(
        resultsGutter,
        "is-resizing--row",
        function (event) {
            const consoleBottom = resultsConsole.getBoundingClientRect().bottom;
            const shell = resultsConsole.parentElement.getBoundingClientRect();
            const height = clamp(
                consoleBottom - event.clientY,
                96,
                shell.height * 0.8
            );
            applyResultsHeight(height);
            writePx(RESULTS_KEY, height);
        },
        function () {
            resultsConsole.style.height = "";
            resultsConsole.style.maxHeight = "";
            removeKey(RESULTS_KEY);
        }
    );

    /* ---- keep the results gutter in sync with console visibility ---- */

    function syncResultsGutter() {
        resultsGutter.hidden = resultsConsole.hidden;
    }

    new MutationObserver(syncResultsGutter).observe(resultsConsole, {
        attributes: true,
        attributeFilter: ["hidden"],
    });
    syncResultsGutter();
})();
