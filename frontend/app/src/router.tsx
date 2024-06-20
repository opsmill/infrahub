import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";
import queryString from "query-string";
import { QueryParamProvider } from "use-query-params";
import { RequireAuth } from "@/hooks/useAuth";
import { IPAM_ROUTE } from "@/screens/ipam/constants";
import { ARTIFACT_OBJECT, GRAPHQL_QUERY_OBJECT } from "@/config/constants";
import Layout from "@/screens/layout/layout";

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}>
        <RequireAuth>
          <Layout>
            <Outlet />
          </Layout>
        </RequireAuth>
      </QueryParamProvider>
    ),
    children: [
      {
        path: "/branches/:branchName",
        lazy: () => import("@/screens/branches/branch-item-details"),
      },
      {
        path: "/branches",
        lazy: () => import("@/screens/branches/branches-items"),
      },
      {
        path: `/objects/${ARTIFACT_OBJECT}/:objectid`,
        lazy: () => import("@/screens/artifacts/object-item-details-paginated"),
      },
      {
        path: `/objects/${GRAPHQL_QUERY_OBJECT}/:graphqlQueryId`,
        lazy: () => import("@/screens/graphql/details/graphql-query-details-page"),
      },
      {
        path: "/objects/:objectname/:objectid",
        lazy: () => import("@/screens/object-item-details/object-item-details-paginated"),
      },
      {
        path: "/objects/:objectname",
        lazy: () => import("@/screens/object-items/object-items-paginated"),
      },
      {
        path: "/profile",
        lazy: () => import("@/screens/user-profile/user-profile"),
      },
      {
        path: "/proposed-changes/new",
        lazy: () => import("@/screens/proposed-changes/proposed-changes-create-page"),
      },
      {
        path: "/proposed-changes/:proposedchange",
        lazy: () => import("@/screens/proposed-changes/proposed-changes-details"),
      },
      {
        path: "/proposed-changes",
        lazy: () => import("@/screens/proposed-changes/proposed-changes-items"),
      },
      {
        path: "/tasks/:task",
        lazy: () => import("@/screens/tasks/task-item-details-screen"),
      },
      {
        path: "/tasks",
        lazy: () => import("@/screens/tasks/task-items-screen"),
      },
      {
        path: "/graphql/:branch",
        lazy: () => import("@/screens/graphql/redirect-to-graphql-sandbox-page"),
      },
      {
        path: "graphql",
        lazy: () => import("@/screens/graphql/graphql-sandbox-page"),
      },
      {
        path: "/resource-manager",
        lazy: () => import("@/screens/resource-manager/resource-manager-page"),
      },
      {
        path: "/resource-manager/:resourcePoolId",
        lazy: () => import("@/screens/resource-manager/resource-pool-page"),
        children: [
          {
            path: "resources/:resourceId",
            lazy: () => import("@/screens/resource-manager/resource-allocation-page"),
          },
        ],
      },
      {
        path: "/schema",
        lazy: () => import("@/screens/schema/schema-page"),
      },
      {
        path: IPAM_ROUTE.INDEX,
        lazy: () => import("@/screens/ipam/ipam-page"),
        children: [
          {
            index: true,
            lazy: () => import("@/screens/ipam/ipam-router"),
          },
          {
            path: IPAM_ROUTE.ADDRESSES,
            lazy: () => import("@/screens/ipam/ipam-router"),
            children: [
              {
                path: ":ip_address",
                lazy: () => import("@/screens/ipam/ipam-router"),
              },
            ],
          },
          {
            path: IPAM_ROUTE.PREFIXES,
            lazy: () => import("@/screens/ipam/ipam-router"),
            children: [
              {
                path: ":prefix",
                lazy: () => import("@/screens/ipam/ipam-router"),
                children: [
                  {
                    path: ":ip_address",
                    lazy: () => import("@/screens/ipam/ipam-router"),
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        path: "/",
        lazy: () => import("@/screens/homepage"),
      },
      {
        path: "*",
        element: <Navigate to="/" />,
      },
    ],
  },
  {
    path: "/signin",
    lazy: () => import("@/screens/sign-in/sign-in"),
  },
]);
