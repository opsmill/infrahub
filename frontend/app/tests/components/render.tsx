import { QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "jotai";
import React from "react";
import { BrowserRouter } from "react-router-dom";
import { Slide, ToastContainer } from "react-toastify";
import { render as renderFromVitest } from "vitest-browser-react";

import { queryClient } from "../../src/shared/api/rest/client";
import { store } from "../../src/shared/stores";

import "/src/app/styles/index.css";
import "react-toastify/dist/ReactToastify.css";
import queryString from "query-string";
import { QueryParamProvider } from "use-query-params";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";

export const render = (component: React.ReactElement, options = {}) =>
  renderFromVitest(component, {
    wrapper: ({ children }) => (
      <Provider store={store}>
        <QueryClientProvider client={queryClient}>
          <QueryParamProvider
            adapter={ReactRouter6Adapter}
            options={{
              searchStringToObject: queryString.parse,
              objectToSearchString: queryString.stringify,
            }}
          >
            <ToastContainer
              hideProgressBar={true}
              transition={Slide}
              autoClose={5000}
              closeOnClick={false}
              newestOnTop
              position="bottom-right"
            />
            <BrowserRouter> {children}</BrowserRouter>
          </QueryParamProvider>
        </QueryClientProvider>
      </Provider>
    ),
    ...options,
  });
