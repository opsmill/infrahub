import { GraphQLClient } from "graphql-request";
import queryString from "query-string";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryParamProvider } from "use-query-params";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";
import App from "./App";
import { CONFIG } from "./config/config";
import "./index.css";
import reportWebVitals from "./reportWebVitals";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);

// Checking if there's a branch specified in the URL QSP
// If it's present, use that instead of "main"
// Need to do the same for date
const params = new URL(window.location.toString()).searchParams;
const branchInQsp = params.get(CONFIG.QSP_BRANCH);
const dateInQsp = params.get(CONFIG.QSP_DATETIME);
export const graphQLClient = new GraphQLClient(CONFIG.GRAPHQL_URL(branchInQsp ? branchInQsp : "main", dateInQsp ? new Date(dateInQsp) : undefined));

root.render(
  <React.StrictMode>
    <BrowserRouter basename="/">
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}
      >
        <App />
      </QueryParamProvider>
    </BrowserRouter>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
