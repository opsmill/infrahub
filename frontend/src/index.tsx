import { ApolloProvider } from "@apollo/client";
import { useAtom } from "jotai";
import queryString from "query-string";
import { useCallback, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Slide, ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { QueryParamProvider } from "use-query-params";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";
import App from "./App";
import { ALERT_TYPES, Alert } from "./components/alert";
import { CONFIG } from "./config/config";
import SentryClient from "./config/sentry";
import graphqlClient from "./graphql/graphqlClientApollo";
import GET_BRANCHES from "./graphql/queries/branches/getBranches";
import reportWebVitals from "./reportWebVitals";
import { branchesState } from "./state/atoms/branches.atom";
import { Config, configState } from "./state/atoms/config.atom";

import "./styles/index.css";
import { fetchUrl } from "./utils/fetch";

const root = ReactDOM.createRoot(
  (document.getElementById("root") || document.createElement("div")) as HTMLElement
);

const Root = () => {
  const [, setBranches] = useAtom(branchesState);
  const [config, setConfig] = useAtom(configState);

  /**
   * Sentry configuration
   */
  SentryClient(config);

  /**
   * Fetch config from the backend and return it
   */
  const fetchConfig = async () => {
    try {
      return fetchUrl(CONFIG.CONFIG_URL);
    } catch (err) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={"Something went wrong when fetching the config"} />
      );
      console.error("Error while fetching the config: ", err);
      return undefined;
    }
  };

  /**
   * Set config in state atom
   */
  const setConfigInState = useCallback(async () => {
    try {
      const config: Config = await fetchConfig();

      setConfig(config);
    } catch (error) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={"Something went wrong when fetching the config"} />
      );
      console.error("Error while fetching the config: ", error);
    }
  }, [setConfig]);

  useEffect(() => {
    setConfigInState();
  }, [setConfigInState]);

  /**
   * Fetch branches from the backend, sort, and return them
   */
  const fetchBranches = async () => {
    try {
      const { data }: any = await graphqlClient.query({
        query: GET_BRANCHES,
      });

      return data.branch ?? [];
    } catch (err) {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"Something went wrong when fetching the branch details"}
        />
      );
      console.error("Error while fetching branches: ", err);

      return [];
    }
  };

  /**
   * Set branches in state atom
   */
  const setBranchesInState = useCallback(async () => {
    const branches = await fetchBranches();
    setBranches(branches);
  }, [setBranches]);

  useEffect(() => {
    setBranchesInState();
  }, [setBranchesInState]);

  return (
    <BrowserRouter basename="/">
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}>
        <ApolloProvider client={graphqlClient}>
          <App />
          <ToastContainer
            hideProgressBar={true}
            transition={Slide}
            autoClose={5000}
            closeOnClick={false}
            newestOnTop
            position="bottom-right"
          />
        </ApolloProvider>
      </QueryParamProvider>
    </BrowserRouter>
  );
};

root.render(<Root />);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
