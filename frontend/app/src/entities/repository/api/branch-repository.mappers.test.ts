import { describe, expect, it } from "vitest";

import { toBranchRepositories } from "./branch-repository.mappers";

const node = (overrides: Record<string, unknown> = {}) => ({
  id: "repo-1",
  __typename: "CoreRepository",
  display_label: "infrastructure-templates (label)",
  name: { value: "infrastructure-templates" },
  commit: { value: "8f3c2a1" },
  sync_status: {
    value: "in-sync",
    label: "In Sync",
    color: "#60a5fa",
    description: "The repository is syncing correctly",
  },
  operational_status: { value: "online", label: "Online", color: "#86efac" },
  ...overrides,
});

const connection = (nodes: ReturnType<typeof node>[]) =>
  ({ edges: nodes.map((n) => ({ node: n })) }) as unknown as Parameters<
    typeof toBranchRepositories
  >[0];

describe("toBranchRepositories", () => {
  it("maps nodes to branch repositories", () => {
    expect(toBranchRepositories(connection([node()]))).toEqual([
      {
        id: "repo-1",
        kind: "CoreRepository",
        name: "infrastructure-templates",
        isReadOnly: false,
        commit: "8f3c2a1",
        syncStatus: {
          value: "in-sync",
          label: "In Sync",
          color: "#60a5fa",
          description: "The repository is syncing correctly",
        },
        operationalStatus: { value: "online", label: "Online" },
      },
    ]);
  });

  it("falls back to display_label, then id, for the name", () => {
    const repositories = toBranchRepositories(
      connection([
        node({ id: "a", name: { value: null } }),
        node({ id: "b", name: null, display_label: null }),
      ])
    );

    expect(repositories.map(({ name }) => name)).toEqual(["infrastructure-templates (label)", "b"]);
  });

  it("marks read-only repositories from __typename", () => {
    const [repository] = toBranchRepositories(
      connection([node({ __typename: "CoreReadOnlyRepository" })])
    );

    expect(repository).toMatchObject({ kind: "CoreReadOnlyRepository", isReadOnly: true });
  });

  it("maps a missing commit and statuses to null", () => {
    const [repository] = toBranchRepositories(
      connection([node({ commit: { value: null }, sync_status: null, operational_status: null })])
    );

    expect(repository).toMatchObject({
      commit: null,
      syncStatus: { value: null, label: null, color: null, description: null },
      operationalStatus: { value: null, label: null },
    });
  });

  it("drops nodes without an id", () => {
    const repositories = toBranchRepositories(
      connection([node({ id: null }), node({ id: "repo-2" })])
    );

    expect(repositories.map(({ id }) => id)).toEqual(["repo-2"]);
  });
});
