import { describe, expect, test } from "vitest";

import { getCommitWebUrl } from "@/entities/repository/domain/rules/get-commit-web-url";

import { render } from "../../../../tests/components/render";
import { generateRepositoryCommit } from "../../../../tests/fake/repository-commit";
import { RepositoryCommitRowActions } from "./repository-commit-row-actions";

const commit = generateRepositoryCommit({ short_hash: "abc1234" });

const renderRowActions = (location: string) =>
  render(
    <RepositoryCommitRowActions commit={commit} webUrl={getCommitWebUrl(location, commit.hash)} />
  );

describe("RepositoryCommitRowActions", () => {
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
