import { describe, expect, test } from "vitest";

import { getCommitWebUrl } from "@/entities/repository/domain/rules/get-commit-web-url";

const HASH = "0123456789abcdef0123456789abcdef01234567";
const COMMIT_URL = `https://github.com/opsmill/infrahub-demo/commit/${HASH}`;

describe("getCommitWebUrl", () => {
  test.each([
    "https://github.com/opsmill/infrahub-demo",
    "https://github.com/opsmill/infrahub-demo.git",
    "https://github.com/opsmill/infrahub-demo/",
    "https://github.com/opsmill/infrahub-demo.git/",
    "http://github.com/opsmill/infrahub-demo.git",
    "https://GitHub.com/opsmill/infrahub-demo",
    "  https://github.com/opsmill/infrahub-demo.git  ",
    "git@github.com:opsmill/infrahub-demo",
    "git@github.com:opsmill/infrahub-demo.git",
    "ssh://git@github.com/opsmill/infrahub-demo",
    "ssh://git@github.com/opsmill/infrahub-demo.git",
  ])("builds the commit page URL for %s", (location) => {
    expect(getCommitWebUrl(location, HASH)).toBe(COMMIT_URL);
  });

  test("drops the credentials embedded in the location", () => {
    const location = "https://deploy-bot:ghp_s3cr3tT0ken@github.com/opsmill/infrahub-demo.git";

    const url = getCommitWebUrl(location, HASH);

    expect(url).toBe(COMMIT_URL);
    expect(url).not.toContain("ghp_s3cr3tT0ken");
    expect(url).not.toContain("deploy-bot");
  });

  test.each([
    ["a local path", "/remote/infrahub-demo-edge"],
    ["a file URL", "file:///remote/infrahub-demo-edge"],
    ["another host", "https://gitlab.com/opsmill/infrahub-demo.git"],
    ["a GitHub lookalike host", "https://github.com.evil.example/opsmill/infrahub-demo"],
    ["a GitHub subdomain", "https://gist.github.com/opsmill/infrahub-demo"],
    ["a scp-like remote on another host", "git@gitlab.com:opsmill/infrahub-demo.git"],
    ["an ssh remote on another host", "ssh://git@gitlab.com/opsmill/infrahub-demo.git"],
    ["a non-default port", "https://github.com:8443/opsmill/infrahub-demo"],
    ["an unsupported scheme", "ftp://github.com/opsmill/infrahub-demo"],
    ["an owner without a repository", "https://github.com/opsmill"],
    ["the host alone", "https://github.com"],
    ["extra path segments", "https://github.com/opsmill/infrahub-demo/tree/main"],
    ["a query string", "https://github.com/opsmill/infrahub-demo?tab=readme"],
    ["a fragment", "https://github.com/opsmill/infrahub-demo#readme"],
    ["an empty repository name", "https://github.com/opsmill/.git"],
    ["malformed input", "not a url"],
    ["an empty string", ""],
  ])("returns null for %s", (_, location) => {
    expect(getCommitWebUrl(location, HASH)).toBeNull();
  });

  test.each([
    ["an empty hash", ""],
    ["a non-hex hash", "not-a-hash"],
    ["a path in place of a hash", "../../settings"],
  ])("returns null for %s", (_, hash) => {
    expect(getCommitWebUrl("https://github.com/opsmill/infrahub-demo", hash)).toBeNull();
  });
});
