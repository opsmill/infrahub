// Ensure window.Prism is set before any prismjs language components run.
// Rolldown (Vite 8) wraps prismjs in a lazy CJS factory but inlines language
// components as top-level code — they reference a bare `Prism` global that
// doesn't exist yet. This module forces prismjs evaluation and sets the global.
import Prism from "prismjs";

window.Prism = Prism;
