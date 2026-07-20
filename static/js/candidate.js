/* DebugLab candidate workspace: question loading, run/submit, persistence. */
(function () {
    "use strict";

    const CODE_KEY_PREFIX = "debuglab:code:";
    const LAST_QUESTION_KEY = "debuglab:last-question";

    let questions = [];
    let current = null;
    let busy = false;
    let saveTimer = null;

    const problemBody = document.getElementById("problem-body");
    const progressEl = document.getElementById("question-progress");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const runBtn = document.getElementById("run-btn");
    const submitBtn = document.getElementById("submit-btn");
    const resetBtn = document.getElementById("reset-btn");
    const resultsConsole = document.getElementById("results-console");
    const resultsBody = document.getElementById("results-body");
    const resultsTitle = document.getElementById("results-title");
    const resultsClose = document.getElementById("results-close");
    const cursorEl = document.getElementById("cursor-position");
    const saveIndicator = document.getElementById("save-indicator");

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function formatValue(value) {
        try {
            return JSON.stringify(value);
        } catch (_err) {
            return String(value);
        }
    }

    function codeKey(questionId) {
        return CODE_KEY_PREFIX + questionId;
    }

    function readStored(key) {
        try {
            return localStorage.getItem(key);
        } catch (_err) {
            return null;
        }
    }

    function writeStored(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (_err) {
            /* ignore quota errors */
        }
    }

    function removeStored(key) {
        try {
            localStorage.removeItem(key);
        } catch (_err) {
            /* ignore */
        }
    }

    function setBusy(value, label) {
        busy = value;
        [runBtn, submitBtn, resetBtn, prevBtn, nextBtn].forEach(function (btn) {
            if (btn) {
                btn.disabled = value;
            }
        });
        if (!value) {
            updateNavButtons();
        }
        runBtn.textContent = value && label === "run" ? "Running…" : "Run Code";
        submitBtn.textContent =
            value && label === "submit" ? "Submitting…" : "Submit";
    }

    function updateNavButtons() {
        if (!current) {
            return;
        }
        prevBtn.disabled = current.index <= 0;
        nextBtn.disabled = current.index >= current.total - 1;
    }

    function difficultyBadge(difficulty) {
        return (
            '<span class="badge badge--' +
            escapeHtml(difficulty) +
            '">' +
            escapeHtml(difficulty.charAt(0).toUpperCase() + difficulty.slice(1)) +
            "</span>"
        );
    }

    function renderProblem(question) {
        let html = "";
        html += '<div class="problem-header">';
        html += '<span class="problem-header__icon" aria-hidden="true">&#128196;</span>';
        html += "<h1>" + escapeHtml(question.title) + "</h1>";
        html += "</div>";
        html += '<div class="problem-meta">';
        html += difficultyBadge(question.difficulty);
        question.tags.forEach(function (tag) {
            html += '<span class="tag-chip">' + escapeHtml(tag) + "</span>";
        });
        html += "</div>";
        html +=
            '<div class="problem-description">' + question.description_html + "</div>";
        if (question.constraints && question.constraints.length) {
            html += "<h3>Constraints</h3><ul class='problem-constraints'>";
            question.constraints.forEach(function (item) {
                html += "<li><code>" + escapeHtml(item) + "</code></li>";
            });
            html += "</ul>";
        }
        if (question.visible_tests && question.visible_tests.length) {
            html += "<h3>Sample Tests</h3>";
            question.visible_tests.forEach(function (test, i) {
                html += '<div class="sample-test">';
                html +=
                    '<div class="sample-test__name">Test ' +
                    (i + 1) +
                    ": " +
                    escapeHtml(test.name) +
                    "</div>";
                html +=
                    '<pre class="sample-test__io">' +
                    escapeHtml(
                        question.function_name +
                            "(" +
                            test.args.map(formatValue).join(", ") +
                            ")"
                    ) +
                    "\n&rarr; " +
                    escapeHtml(formatValue(test.expected)) +
                    "</pre>";
                html += "</div>";
            });
        }
        html +=
            '<p class="problem-footnote">Time limit: ' +
            escapeHtml(String(question.time_limit_seconds)) +
            "s per test &middot; Memory limit: " +
            escapeHtml(String(question.memory_limit_mb)) +
            " MB</p>";
        problemBody.innerHTML = html;
    }

    function hideResults() {
        resultsConsole.hidden = true;
        resultsBody.innerHTML = "";
        window.debuglabEditor.layout();
    }

    function showResults(title) {
        resultsTitle.textContent = title;
        resultsConsole.hidden = false;
        window.debuglabEditor.layout();
    }

    function statusPill(status) {
        const labels = {
            passed: "Passed",
            failed: "Failed",
            error: "Error",
            timeout: "Timed out",
        };
        return (
            '<span class="result-pill result-pill--' +
            escapeHtml(status) +
            '">' +
            (labels[status] || escapeHtml(status)) +
            "</span>"
        );
    }

    function renderVisibleResults(results) {
        let html = "";
        results.forEach(function (result) {
            html += '<div class="result-row result-row--' + escapeHtml(result.status) + '">';
            html +=
                '<div class="result-row__head">' +
                statusPill(result.status) +
                '<span class="result-row__name">' +
                escapeHtml(result.name) +
                "</span></div>";
            if (result.status === "failed") {
                html +=
                    '<pre class="result-detail">expected: ' +
                    escapeHtml(formatValue(result.expected)) +
                    "\ngot:      " +
                    escapeHtml(result.actual == null ? "nothing" : result.actual) +
                    "</pre>";
            }
            if (result.error) {
                html +=
                    '<pre class="result-detail result-detail--error">' +
                    escapeHtml(result.error) +
                    "</pre>";
            }
            if (result.stdout) {
                html +=
                    '<details class="result-output"><summary>stdout</summary><pre>' +
                    escapeHtml(result.stdout) +
                    "</pre></details>";
            }
            if (result.stderr) {
                html +=
                    '<details class="result-output"><summary>stderr</summary><pre>' +
                    escapeHtml(result.stderr) +
                    "</pre></details>";
            }
            html += "</div>";
        });
        return html;
    }

    function renderSyntaxError(payload) {
        let message = payload.syntax_error
            ? payload.syntax_error.message
            : "Syntax error";
        if (payload.syntax_error && payload.syntax_error.line != null) {
            message = "Line " + payload.syntax_error.line + ": " + message;
        }
        return (
            '<div class="result-banner result-banner--error">Syntax error</div>' +
            '<pre class="result-detail result-detail--error">' +
            escapeHtml(message) +
            "</pre>"
        );
    }

    function renderRunResponse(payload) {
        if (payload.status === "syntax_error") {
            resultsBody.innerHTML = renderSyntaxError(payload);
            showResults("Run — syntax error");
            return;
        }
        let html = "";
        if (payload.all_passed) {
            html +=
                '<div class="result-banner result-banner--success">All sample tests passed &#10003;</div>';
        } else {
            html +=
                '<div class="result-banner">' +
                payload.passed_count +
                " / " +
                payload.total_count +
                " sample tests passed</div>";
        }
        html += renderVisibleResults(payload.visible_results);
        resultsBody.innerHTML = html;
        showResults("Run results (sample tests)");
    }

    function renderSubmitResponse(payload) {
        if (payload.status === "syntax_error") {
            resultsBody.innerHTML = renderSyntaxError(payload);
            showResults("Submission — syntax error");
            return;
        }
        let html = "";
        if (payload.all_passed) {
            html +=
                '<div class="result-banner result-banner--success">Accepted — all ' +
                payload.total_count +
                " tests passed &#127881;</div>";
        } else {
            html +=
                '<div class="result-banner result-banner--fail">' +
                payload.passed_count +
                " / " +
                payload.total_count +
                " tests passed</div>";
        }
        html += "<h4>Sample tests</h4>";
        html += renderVisibleResults(payload.visible_results);
        html += "<h4>Hidden tests</h4>";
        payload.hidden_results.forEach(function (result) {
            html +=
                '<div class="result-row result-row--' +
                escapeHtml(result.status) +
                '"><div class="result-row__head">' +
                statusPill(result.status) +
                '<span class="result-row__name">' +
                escapeHtml(result.label) +
                "</span></div></div>";
        });
        resultsBody.innerHTML = html;
        showResults("Submission results");
    }

    function renderErrorMessage(message) {
        resultsBody.innerHTML =
            '<div class="result-banner result-banner--error">' +
            escapeHtml(message) +
            "</div>";
        showResults("Error");
    }

    function scheduleSave() {
        if (!current) {
            return;
        }
        const questionId = current.id;
        if (saveTimer) {
            clearTimeout(saveTimer);
        }
        saveTimer = setTimeout(function () {
            writeStored(codeKey(questionId), window.debuglabEditor.getValue());
            if (saveIndicator) {
                saveIndicator.hidden = false;
                setTimeout(function () {
                    saveIndicator.hidden = true;
                }, 1200);
            }
        }, 400);
    }

    function loadQuestion(questionId) {
        return fetch("/api/questions/" + encodeURIComponent(questionId))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Failed to load question");
                }
                return response.json();
            })
            .then(function (question) {
                current = question;
                writeStored(LAST_QUESTION_KEY, question.id);
                renderProblem(question);
                hideResults();
                progressEl.textContent =
                    "Question " + (question.index + 1) + " of " + question.total;
                updateNavButtons();
                const saved = readStored(codeKey(question.id));
                const value = saved != null ? saved : question.starter_code;
                return window.debuglabEditor.init(
                    document.getElementById("code-editor"),
                    {
                        value: value,
                        language: question.language,
                        onChange: scheduleSave,
                        onCursor: function (line, col) {
                            cursorEl.textContent = "Line: " + line + " Col: " + col;
                        },
                    }
                );
            })
            .catch(function (error) {
                problemBody.innerHTML =
                    '<p class="problem-loading">' +
                    escapeHtml(error.message || "Failed to load question") +
                    "</p>";
            });
    }

    function navigate(delta) {
        if (!current || busy) {
            return;
        }
        const nextIndex = current.index + delta;
        if (nextIndex < 0 || nextIndex >= questions.length) {
            return;
        }
        loadQuestion(questions[nextIndex].id);
    }

    function execute(endpoint, label, renderFn) {
        if (!current || busy) {
            return;
        }
        setBusy(true, label);
        fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question_id: current.id,
                code: window.debuglabEditor.getValue(),
            }),
        })
            .then(function (response) {
                if (response.status === 503) {
                    return response.json().then(function (body) {
                        throw new Error(
                            body.detail || "Execution service unavailable"
                        );
                    });
                }
                if (!response.ok) {
                    throw new Error("Request failed (" + response.status + ")");
                }
                return response.json();
            })
            .then(renderFn)
            .catch(function (error) {
                renderErrorMessage(error.message || "Something went wrong");
            })
            .finally(function () {
                setBusy(false);
            });
    }

    runBtn.addEventListener("click", function () {
        execute("/api/run", "run", renderRunResponse);
    });

    submitBtn.addEventListener("click", function () {
        execute("/api/submit", "submit", renderSubmitResponse);
    });

    resetBtn.addEventListener("click", function () {
        if (!current || busy) {
            return;
        }
        const confirmed = window.confirm(
            "Reset your code to the original starter code? Your current edits for this question will be lost."
        );
        if (!confirmed) {
            return;
        }
        removeStored(codeKey(current.id));
        window.debuglabEditor.setValue(current.starter_code);
        hideResults();
    });

    resultsClose.addEventListener("click", hideResults);
    prevBtn.addEventListener("click", function () {
        navigate(-1);
    });
    nextBtn.addEventListener("click", function () {
        navigate(1);
    });

    fetch("/api/questions")
        .then(function (response) {
            if (!response.ok) {
                throw new Error("Failed to load question list");
            }
            return response.json();
        })
        .then(function (list) {
            questions = list;
            if (!questions.length) {
                problemBody.innerHTML =
                    '<p class="problem-loading">No questions found. Add YAML files under data/questions/.</p>';
                progressEl.textContent = "No questions";
                return;
            }
            const last = readStored(LAST_QUESTION_KEY);
            const initial = questions.some(function (q) {
                return q.id === last;
            })
                ? last
                : questions[0].id;
            loadQuestion(initial);
        })
        .catch(function (error) {
            problemBody.innerHTML =
                '<p class="problem-loading">' +
                escapeHtml(error.message || "Failed to load questions") +
                "</p>";
        });
})();
