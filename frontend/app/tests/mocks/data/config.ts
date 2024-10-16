export const configMocks = {
  main: {
    docs_index_path: "/opt/infrahub/docs/build/search-index.json",
    internal_address: "http://infrahub-server:8000",
    allow_anonymous_access: true,
    telemetry_optout: false,
    telemetry_endpoint: "https://telemetry.opsmill.cloud/infrahub",
    telemetry_interval: 86400,
    permission_backends: ["infrahub.permissions.LocalPermissionBackend"],
  },
  logging: {
    remote: {
      enable: false,
      frontend_dsn: null,
      api_server_dsn: null,
      git_agent_dsn: null,
    },
  },
  analytics: {
    enable: true,
    address: null,
    api_key: null,
  },
  experimental_features: {
    pull_request: false,
    graphql_enums: false,
  },
  sso: {
    providers: [],
    enabled: false,
  },
};
