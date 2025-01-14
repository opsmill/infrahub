import { Provider } from "jotai";
import { ErrorBoundary } from "react-error-boundary";
import { RouterProvider } from "react-router-dom";
import { Slide, ToastContainer } from "react-toastify";

import { router } from "@/app/router";
import { AuthProvider } from "@/entities/authentication/ui/useAuth";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import ErrorFallback from "@/shared/components/errors/error-fallback";
import { store } from "@/shared/stores";
import { ApolloProvider } from "@apollo/client";
import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import { QueryClientProvider } from "@tanstack/react-query";

import "@/app/styles/index.css";
import "react-toastify/dist/ReactToastify.css";
import { TanStackQueryDevtools } from "@/app/devtools";
import { queryClient } from "@/shared/api/rest/client";

addCollection(mdiIcons);

export function App() {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <Provider store={store}>
        <AuthProvider>
          <QueryClientProvider client={queryClient}>
            <ApolloProvider client={graphqlClient}>
              <ToastContainer
                hideProgressBar={true}
                transition={Slide}
                autoClose={5000}
                closeOnClick={false}
                newestOnTop
                position="bottom-right"
              />
              <RouterProvider router={router} />
            </ApolloProvider>
            <TanStackQueryDevtools buttonPosition="bottom-left" />
          </QueryClientProvider>
        </AuthProvider>
      </Provider>
    </ErrorBoundary>
  );
}
