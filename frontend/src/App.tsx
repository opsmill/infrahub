import { useAtom } from "jotai";
import * as R from "ramda";
import { useCallback, useEffect } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./App.css";
import { CONFIG } from "./config/config";
import { components } from "./infraops";
import DeviceList from "./screens/device-list/device-list";
import Layout from "./screens/layout/layout";
import ObjectItemDetails from "./screens/object-item-details/object-item-details";
import ObjectItemEdit from "./screens/object-item-edit/object-item-edit";
import ObjectItems from "./screens/object-items/object-items";
import OpsObjects from "./screens/ops-objects/ops-objects";
import { branchState } from "./state/atoms/branch.atom";
import { schemaState } from "./state/atoms/schema.atom";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";

type APIResponse = components["schemas"]["SchemaAPI"];

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      {
        path: "/objects/:objectname/:objectid/edit",
        element: <ObjectItemEdit />,
      },
      {
        path: "/objects/:objectname/:objectid",
        element: <ObjectItemDetails />,
      },
      {
        path: "/objects/:objectname",
        element: <ObjectItems />,
      },
      {
        path: "/schema",
        element: <OpsObjects />,
      },
      {
        path: "/devices",
        element: <DeviceList />,
      },
    ],
  },
]);

export function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

function App() {
  const [, setSchema] = useAtom(schemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [branch] = useAtom(branchState);

  /**
   * Fetch schema from the backend, sort, and return them
   */
  const fetchSchema = useCallback(async () => {
    const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));
    try {
      const rawResponse = await fetch(CONFIG.SCHEMA_URL(branch?.name));
      const data = await rawResponse.json();
      return sortByName(data.nodes || []);
    } catch(err) {
      console.error("Something went wrong when fetching the schema details");
      return [];
    }
  }, [branch])

  /**
   * Set schema in state atom
   */
  const setSchemaInState = useCallback(async () => {
    const schema: APIResponse["nodes"] = await fetchSchema();
    setSchema(schema);
    const schemaNames = R.map(R.prop("name"), schema);
    const schemaKinds = R.map(R.prop("kind"), schema);
    const schemaKindNameTuples = R.zip(schemaKinds, schemaNames);
    const schemaKindNameMap = R.fromPairs(schemaKindNameTuples);
    setSchemaKindNameState(schemaKindNameMap);
  }, [fetchSchema, setSchema, setSchemaKindNameState]);

  useEffect(() => {
    setSchemaInState();
  }, [setSchemaInState, branch]);

  return <RouterProvider router={router} />;
}

export default App;
