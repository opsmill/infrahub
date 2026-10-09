import { describe, expect, it } from "vitest";

import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";
import { QSP } from "@/shared/config/qsp";

import { getDocumentationUrl, getObjectGraphqlSandboxUrl, getObjectTasksUrl } from "./object-urls";

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
