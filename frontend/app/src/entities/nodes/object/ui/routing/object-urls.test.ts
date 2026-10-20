import { afterEach, describe, expect, it } from "vitest";

import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";
import { QSP } from "@/shared/config/qsp";
import { store } from "@/shared/stores";

import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import {
  getDocumentationUrl,
  getObjectDetailsUrl,
  getObjectGraphqlSandboxUrl,
  getObjectTasksUrl,
} from "./object-urls";

describe("getObjectDetailsUrl for a resource pool", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  afterEach(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("appends the tab segment to the pool's address", () => {
    // GIVEN
    store.set(nodeSchemasAtom, [
      generateNodeSchema({
        kind: "CoreNumberPool",
        name: "NumberPool",
        namespace: "Core",
        inherit_from: [RESOURCE_GENERIC_KIND],
      }),
    ]);

    // WHEN
    const url = getObjectDetailsUrl("CoreNumberPool", "pool-id", undefined, "ranges/range-id");

    // THEN
    expect(url).toBe("/resource-manager/pool-id/ranges/range-id");
  });
});

describe("getObjectTasksUrl", () => {
  it("filters the tasks list on the node id", () => {
    // WHEN
    const url = getObjectTasksUrl("pool-id");

    // THEN
    expect(url).toBe(`/tasks?${QSP.FILTER}=[{"name":"node__value","value":"pool-id"}]`);
  });
});

describe("getObjectGraphqlSandboxUrl", () => {
  it("opens the sandbox with a query for the node by id", () => {
    // WHEN
    const url = getObjectGraphqlSandboxUrl("CoreNumberPool", "pool-id");

    // THEN
    const [path, search] = url.split("?");
    const query = new URLSearchParams(search).get("query");
    expect(path).toBe("/graphql");
    expect(query).toContain("CoreNumberPool");
    expect(query).toContain('ids: ["pool-id"]');
    expect(query).toContain("display_label");
  });
});

describe("getDocumentationUrl", () => {
  it("keeps an absolute documentation url", () => {
    // WHEN
    const url = getDocumentationUrl("https://example.com/pools");

    // THEN
    expect(url).toBe("https://example.com/pools");
  });

  it("prefixes a relative documentation path with the local docs url", () => {
    // WHEN
    const url = getDocumentationUrl("/topics/resource-manager");

    // THEN
    expect(url).toBe(`${INFRAHUB_DOC_LOCAL}/topics/resource-manager`);
  });
});
