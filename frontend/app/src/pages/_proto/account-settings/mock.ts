// PROTOTYPE design-jam account-settings — worst-case data, never imported by the app.

export type MockToken = { id: string; name: string; expiration: string | null };

const day = 24 * 60 * 60 * 1000;
const at = (offsetDays: number) => new Date(Date.now() + offsetDays * day).toISOString();

export const MANY_TOKENS: MockToken[] = [
  {
    id: "t1",
    name: "ci-pipeline-github-actions-infrahub-sync-production-eu-west-1-network-automation",
    expiration: null,
  },
  { id: "t2", name: "infrahubctl laptop", expiration: at(180) },
  { id: "t3", name: "ansible-inventory", expiration: at(-12) },
  { id: "t4", name: "nautobot-migration-one-off", expiration: at(-400) },
  { id: "t5", name: "grafana dashboard read", expiration: at(3) },
  { id: "t6", name: "python-sdk-notebook", expiration: null },
  { id: "t7", name: "terraform-provider-staging", expiration: at(30) },
  { id: "t8", name: "netbox-sync", expiration: at(90) },
  { id: "t9", name: "temp", expiration: at(1) },
  { id: "t10", name: "jenkins-legacy-do-not-delete-ask-network-team-first", expiration: null },
  { id: "t11", name: "generator-worker-dc1", expiration: at(365) },
  { id: "t12", name: "generator-worker-dc2", expiration: at(365) },
  { id: "t13", name: "transform-artifacts-render", expiration: at(-2) },
  { id: "t14", name: "observability-exporter", expiration: at(60) },
];

export const LONG_IDENTITY = {
  name: "jean-baptiste.emmanuel.zorg-montgomery",
  label: "Jean-Baptiste Emmanuel Zorg-Montgomery (network-automation-service-account)",
  description: null as string | null,
};

export const FAKE_SECRET = "180f2a1b-6c7e-4b0f-9c1e-8d3f0a9b7e21";

export const tokenSummary = (tokens: MockToken[]) => {
  const now = Date.now();
  const expired = tokens.filter((t) => t.expiration && new Date(t.expiration).getTime() < now);
  const noExpiry = tokens.filter((t) => !t.expiration);
  return { total: tokens.length, expired: expired.length, noExpiry: noExpiry.length };
};
