import { ApolloProvider } from "@apollo/client";
import { useAtom } from "jotai";
import * as R from "ramda";
import { useCallback, useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { StringParam, useQueryParam } from "use-query-params";
import { graphQLClient } from ".";
import { CONFIG } from "./config/config";
import { MAIN_ROUTES } from "./config/constants";
import graphqlClient from "./config/graphqlClient";
import { BRANCH_QUERY, iBranchData } from "./graphql/defined_queries/branch";
import { components } from "./infraops";
import Layout from "./screens/layout/layout";
import { branchState } from "./state/atoms/branch.atom";
import { branchesState } from "./state/atoms/branches.atom";
import { schemaState } from "./state/atoms/schema.atom";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";
type APIResponse = components["schemas"]["SchemaAPI"];

function App() {
  const [, setSchema] = useAtom(schemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [branch] = useAtom(branchState);
  const [, setBranches] = useAtom(branchesState);
  const [branchInQueryString] = useQueryParam(CONFIG.QSP_BRANCH, StringParam);

  /**
   * Fetch branches from the backend, sort, and return them
   */
  const fetchBranches = async () => {
    const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));
    try {
      const data: iBranchData = await graphQLClient.request(BRANCH_QUERY);
      return sortByName(data.branch || []);
    } catch (err) {
      console.error("Something went wrong when fetching the branch details");
      return [];
    }
  };

  /**
   * Fetch schema from the backend, sort, and return them
   */
  const fetchSchema = useCallback(
    async () => {
      const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));
      try {
        const rawResponse = await fetch(CONFIG.SCHEMA_URL(branchInQueryString ?? branch?.name));
        const data = await rawResponse.json();
        return sortByName(data.nodes || []);
      } catch(err) {
        console.error("Something went wrong when fetching the schema details");
        return [];
      }
    },
    [branch?.name, branchInQueryString]
  );

  /**
   * Set schema in state atom
   */
  const setSchemaInState = useCallback(
    async () => {
      const schema: APIResponse["nodes"] = await fetchSchema();
      setSchema(schema);

      const schemaNames = R.map(R.prop("name"), schema);
      const schemaKinds = R.map(R.prop("kind"), schema);
      const schemaKindNameTuples = R.zip(schemaKinds, schemaNames);
      const schemaKindNameMap = R.fromPairs(schemaKindNameTuples);
      setSchemaKindNameState(schemaKindNameMap);
    },
    [fetchSchema, setSchema, setSchemaKindNameState]
  );

  /**
   * Set branches in state atom
   */
  const setBranchesInState = useCallback(
    async () => {
      const branches = await fetchBranches();
      setBranches(branches);
    },
    [setBranches]
  );

  useEffect(
    () => {
      setBranchesInState();
    },
    [setBranchesInState]
  );

  useEffect(
    () => {
      setSchemaInState();
    },
    [setSchemaInState, branch]
  );

  return (
    <ApolloProvider client={graphqlClient}>
      <Routes>
        <Route path="/" element={<Layout />}>
          {MAIN_ROUTES.map((route) => (
            <Route index key={route.path} path={route.path} element={route.element} />
          ))}
        </Route>
      </Routes>
      <ToastContainer closeOnClick={false} />
    </ApolloProvider>
  );
}

export default App;
