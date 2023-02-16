import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import {
  ApolloClient,
  HttpLink,
  InMemoryCache,
  ApolloProvider,
} from "@apollo/client";
import { CONFIG } from "./config/config";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);

const httpLink = new HttpLink({ uri: CONFIG.BACKEND_URL });
const graphQLclient = new ApolloClient({
  cache: new InMemoryCache({ addTypename: true }),
  link: httpLink,
});

root.render(
  <React.StrictMode>
    <ApolloProvider client={graphQLclient}>
      <App />
    </ApolloProvider>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
