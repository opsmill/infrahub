import React from "react";
import ReactDOM from "react-dom/client";
import { Provider } from "jotai";
import { Infrahub } from "./";
import { store } from "./state";

// https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react#consistent-components-exports
ReactDOM.createRoot(document.getElementById("root")!).render(
  <Provider store={store}>
    <Infrahub />
  </Provider>
);
