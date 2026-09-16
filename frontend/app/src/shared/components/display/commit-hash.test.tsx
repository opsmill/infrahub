import { describe, expect, test } from "vitest";

import { CommitHash } from "@/shared/components/display/commit-hash";

import { render } from "../../../../tests/components/render";

const HASH = "8f3c2a1d9b4e7c05a2f1e6d3b8074c5a19fe2b6d";

describe("CommitHash", () => {
  test("displays the first seven characters of the hash", async () => {
    const component = await render(<CommitHash hash={HASH} />);

    await expect.element(component.getByText("8f3c2a1", { exact: true })).toBeVisible();
  });

  test("reveals the full hash on hover", async () => {
    const component = await render(<CommitHash hash={HASH} />);

    await expect.element(component.getByTitle(HASH, { exact: true })).toBeVisible();
  });

  test("renders no copy affordance by default", async () => {
    const component = await render(<CommitHash hash={HASH} />);

    expect(component.getByRole("button").elements()).toHaveLength(0);
  });

  test("offers a copy button naming the full hash when copyable", async () => {
    const component = await render(<CommitHash hash={HASH} copyable />);

    await expect
      .element(component.getByRole("button", { name: `Copy commit ${HASH}` }))
      .toBeVisible();
  });

  test("leaves a hash shorter than the short form untouched", async () => {
    const component = await render(<CommitHash hash="abc12" />);

    await expect.element(component.getByText("abc12", { exact: true })).toBeVisible();
  });
});
