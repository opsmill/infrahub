import "./App.css";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { useEffect } from "react";
import DeviceList from "./screens/device-list/device-list";
import { schemaState } from "./state/atoms/schema.atom";
import { useAtom } from "jotai";
import ObjectItems from "./screens/object-items/object-items";
import Layout from "./screens/layout/layout";
import ObjectItemDetails from "./screens/object-item-details/object-item-details";
import OpsObjects from "./screens/ops-objects/ops-objects";
import { branchState } from "./state/atoms/branch.atom";
import { components } from "./infraops";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";
import ObjectItemEdit from "./screens/object-item-edit/object-item-edit";

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

  useEffect(() => {
    fetch(
      `http://localhost:8000/schema/?branch=${branch ? branch.name : "main"}`
    )
      .then((res) => res.json())
      .then((data: APIResponse) => {
        if (data.nodes.length) {
          setSchema(
            data.nodes.sort((a, b) => {
              if (a.name && b.name) {
                return a.name.localeCompare(b.name);
              }
              return -1;
            })
          );
          setSchemaKindNameState(
            data.nodes
              .map((node) => ({
                name: node.name,
                kind: node.kind,
              }))
              .reduce((acc, value) => {
                return {
                  ...acc,
                  [value.kind]: value.name,
                };
              }, {})
          );
        }
      })
      .catch(() => {
        console.error("Something went wrong when fetching the schema details");
      });
  }, [setSchema, branch, setSchemaKindNameState]);

  return <RouterProvider router={router} />;
}

export default App;
