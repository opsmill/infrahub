import { ApolloProvider } from "@apollo/client";
import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json" with { type: "json" };
import { QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "jotai";
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";
import { ErrorBoundary } from "react-error-boundary";
import { RouterProvider } from "react-router";

import { TanStackQueryDevtools } from "@/app/devtools";
import { router } from "@/app/router";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import { ErrorBoundaryApp } from "@/shared/components/errors/error-boundary-app";
import { store } from "@/shared/stores";

import { AuthProvider } from "@/entities/authentication/ui/useAuth";
import { ConfigProvider } from "@/entities/config/ui/config-provider";
import { ThemeProvider } from "@/entities/theme/ui/theme-provider";

import "@/app/styles/index.css";
import "react-toastify/dist/ReactToastify.css";

addCollection(mdiIcons);

export function App() {
  return (
    <ErrorBoundary FallbackComponent={ErrorBoundaryApp}>
      <NuqsAdapter>
        <Provider store={store}>
          <ThemeProvider>
            <QueryClientProvider client={queryClient}>
              <ApolloProvider client={graphqlClient}>
                <AuthProvider>
                  <ConfigProvider>
                    <RouterProvider router={router} />
                  </ConfigProvider>
                </AuthProvider>
              </ApolloProvider>
              <TanStackQueryDevtools buttonPosition="bottom-left" />
            </QueryClientProvider>
          </ThemeProvider>
        </Provider>
      </NuqsAdapter>
    </ErrorBoundary>
  );
}
