import type { Config } from "@/entities/config/domain/model/config";

export const generateConfig = (overrides: Partial<Config> = {}): Config => ({
  main: {
    docs_index_path: "/opt/infrahub/docs/search-index.json",
    internal_address: "http://infrahub-server:8000",
    allow_anonymous_access: true,
    anonymous_access_role: "Anonymous User",
    telemetry_optout: false,
    telemetry_endpoint: "https://telemetry.opsmill.cloud/infrahub",
    permission_backends: ["infrahub.permissions.LocalPermissionBackend"],
    public_url: null,
    schema_strict_mode: true,
    diff_update_after_merge: true,
    delete_branch_after_merge: false,
    selective_execution_after_merge: true,
    merge_failure_grace_period_seconds: 60,
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
    enable: false,
    address: null,
    api_key: null,
  },
  experimental_features: {
    graphql_enums: false,
    value_db_index: false,
  },
  sso: {
    providers: [],
    enabled: false,
  },
  ldap: {
    enabled: false,
    display_label: "LDAP",
    icon: "mdi:account-key",
  },
  installation_type: "community",
  policy: {
    required_proposed_change_approvals: 0,
    revoke_proposed_change_approvals: false,
  },
  instance: {
    label: null,
    color: null,
  },
  ...overrides,
});

export const generateConfigWithInstance = (
  label: Config["instance"]["label"],
  color: Config["instance"]["color"]
): Config => generateConfig({ instance: { label, color } });
