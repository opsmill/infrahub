import { afterEach, describe, expect, test, vi } from "vitest";

import { copyTextToClipboard } from "@/shared/utils/clipboard";

const stubClipboard = (writeText: (value: string) => Promise<void>) =>
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

describe("copyTextToClipboard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  });

  test("writes through the Clipboard API in a secure context", async () => {
    // GIVEN
    vi.stubGlobal("isSecureContext", true);
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    const execCommand = vi.spyOn(document, "execCommand");

    // WHEN
    const isCopied = await copyTextToClipboard("abc1234");

    // THEN
    expect(isCopied).toBe(true);
    expect(writeText).toHaveBeenCalledWith("abc1234");
    expect(execCommand).not.toHaveBeenCalled();
  });

  test("falls back to a selection copy when the Clipboard API rejects", async () => {
    // GIVEN
    vi.stubGlobal("isSecureContext", true);
    stubClipboard(vi.fn().mockRejectedValue(new Error("Denied")));
    const execCommand = vi.spyOn(document, "execCommand").mockReturnValue(true);

    // WHEN
    const isCopied = await copyTextToClipboard("abc1234");

    // THEN
    expect(isCopied).toBe(true);
    expect(execCommand).toHaveBeenCalledWith("copy");
  });

  test("falls back to a selection copy outside a secure context", async () => {
    // GIVEN
    vi.stubGlobal("isSecureContext", false);
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    vi.spyOn(document, "execCommand").mockReturnValue(true);

    // WHEN
    const isCopied = await copyTextToClipboard("abc1234");

    // THEN
    expect(isCopied).toBe(true);
    expect(writeText).not.toHaveBeenCalled();
  });

  test("reports a failure when both the Clipboard API and the selection copy fail", async () => {
    // GIVEN
    vi.stubGlobal("isSecureContext", true);
    stubClipboard(vi.fn().mockRejectedValue(new Error("Denied")));
    vi.spyOn(document, "execCommand").mockReturnValue(false);

    // WHEN
    const isCopied = await copyTextToClipboard("abc1234");

    // THEN
    expect(isCopied).toBe(false);
  });

  test("leaves no copied text behind in the document", async () => {
    // GIVEN
    vi.stubGlobal("isSecureContext", false);
    vi.spyOn(document, "execCommand").mockReturnValue(false);
    const bodyText = document.body.textContent;

    // WHEN
    await copyTextToClipboard("abc1234");

    // THEN
    expect(document.body.textContent).toBe(bodyText);
  });
});
