import { ApolloProvider } from "@apollo/client";
import { useAtom, useSetAtom } from "jotai";
import queryString from "query-string";
import { useEffect, useState } from "react";
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
import { branchesState, currentBranchAtom } from "./state/atoms/branches.atom";
import { Config, configState } from "./state/atoms/config.atom";

import LoadingScreen from "./screens/loading-screen/loading-screen";
import "./styles/index.css";
import { fetchUrl, getCurrentQsp } from "./utils/fetch";
import {
  genericsState,
  iGenericSchema,
  iNamespace,
  iNodeSchema,
  namespacesState,
  schemaFamily,
  schemaState,
  SchemaSummary,
  schemaSummaryAtom,
} from "./state/atoms/schema.atom";
import { sortByOrderWeight } from "./utils/common";
import * as R from "ramda";
import { QSP } from "./config/qsp";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";
import { Branch } from "./generated/graphql";

const root = ReactDOM.createRoot(
  (document.getElementById("root") || document.createElement("div")) as HTMLElement
);

export const Root = () => {
  const setBranches = useSetAtom(branchesState);
  const setCurrentBranch = useSetAtom(currentBranchAtom);
  const [config, setConfig] = useAtom(configState);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);
  const [isLoadingBranches, setIsLoadingBranches] = useState(true);

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
  const setConfigInState = async () => {
    try {
      setIsLoadingConfig(true);
      const config: Config = await fetchConfig();

      setConfig(config);
      setIsLoadingConfig(false);
    } catch (error: any) {
      setIsLoadingConfig(false);

      if (error?.message?.includes("Received status code 401")) {
        return;
      }

      toast(
        <Alert type={ALERT_TYPES.ERROR} message={"Something went wrong when fetching the config"} />
      );
      console.error("Error while fetching the config: ", error);
    }
  };

  /**
   * Fetch branches from the backend, sort, and return them
   */
  const fetchBranches = async () => {
    try {
      const { data }: any = await graphqlClient.query({
        query: GET_BRANCHES,
      });

      return data.Branch ?? [];
    } catch (err: any) {
      console.log("err.message: ", err.message);

      if (err?.message?.includes("Received status code 401")) {
        return [];
      }

      console.error("Error while fetching branches: ", err);

      return [];
    }
  };

  /**
   * Set branches in state atom
   */
  const setBranchesInState = async () => {
    const branches = await fetchBranches();
    setBranches(branches);

    const branchInQueryString = getCurrentQsp().get(QSP.BRANCH);
    const filter = branchInQueryString
      ? (b: Branch) => branchInQueryString === b.name
      : (b: Branch) => b.is_default;
    const selectedBranch = branches.find(filter);
    setCurrentBranch(selectedBranch ?? null);
    setIsLoadingBranches(false);
  };

  useEffect(() => {
    setConfigInState();
    setBranchesInState();
  }, []);

  if (isLoadingConfig || isLoadingBranches) {
    // Loading screen while loading the token from the local storage
    return (
      <div className="w-screen h-screen flex ">
        <LoadingScreen />;
      </div>
    );
  }

  return <AppInitializer />;
};

const AppInitializer = () => {
  const setGenerics = useSetAtom(genericsState);
  const setNamespaces = useSetAtom(namespacesState);
  const setSchema = useSetAtom(schemaState);
  const setSchemaKindNameState = useSetAtom(schemaKindNameState);
  const setCurrentSchemaHash = useSetAtom(schemaSummaryAtom);
  const [isSchemaLoading, setSchemaLoading] = useState(true);
  const [isSchemaSummaryLoading, setSchemaSummaryLoading] = useState(true);

  const branchInQueryString = getCurrentQsp().get(QSP.BRANCH);

  const fetchAndSetSchema = async () => {
    try {
      const schemaData: {
        main: string;
        nodes: iNodeSchema[];
        generics: iGenericSchema[];
        namespaces: iNamespace[];
      } = await fetchUrl(CONFIG.SCHEMA_URL(branchInQueryString));

      const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));
      const schema: iNodeSchema[] = sortByName(schemaData.nodes || []);
      const generics: iGenericSchema[] = sortByName(schemaData.generics || []);
      const namespaces: iNamespace[] = sortByName(schemaData.namespaces || []);

      schema.forEach((s) => {
        s.attributes = sortByOrderWeight(s.attributes || []);
        s.relationships = sortByOrderWeight(s.relationships || []);
        schemaFamily(s);
      });

      generics.forEach((g) => {
        schemaFamily(g);
      });

      const schemaKindNameMap = schema.reduce(
        (kindNameMap: Record<string, string>, { name, kind }) => ({
          ...kindNameMap,
          [kind as string]: name,
        }),
        {}
      );

      setGenerics(generics);
      setSchema(schema);
      setSchemaKindNameState(schemaKindNameMap);
      setNamespaces(namespaces);
      setSchemaLoading(false);
    } catch (error) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the schema" />
      );

      console.error("Error while fetching the schema: ", error);
    }
  };

  const fetchAndSetSchemaSummary = async () => {
    try {
      const schemaSummary: SchemaSummary = await fetchUrl(
        CONFIG.SCHEMA_SUMMARY_URL(branchInQueryString)
      );

      setCurrentSchemaHash(schemaSummary);
      setSchemaSummaryLoading(false);
    } catch (error) {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message="Something went wrong when fetching the schema summary"
        />
      );

      console.error("Error while fetching the schema summary: ", error);
    }
  };

  useEffect(() => {
    fetchAndSetSchema();
    fetchAndSetSchemaSummary();
  }, []);

  if (isSchemaLoading || isSchemaSummaryLoading) {
    return (
      <div className="w-screen h-screen flex ">
        <LoadingScreen />;
      </div>
    );
  }

  return <App />;
};

root.render(
  <BrowserRouter basename="/">
    <QueryParamProvider
      adapter={ReactRouter6Adapter}
      options={{
        searchStringToObject: queryString.parse,
        objectToSearchString: queryString.stringify,
      }}>
      <ApolloProvider client={graphqlClient}>
        <ToastContainer
          hideProgressBar={true}
          transition={Slide}
          autoClose={5000}
          closeOnClick={false}
          newestOnTop
          position="bottom-right"
        />
        <Root />
      </ApolloProvider>
    </QueryParamProvider>
  </BrowserRouter>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
