import * as Sentry from "@sentry/react";
import { BrowserTracing } from "@sentry/tracing";
import { useAtom } from "jotai";
import * as R from "ramda";
import { useCallback, useEffect } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { graphQLClient } from ".";
import "./App.css";
import { CONFIG } from "./config/config";
import { MAIN_ROUTES } from "./config/constants";
import { BRANCH_QUERY, iBranchData } from "./graphql/defined_queries/branch";
import { components } from "./infraops";
import { branchState } from "./state/atoms/branch.atom";
import { branchesState } from "./state/atoms/branches.atom";
import { schemaState } from "./state/atoms/schema.atom";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";

type APIResponse = components["schemas"]["SchemaAPI"];

const router = createBrowserRouter(MAIN_ROUTES);

Sentry.init({
  dsn: "https://c271c704fe5a43b3b08c83919f0d8e01@o4504893920247808.ingest.sentry.io/4504893931520000",
  integrations: [
    new BrowserTracing(
    //   {
    //   tracePropagationTargets: ["localhost"],
    //   // ... other options
    // }
    ),
    new Sentry.Replay()
  ],
});

Sentry.setContext("character", {
  name: "Mighty Fighter",
  age: 19,
  attack_type: "melee",
});

Sentry.configureScope(scope => scope.setTransactionName("MainApp"));

function App() {
  const [, setSchema] = useAtom(schemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [branch] = useAtom(branchState);
  const [, setBranches] = useAtom(branchesState);

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
        const rawResponse = await fetch(CONFIG.SCHEMA_URL(branch?.name));
        const data = await rawResponse.json();
        return sortByName(data.nodes || []);
      } catch(err) {
        console.error("Something went wrong when fetching the schema details");
        return [];
      }
    },
    [branch]
  )

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

  return <RouterProvider router={router} />;
}

export default App;
