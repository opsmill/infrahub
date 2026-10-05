import { afterEach, describe, expect, test, vi } from "vitest";

import { getCommitWebUrl } from "@/entities/repository/domain/rules/get-commit-web-url";

import { render } from "../../../../tests/components/render";
import { generateRepositoryCommit } from "../../../../tests/fake/repository-commit";
import { RepositoryCommitRowActions } from "./repository-commit-row-actions";

const commit = generateRepositoryCommit({ short_hash: "abc1234" });

const renderRowActions = (location: string) =>
  render(
    <RepositoryCommitRowActions commit={commit} webUrl={getCommitWebUrl(location, commit.hash)} />
  );

const stubClipboard = (writeText: (value: string) => Promise<void>) => {
  vi.stubGlobal("isSecureContext", true);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
};

describe("RepositoryCommitRowActions", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  });

  test("copies the full hash and confirms it in a toast", async () => {
    // GIVEN
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    const component = await renderRowActions("/remote/infrahub-demo-edge");

    // WHEN
    await component.getByRole("button", { name: "Actions for commit abc1234" }).click();
    await component.getByRole("menuitem", { name: "Copy commit hash" }).click();

    // THEN
    expect(writeText).toHaveBeenCalledWith(commit.hash);
    await expect.element(component.getByText("Commit hash copied")).toBeVisible();
    expect(component.getByText("Could not copy the commit hash").query()).toBeNull();
  });

  test("reports in a toast that the hash could not be copied", async () => {
    // GIVEN
    stubClipboard(vi.fn().mockRejectedValue(new Error("Denied")));
    vi.spyOn(document, "execCommand").mockReturnValue(false);
    const component = await renderRowActions("/remote/infrahub-demo-edge");

    // WHEN
    await component.getByRole("button", { name: "Actions for commit abc1234" }).click();
    await component.getByRole("menuitem", { name: "Copy commit hash" }).click();

    // THEN
    await expect.element(component.getByText("Could not copy the commit hash")).toBeVisible();
    expect(component.getByText("Commit hash copied").query()).toBeNull();
  });

  test("links to the commit on GitHub in a new tab for a GitHub repository", async () => {
    // GIVEN
    const component = await renderRowActions("https://github.com/opsmill/infrahub-demo.git");

    // WHEN
    await component.getByRole("button", { name: "Actions for commit abc1234" }).click();

    // THEN
    const link = component.getByRole("menuitem", { name: "View on GitHub" });
    await expect
      .element(link)
      .toHaveAttribute("href", `https://github.com/opsmill/infrahub-demo/commit/${commit.hash}`);
    await expect.element(link).toHaveAttribute("target", "_blank");
    await expect.element(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("offers no GitHub link for a repository outside GitHub", async () => {
    // GIVEN
    const component = await renderRowActions("/remote/infrahub-demo-edge");

    // WHEN
    await component.getByRole("button", { name: "Actions for commit abc1234" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Copy commit hash" }))
      .toBeVisible();
    expect(component.getByRole("menuitem", { name: "View on GitHub" }).query()).toBeNull();
  });
});
