import { RouterProvider } from "react-aria-components";
import {
  createBrowserRouter,
  Navigate,
  type NavigateOptions,
  Outlet,
  type To,
  type UIMatch,
  useHref,
  useNavigate,
} from "react-router";
import { Slide, ToastContainer } from "react-toastify";

import { ARTIFACT_OBJECT, NODE_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";

import { constructPath } from "@/shared/api/rest/fetch";
import { ErrorBoundaryRouter } from "@/shared/components/errors/error-boundary-router";
import type { BreadcrumbItem } from "@/shared/components/layout/breadcrumb-navigation/type";

import { RequireAuth } from "@/entities/authentication/ui/require-auth";
import { BranchesProvider } from "@/entities/branches/ui/branches-provider";
import { constructPathForIpam } from "@/entities/ipam/utils";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
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
                lazy: () => import("@/pages/home/homepage"),
              },
              {
                path: "/branches",
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Branches",
                      to: constructPath("/branches"),
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/branches"),
                  },
                  {
                    path: "*",
                    lazy: () => import("@/pages/branches/details"),
                    handle: {
                      breadcrumb: (match: UIMatch) => {
                        return {
                          type: "branch",
                          value: match.params["*"],
                        };
                      },
                    },
                  },
                ],
              },
              {
                path: "/activities",
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Activities",
                      to: constructPath("/activities"),
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/activities"),
                  },
                  {
                    path: ":activityId",
                    lazy: () => import("@/pages/activities/details"),
                    handle: {
                      breadcrumb: (match: UIMatch) => {
                        return {
                          type: "id",
                          value: match.params.activityId,
                          link: "/activities",
                        };
                      },
                    },
                  },
                ],
              },
              {
                path: `/objects/${ARTIFACT_OBJECT}/:artifactId`,
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "select",
                      value: ARTIFACT_OBJECT,
                      kind: "schema",
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/objects/CoreArtifact/artifact-details"),
                    handle: {
                      breadcrumb: (match: UIMatch) => {
                        return {
                          type: "select",
                          value: match.params.artifactId,
                          kind: ARTIFACT_OBJECT,
                        };
                      },
                    },
                  },
                ],
              },
              {
                path: "/objects",
                children: [
                  {
                    path: ":objectKind",
                    handle: {
                      breadcrumb: (match: UIMatch) => {
                        return {
                          type: "select",
                          value: match.params.objectKind,
                          kind: "schema",
                        };
                      },
                    },
                    children: [
                      {
                        path: ":objectId",
                        handle: {
                          breadcrumb: (match: UIMatch) => ({
                            type: "select",
                            value: match.params.objectId,
                            kind: match.params.objectKind,
                          }),
                        },
                        children: [
                          {
                            path: "convert",
                            lazy: () => import("@/pages/objects/object-convert"),
                            handle: {
                              breadcrumb: (match: UIMatch) =>
                                ({
                                  type: "link",
                                  label: "Convert",
                                  to: constructPath(
                                    `/objects/${match.params.objectKind}/${match.params.objectid}/convert`
                                  ),
                                }) satisfies BreadcrumbItem,
                            },
                          },
                        ],
                      },
                      {
                        lazy: () => import("@/pages/objects/layout"),
                        children: [
                          {
                            index: true,
                            lazy: () => import("@/pages/objects/object-items"),
                          },
                          {
                            path: ":objectid",
                            handle: {
                              breadcrumb: (match: UIMatch) => ({
                                type: "select",
                                value: match.params.objectid,
                                kind: match.params.objectKind,
                              }),
                            },
                            children: [
                              {
                                index: true,
                                lazy: () => import("@/pages/objects/object-details"),
                              },
                              {
                                path: "convert",
                                lazy: () => import("@/pages/objects/object-convert"),
                                handle: {
                                  breadcrumb: (match: UIMatch) =>
                                    ({
                                      type: "link",
                                      label: "Convert",
                                      to: constructPath(
                                        `/objects/${match.params.objectKind}/${match.params.objectid}/convert`
                                      ),
                                    }) satisfies BreadcrumbItem,
                                },
                              },
                            ],
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
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Account settings",
                      to: constructPath("/profile"),
                    };
                  },
                },
              },
              {
                path: "/proposed-changes",
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Proposed changes",
                      to: constructPath("/proposed-changes"),
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/proposed-changes/items"),
                  },
                  {
                    path: "new",
                    lazy: () => import("@/pages/proposed-changes/new"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "new",
                          to: constructPath("/proposed-changes/new"),
                        };
                      },
                    },
                  },
                  {
                    path: ":proposedChangeId",
                    lazy: () => import("@/pages/proposed-changes/details"),
                    handle: {
                      breadcrumb: (match: UIMatch) => {
                        return {
                          type: "select",
                          value: match.params.proposedChangeId,
                          kind: PROPOSED_CHANGES_OBJECT,
                        };
                      },
                    },
                  },
                ],
              },
              {
                path: "/tasks",
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Tasks",
                      to: constructPath("/tasks"),
                    };
                  },
                },
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
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "GraphQL Sandbox",
                      to: constructPath("/graphql"),
                    };
                  },
                },
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
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Resource manager",
                      to: constructPath("/resource-manager"),
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/pages/resource-manager"),
                  },
                  {
                    path: ":resourcePoolId",
                    lazy: () => import("@/pages/resource-manager/resource-pool-details"),
                    handle: {
                      breadcrumb: (match: UIMatch) => {
                        return {
                          type: "select",
                          value: match.params.resourcePoolId,
                          kind: RESOURCE_GENERIC_KIND,
                        };
                      },
                    },
                    children: [
                      {
                        path: "resources/:resourceId",
                        lazy: () => import("@/pages/resource-manager/resource-allocation-details"),
                        handle: {
                          breadcrumb: (match: UIMatch) => {
                            return {
                              type: "select",
                              value: match.params.resourceId,
                              kind: NODE_OBJECT,
                            };
                          },
                        },
                      },
                    ],
                  },
                ],
              },
              {
                path: "/schema",
                lazy: () => import("@/pages/schema"),
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Schema",
                      to: constructPath("/schema"),
                    };
                  },
                },
              },
              {
                path: "ipam",
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "IP Address Manager",
                      to: constructPathForIpam("/ipam"),
                    } as BreadcrumbItem;
                  },
                },
                children: [
                  {
                    path: "namespaces",
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "namespaces",
                          to: constructPath("/ipam/namespaces"),
                        } satisfies BreadcrumbItem;
                      },
                    },
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
                            path: ":objectid",
                            lazy: () => import("@/pages/objects/object-details"),
                            handle: {
                              breadcrumb: (match: UIMatch) => {
                                return {
                                  type: "select",
                                  value: match.params.objectid,
                                  kind: match.params.objectKind,
                                };
                              },
                            },
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
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "IP Address Manager",
                      to: constructPathForIpam("/ipam"),
                    } as BreadcrumbItem;
                  },
                },
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
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Users & Permissions",
                      to: constructPath("/role-management"),
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/entities/role-manager/ui/accounts"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "Accounts",
                          to: constructPath("/role-management/accounts"),
                        };
                      },
                    },
                  },
                  {
                    path: "groups",
                    lazy: () => import("@/entities/role-manager/ui/groups"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "Groups",
                          to: constructPath("/role-management/groups"),
                        };
                      },
                    },
                  },
                  {
                    path: "roles",
                    lazy: () => import("@/entities/role-manager/ui/roles"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "Roles",
                          to: constructPath("/role-management/roles"),
                        };
                      },
                    },
                  },
                  {
                    path: "global-permissions",
                    lazy: () => import("@/entities/role-manager/ui/global-permissions"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "Global Permissions",
                          to: constructPath("/role-management/global-permissions"),
                        };
                      },
                    },
                  },
                  {
                    path: "object-permissions",
                    lazy: () => import("@/entities/role-manager/ui/object-permissions"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "Object Permissions",
                          to: constructPath("/role-management/object-permissions"),
                        };
                      },
                    },
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
