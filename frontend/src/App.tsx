import "./App.css";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { useEffect } from "react";
import DeviceList from "./screens/device-list/device-list";
import { schemaState } from "./state/atoms/schema.atom";
import { useAtom } from "jotai";
import { graphQLClient } from ".";
import { iSchemaData, SCHEMA_QUERY } from "./graphql/queries/schema";
import ObjectItems from "./screens/object-items/object-items";
import Layout from "./screens/layout/layout";
import ObjectItemDetails from "./screens/object-item-details/object-item-details";
import OpsObjects from "./screens/ops-objects/ops-objects";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
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

  useEffect(() => {
    const request = graphQLClient.request(SCHEMA_QUERY);
    request
      .then((data: iSchemaData) => {
        if (data.node_schema?.length) {
          setSchema(
            data.node_schema.sort((a, b) => {
              if (a.name.value && b.name.value) {
                return a.name.value?.localeCompare(b.name.value);
              }
              return -1;
            })
          );
        }
      })
      .catch(() => {
        console.error("Something went wrong when fetching the schema details");
      });
  }, [setSchema]);

  return <RouterProvider router={router} />;
}

export default App;
