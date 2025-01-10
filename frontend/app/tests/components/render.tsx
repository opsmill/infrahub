import { QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "jotai";
import React from "react";
import { Slide, ToastContainer } from "react-toastify";
import { render as renderFromVitest } from "vitest-browser-react";
import { queryClient } from "../../src/api/client";
import { store } from "../../src/state";

import "/src/app/styles/index.css";
import "react-toastify/dist/ReactToastify.css";

export const render = (component: React.ReactElement, options = {}) =>
  renderFromVitest(component, {
    wrapper: ({ children }) => (
      <Provider store={store}>
        <QueryClientProvider client={queryClient}>
          <ToastContainer
            hideProgressBar={true}
            transition={Slide}
            autoClose={5000}
            closeOnClick={false}
            newestOnTop
            position="bottom-right"
          />
          {children}
        </QueryClientProvider>
      </Provider>
    ),
    ...options,
  });
