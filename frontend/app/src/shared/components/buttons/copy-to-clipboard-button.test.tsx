import { afterEach, describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";

describe("CopyToClipboardButton", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  });

  function stubClipboard() {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    return writeText;
  }

  test("writes the value to the clipboard and announces it", async () => {
    // GIVEN
    const writeText = stubClipboard();
    const component = await render(<CopyToClipboardButton data="abc123" aria-label="Copy hash" />);

    // WHEN
    await component.getByRole("button", { name: "Copy hash" }).click();

    // THEN
    expect(writeText).toHaveBeenCalledWith("abc123");
    await expect.element(component.getByRole("status")).toHaveTextContent("Copied to clipboard");
  });

  test("re-announces with a fresh node on a second copy", async () => {
    // GIVEN
    stubClipboard();
    const component = await render(<CopyToClipboardButton data="abc123" aria-label="Copy hash" />);
    const button = component.getByRole("button", { name: "Copy hash" });
    const status = component.getByRole("status");
    await button.click();
    await expect.element(status).toHaveTextContent("Copied to clipboard");
    const firstAnnouncement = status.element().firstElementChild;

    // WHEN
    await button.click();

    // THEN
    await expect.poll(() => status.element().firstElementChild).not.toBe(firstAnnouncement);
    expect(firstAnnouncement?.isConnected).toBe(false);
    await expect.element(status).toHaveTextContent("Copied to clipboard");
  });
});
