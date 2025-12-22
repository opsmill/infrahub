import ReactDOM from "react-dom/client";

// Initialize plugin runtime (exposes React/ReactRouter as globals for plugins)
import "@/entities/plugins/runtime/infrahub-runtime";

import { App } from "@/app/app";

// https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react#consistent-components-exports
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
