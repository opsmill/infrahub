import { Provider } from "jotai";
import { ErrorBoundary } from "react-error-boundary";
import { RouterProvider } from "react-router-dom";
import { Slide, ToastContainer } from "react-toastify";

import { ApolloProvider } from "@apollo/client";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { AuthProvider } from "@/hooks/useAuth";
import { router } from "@/router";
import ErrorFallback from "@/screens/errors/error-fallback";
import { store } from "@/state";

import "./styles/index.css";
import "react-toastify/dist/ReactToastify.css";

export function App() {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <AuthProvider>
        <Provider store={store}>
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
        </Provider>
      </AuthProvider>
    </ErrorBoundary>
  );
}
