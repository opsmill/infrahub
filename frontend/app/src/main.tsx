import ReactDOM from "react-dom/client";

import { App } from "@/app/app";

// https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react#consistent-components-exports
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
