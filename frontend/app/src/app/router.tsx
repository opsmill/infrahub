import { RouterProvider } from "react-aria-components";
import {
  createBrowserRouter,
  Navigate,
  type NavigateOptions,
  Outlet,
  type To,
  useHref,
  useNavigate,
} from "react-router";
import { Slide, ToastContainer } from "react-toastify";

import { ARTIFACT_OBJECT } from "@/config/constants";

import { ErrorBoundaryRouter } from "@/shared/components/errors/error-boundary-router";

import { RequireAuth } from "@/entities/authentication/ui/require-auth";
import { BranchesProvider } from "@/entities/branches/ui/branches-provider";
import { SchemaProvider } from "@/entities/schema/ui/providers/schema-provider";

declare module "react-aria-components" {
  interface RouterConfig {
    href: To;
    routerOptions: NavigateOptions;
  }
}

function useAbsoluteHref(path: To) {
  const relative = useHref(path);
  if (
    typeof path === "string" &&
    (path.startsWith("https://") || path.startsWith("http://") || path.startsWith("mailto:"))
  ) {
    return path;
  }
  return relative;
}

function RootProviders({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();

  return (
    <RouterProvider navigate={navigate} useHref={useAbsoluteHref}>
      <ToastContainer
        hideProgressBar={true}
        transition={Slide}
        autoClose={5000}
        closeOnClick={false}
        newestOnTop
        position="bottom-right"
      />
      {children}
    </RouterProvider>
  );
}

export const router = createBrowserRouter([
  {
    path: "",
    errorElement: <ErrorBoundaryRouter />,
    element: (
      <RootProviders>
        <Outlet />
      </RootProviders>
    ),
    children: [
      {
        path: "",
        element: (
          <RequireAuth>
            <BranchesProvider>
              <SchemaProvider>
                <Outlet />
              </SchemaProvider>
            </BranchesProvider>
          </RequireAuth>
        ),
        children: [
          {
            path: "/",
            lazy: () => import("@/shared/components/layout/app-layout"),
            children: [
              {
                index: true,
                lazy: () => import("@/pages/homepage"),
              },
              {
                path: "/branches",
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/branches"),
                  },
                  {
                    path: "*",
                    lazy: () => import("@/pages/branches/details"),
                  },
                ],
              },
              {
                path: "/activities",
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/activities"),
                  },
                  {
                    path: ":activityId",
                    lazy: () => import("@/pages/activities/details"),
                  },
                ],
              },
              {
                path: "/objects",
                children: [
                  {
                    path: `${ARTIFACT_OBJECT}/:artifactId`,
                    children: [
                      {
                        index: true,
                        lazy: () => import("@/pages/objects/CoreArtifact/artifact-details"),
                      },
                    ],
                  },
                  {
                    path: ":objectKind",
                    lazy: () => import("@/pages/objects/layout"),
                    children: [
                      {
                        index: true,
                        lazy: () => import("@/pages/objects/object-items"),
                      },
                      {
                        path: ":objectId",
                        children: [
                          {
                            index: true,
                            lazy: () => import("@/pages/objects/object-details-page"),
                          },
                          {
                            path: "convert",
                            lazy: () => import("@/pages/objects/object-convert"),
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                path: "/profile",
                lazy: () => import("@/pages/profile"),
              },
              {
                path: "/proposed-changes",
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/proposed-changes/items"),
                  },
                  {
                    path: "new",
                    lazy: () => import("@/pages/proposed-changes/new"),
                  },
                  {
                    path: ":proposedChangeId",
                    lazy: () => import("@/pages/proposed-changes/details"),
                  },
                ],
              },
              {
                path: "/tasks",
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/tasks"),
                  },
                  {
                    path: ":task",
                    lazy: () => import("@/pages/tasks/task-details"),
                  },
                ],
              },
              {
                path: "graphql",
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/graphql"),
                  },
                  {
                    path: ":branch",
                    lazy: () => import("@/pages/graphql/redirect-to-graphql-sandbox-page"),
                  },
                ],
              },
              {
                path: "/resource-manager",
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/resource-manager"),
                  },
                  {
                    path: ":resourcePoolId",
                    lazy: () => import("@/pages/resource-manager/resource-pool-details"),
                    children: [
                      {
                        path: "resources/:resourceId",
                        lazy: () => import("@/pages/resource-manager/resource-allocation-details"),
                      },
                    ],
                  },
                ],
              },
              {
                path: "/schema",
                lazy: () => import("@/pages/schema"),
              },
              {
                path: "ipam",
                children: [
                  {
                    path: "namespaces",
                    children: [
                      {
                        index: true,
                        lazy: () => import("@/pages/ipam/ipam-namespace-list-page"),
                      },
                      {
                        path: ":objectKind",
                        lazy: () => import("@/pages/objects/layout"),
                        children: [
                          {
                            path: ":objectId",
                            lazy: () => import("@/pages/objects/object-details-page"),
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                path: "ipam",
                lazy: () => import("@/pages/ipam/ipam-layout"),
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/ipam/ipam-ip-prefixes-list-page"),
                  },
                  {
                    path: "ip_prefixes",
                    lazy: () => import("@/pages/ipam/ipam-ip-prefixes-list-page"),
                  },
                  {
                    path: "ip_addresses",
                    lazy: () => import("@/pages/ipam/ipam-ip-addresses-list-page"),
                  },
                  {
                    path: ":objectKind/:objectId",
                    lazy: () => import("@/pages/ipam/ipam-details-layout"),
                    children: [
                      {
                        index: true,
                        lazy: () => import("@/pages/ipam/ipam-details-index-page"),
                      },
                      {
                        path: ":relationshipName",
                        lazy: () => import("@/pages/ipam/ipam-details-relationship-page"),
                      },
                      {
                        path: "details",
                        lazy: () => import("@/pages/ipam/ipam-details-page"),
                      },
                    ],
                  },
                ],
              },
              {
                path: "role-management",
                lazy: () => import("@/pages/role-management"),
                children: [
                  {
                    index: true,
                    lazy: () => import("@/entities/role-manager/ui/accounts"),
                  },
                  {
                    path: "groups",
                    lazy: () => import("@/entities/role-manager/ui/groups"),
                  },
                  {
                    path: "roles",
                    lazy: () => import("@/entities/role-manager/ui/roles"),
                  },
                  {
                    path: "global-permissions",
                    lazy: () => import("@/entities/role-manager/ui/global-permissions"),
                  },
                  {
                    path: "object-permissions",
                    lazy: () => import("@/entities/role-manager/ui/object-permissions"),
                  },
                ],
              },
              {
                path: "*",
                element: <Navigate to="/" />,
              },
            ],
          },
          {
            path: "*",
            element: <Navigate to="/" />,
          },
        ],
      },
      {
        path: "/login",
        lazy: () => import("@/pages/login"),
      },
      {
        path: "auth/:protocol/:provider/callback",
        lazy: () => import("@/pages/auth-callback"),
      },
    ],
  },
]);
