import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "jotai";
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";
import type React from "react";
import { BrowserRouter } from "react-router";
import { Slide, ToastContainer } from "react-toastify";
import { render as renderFromVitest } from "vitest-browser-react";

import { BranchContext } from "../../src/entities/branches/ui/branches-provider";
import { ConfigContext } from "../../src/entities/config/ui/config-provider";
import { store } from "../../src/shared/stores";
import { generateBranch } from "../fake/branch";
import { generateConfig } from "../fake/config";

import "/src/app/styles/index.css";
import "react-toastify/dist/ReactToastify.css";

export const render = (component: React.ReactElement, options = {}) => {
  const currentBranch = generateBranch();
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        // A query with its own retry policy retries at once, so a test doesn't wait on the backoff.
        retryDelay: 0,
        staleTime: 2000,
      },
    },
  });

  return renderFromVitest(component, {
    wrapper: ({ children }) => {
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
                <ConfigContext value={generateConfig()}>
                  <BranchContext value={{ currentBranch, setCurrentBranch: () => {} }}>
                    {children}
                  </BranchContext>
                </ConfigContext>
              </BrowserRouter>
            </QueryClientProvider>
          </Provider>
        </NuqsAdapter>
      );
    },
    ...options,
  });
};
