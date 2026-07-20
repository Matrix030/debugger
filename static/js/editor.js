/* DebugLab Monaco editor wrapper (Monaco is vendored locally; no CDN). */
(function () {
    "use strict";

    let editor = null;
    let monacoInitPromise = null;

    function loadMonaco() {
        if (monacoInitPromise) {
            return monacoInitPromise;
        }
        monacoInitPromise = new Promise(function (resolve, reject) {
            if (window.monaco && window.monaco.editor) {
                resolve(window.monaco);
                return;
            }
            window.MonacoEnvironment = {
                getWorkerUrl: function () {
                    return "/static/vendor/monaco/vs/base/worker/workerMain.js";
                },
            };
            const script = document.createElement("script");
            script.src = "/static/vendor/monaco/vs/loader.js";
            script.onload = function () {
                window.require.config({
                    paths: { vs: "/static/vendor/monaco/vs" },
                });
                window.require(
                    ["vs/editor/editor.main"],
                    function () {
                        resolve(window.monaco);
                    },
                    reject
                );
            };
            script.onerror = function () {
                reject(new Error("Failed to load the Monaco editor"));
            };
            document.head.appendChild(script);
        });
        return monacoInitPromise;
    }

    window.debuglabEditor = {
        init: function (container, options) {
            const opts = options || {};
            return loadMonaco().then(function (monaco) {
                if (editor) {
                    editor.dispose();
                    editor = null;
                }
                editor = monaco.editor.create(container, {
                    value: opts.value || "",
                    language: opts.language || "python",
                    theme: "vs-dark",
                    automaticLayout: true,
                    minimap: { enabled: false },
                    fontSize: 14,
                    scrollBeyondLastLine: false,
                    tabSize: 4,
                    insertSpaces: true,
                });
                if (typeof opts.onChange === "function") {
                    editor.onDidChangeModelContent(function () {
                        opts.onChange(editor.getValue());
                    });
                }
                if (typeof opts.onCursor === "function") {
                    editor.onDidChangeCursorPosition(function (event) {
                        opts.onCursor(event.position.lineNumber, event.position.column);
                    });
                }
                return editor;
            });
        },

        getValue: function () {
            return editor ? editor.getValue() : "";
        },

        setValue: function (value) {
            if (editor) {
                editor.setValue(value || "");
            }
        },

        layout: function () {
            if (editor) {
                editor.layout();
            }
        },
    };
})();
