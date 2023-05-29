import { ApolloProvider, useReactiveVar } from "@apollo/client";
import { useAtom } from "jotai";
import * as R from "ramda";
import React, { useCallback, useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { Slide, ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "./components/alert";
import { CONFIG } from "./config/config";
import { CUSTOM_COMPONENT_ROUTES, MAIN_ROUTES } from "./config/constants";
import { QSP } from "./config/qsp";
import SentryClient from "./config/sentry";
import graphqlClient from "./graphql/graphqlClientApollo";
import GET_BRANCHES from "./graphql/queries/branches/getBranches";
import { branchVar } from "./graphql/variables/branchVar";
import Layout from "./screens/layout/layout";
import SignIn from "./screens/sign-in/sign-in";
import { branchesState } from "./state/atoms/branches.atom";
import { Config, configState } from "./state/atoms/config.atom";
import {
  genericSchemaState,
  genericsState,
  iGenericSchema,
  iGenericSchemaMapping,
  iNodeSchema,
  schemaState,
} from "./state/atoms/schema.atom";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";
import "./styles/index.css";
import { fetchUrl } from "./utils/fetch";

const sortByOrderWeight = R.sortBy(R.compose(R.prop("order_weight")));

// TODO: Use only 1 hook and 1 callback for all 3 requests (branches, schema, config)
function App() {
  const [, setSchema] = useAtom(schemaState);
  const [, setGenerics] = useAtom(genericsState);
  const [, setGenericSchema] = useAtom(genericSchemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [, setBranches] = useAtom(branchesState);
  const [config, setConfig] = useAtom(configState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const branch = useReactiveVar(branchVar);

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
    const config: Config = await fetchConfig();
    setConfig(config);
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

  /**
   * Fetch schema from the backend, sort, and return them
   */
  const fetchSchema = useCallback(async () => {
    const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));
    try {
      const data = await fetchUrl(CONFIG.SCHEMA_URL(branchInQueryString ?? branch?.name));

      return {
        schema: sortByName(data.nodes || []),
        generics: sortByName(data.generics || []),
      };
    } catch (err) {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"Something went wrong when fetching the schema details"}
        />
      );
      console.error("Error while fetching the schema: ", err);
      return {
        schema: [],
        generics: [],
      };
    }
  }, [branch?.name, branchInQueryString]);

  /**
   * Set schema in state atom
   */
  const setSchemaInState = useCallback(async () => {
    const { schema, generics }: { schema: iNodeSchema[]; generics: iGenericSchema[] } =
      await fetchSchema();
    schema.forEach((s) => {
      s.attributes = sortByOrderWeight(s.attributes || []);
      s.relationships = sortByOrderWeight(s.relationships || []);
    });
    setSchema(schema);
    setGenerics(generics);

    const schemaNames = R.map(R.prop("name"), schema);
    const schemaKinds = R.map(R.prop("kind"), schema);
    const schemaKindNameTuples = R.zip(schemaKinds, schemaNames);
    const schemaKindNameMap = R.fromPairs(schemaKindNameTuples);
    setSchemaKindNameState(schemaKindNameMap);

    const genericSchemaMapping: iGenericSchemaMapping = {};
    schema.forEach((schemaNode: any) => {
      if (schemaNode.used_by?.length) {
        genericSchemaMapping[schemaNode.name] = schemaNode.used_by;
      }
    });
    setGenericSchema(genericSchemaMapping);
  }, [fetchSchema, setGenericSchema, setSchema, setSchemaKindNameState, setGenerics]);

  useEffect(() => {
    setSchemaInState();
  }, [setSchemaInState, branch]);

  return (
    <ApolloProvider client={graphqlClient}>
      <Routes>
        <Route path="/signin" element={<SignIn />} />
        <Route path="/" element={<Layout />}>
          {MAIN_ROUTES.map((route) => (
            <Route index key={route.path} path={route.path} element={route.element} />
          ))}

          {CUSTOM_COMPONENT_ROUTES.map((route) => (
            <Route index key={route.path} path={route.path} element={route.element} />
          ))}
        </Route>
      </Routes>
      <ToastContainer
        hideProgressBar={true}
        transition={Slide}
        autoClose={5000}
        closeOnClick={false}
        newestOnTop
        position="bottom-right"
      />
    </ApolloProvider>
  );
}

export default App;
