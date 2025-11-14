import { QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "jotai";
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";
import React from "react";
import { BrowserRouter } from "react-router";
import { Slide, ToastContainer } from "react-toastify";
import { render as renderFromVitest } from "vitest-browser-react";

import { BranchContext } from "../../src/entities/branches/ui/branches-provider";
import { queryClient } from "../../src/shared/api/rest/client";
import { store } from "../../src/shared/stores";
import { generateBranch } from "../fake/branch";

import "/src/app/styles/index.css";
import "react-toastify/dist/ReactToastify.css";

export const render = (component: React.ReactElement, options = {}) =>
  renderFromVitest(component, {
    wrapper: ({ children }) => {
      const [currentBranch, setCurrentBranch] = React.useState(generateBranch());

      return (
        <NuqsAdapter>
          <Provider store={store}>
            <QueryClientProvider client={queryClient}>
              <BrowserRouter>
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
              </BrowserRouter>
            </QueryClientProvider>
          </Provider>
        </NuqsAdapter>
      );
    },
    ...options,
  });
