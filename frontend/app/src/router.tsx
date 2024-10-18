import { Root } from "@/Root";
import { NODE_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { RequireAuth } from "@/hooks/useAuth";
import { constructPathForIpam } from "@/screens/ipam/common/utils";
import { IPAM_ROUTE, IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/screens/ipam/constants";
import { RESOURCE_GENERIC_KIND } from "@/screens/resource-manager/constants";
import { constructPath } from "@/utils/fetch";
import queryString from "query-string";
import { Navigate, Outlet, UIMatch, createBrowserRouter } from "react-router-dom";
import { QueryParamProvider } from "use-query-params";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";

export const router = createBrowserRouter([
  {
    path: "",
    element: (
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}
      >
        <Root>
          <Outlet />
        </Root>
      </QueryParamProvider>
    ),
    children: [
      {
        path: "",
        element: (
          <RequireAuth>
            <Outlet />
          </RequireAuth>
        ),
        children: [
          {
            path: "/",
            lazy: () => import("@/screens/layout/layout"),
            children: [
              {
                index: true,
                lazy: () => import("@/pages/homepage"),
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
                path: "/objects",
                lazy: () => import("@/pages/objects/layout"),
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
                        index: true,
                        lazy: () => import("@/pages/objects/object-items"),
                      },
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
                path: IPAM_ROUTE.INDEX,
                lazy: () => import("@/pages/ipam/layout"),
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "IP Address Manager",
                      to: constructPathForIpam("/ipam"),
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/screens/ipam/ipam-router"),
                  },
                  {
                    path: IPAM_ROUTE.ADDRESSES,
                    lazy: () => import("@/screens/ipam/ipam-router"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "IP Addresses",
                          to: constructPathForIpam("/ipam/addresses"),
                        };
                      },
                    },
                    children: [
                      {
                        path: ":ip_address",
                        lazy: () => import("@/screens/ipam/ipam-router"),
                        handle: {
                          breadcrumb: (match: UIMatch) => {
                            return {
                              type: "select",
                              value: match.params.ip_address,
                              kind: IP_ADDRESS_GENERIC,
                            };
                          },
                        },
                      },
                    ],
                  },
                  {
                    path: IPAM_ROUTE.PREFIXES,
                    lazy: () => import("@/screens/ipam/ipam-router"),
                    handle: {
                      breadcrumb: () => {
                        return {
                          type: "link",
                          label: "IP Prefixes",
                          to: constructPathForIpam("/ipam/prefixes"),
                        };
                      },
                    },
                    children: [
                      {
                        path: ":prefix",
                        lazy: () => import("@/screens/ipam/ipam-router"),
                        handle: {
                          breadcrumb: (match: UIMatch) => {
                            return {
                              type: "select",
                              value: match.params.prefix,
                              kind: IP_PREFIX_GENERIC,
                            };
                          },
                        },
                        children: [
                          {
                            path: ":ip_address",
                            lazy: () => import("@/screens/ipam/ipam-router"),
                            handle: {
                              breadcrumb: (match: UIMatch) => {
                                return {
                                  type: "select",
                                  value: match.params.ip_address,
                                  kind: IP_ADDRESS_GENERIC,
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
                path: "role-management",
                lazy: () => import("@/pages/role-management"),
                handle: {
                  breadcrumb: () => {
                    return {
                      type: "link",
                      label: "Role Management",
                      to: constructPath("/role-management"),
                    };
                  },
                },
                children: [
                  {
                    index: true,
                    lazy: () => import("@/screens/role-management/accounts"),
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
                    lazy: () => import("@/screens/role-management/groups"),
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
                    lazy: () => import("@/screens/role-management/roles"),
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
                    lazy: () => import("@/screens/role-management/global-permissions"),
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
                    lazy: () => import("@/screens/role-management/object-permissions"),
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
