import { QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "jotai";
import queryString from "query-string";
import React from "react";
import { BrowserRouter } from "react-router";
import { Slide, ToastContainer } from "react-toastify";
import { QueryParamProvider } from "use-query-params";
import { render as renderFromVitest } from "vitest-browser-react";

import { BranchContext } from "../../src/entities/branches/ui/branches-provider";
import { queryClient } from "../../src/shared/api/rest/client";
import { ReactRouter7Adapter } from "../../src/shared/libs/use-query-params";
import { store } from "../../src/shared/stores";
import { generateBranch } from "../fake/branch";

import "/src/app/styles/index.css";
import "react-toastify/dist/ReactToastify.css";

export const render = (component: React.ReactElement, options = {}) =>
  renderFromVitest(component, {
    wrapper: ({ children }) => {
      const [currentBranch, setCurrentBranch] = React.useState(generateBranch());

      return (
        <Provider store={store}>
          <QueryClientProvider client={queryClient}>
            <BrowserRouter>
              <QueryParamProvider
                adapter={ReactRouter7Adapter}
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
                <BranchContext value={{ currentBranch, setCurrentBranch }}>
                  {children}
                </BranchContext>
              </QueryParamProvider>
            </BrowserRouter>
          </QueryClientProvider>
        </Provider>
      );
    },
    ...options,
  });
