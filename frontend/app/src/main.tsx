import ErrorFallback from "@/screens/errors/error-fallback";
import { Provider } from "jotai";
import ReactDOM from "react-dom/client";
import { ErrorBoundary } from "react-error-boundary";
import { Infrahub } from "./";
import { store } from "./state";

// https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react#consistent-components-exports
ReactDOM.createRoot(document.getElementById("root")!).render(
  <Provider store={store}>
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <Infrahub />
    </ErrorBoundary>
  </Provider>
);
