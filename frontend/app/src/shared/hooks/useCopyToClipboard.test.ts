import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useCopyToClipboard } from "./useCopyToClipboard";

describe("useCopyToClipboard", () => {
  let originalWriteText: typeof navigator.clipboard.writeText;
  let originalIsSecureContext: boolean;

  beforeEach(() => {
    originalWriteText = navigator.clipboard.writeText.bind(navigator.clipboard);
    originalIsSecureContext = window.isSecureContext;
  });

  afterEach(() => {
    navigator.clipboard.writeText = originalWriteText;
    Object.defineProperty(window, "isSecureContext", {
      value: originalIsSecureContext,
      configurable: true,
    });
    vi.restoreAllMocks();
  });

  it("should call fallback copy synchronously when in a non-secure context", async () => {
    // GIVEN - non-secure context (HTTP deployment) where the Clipboard API
    // rejects with NotAllowedError, as Chrome does on non-HTTPS origins
    Object.defineProperty(window, "isSecureContext", {
      value: false,
      configurable: true,
    });
    navigator.clipboard.writeText = vi
      .fn()
      .mockRejectedValue(new DOMException("Clipboard write was blocked", "NotAllowedError"));

    const execCommandSpy = vi.spyOn(document, "execCommand").mockReturnValue(true);
    const { result } = await renderHook(() => useCopyToClipboard());

    // WHEN - copyToClipboard is called from a user-gesture handler.
    // The fallback (document.execCommand) must execute synchronously within
    // the same call stack so Chrome 146 honours the user-activation context.
    result.current.copyToClipboard("test text");

    // THEN - document.execCommand('copy') must have been called synchronously.
    //
    // BUG: The current implementation is an async function that always enters
    // `await navigator.clipboard.writeText()` first. When writeText returns a
    // rejected promise, `await` suspends the function and the catch block
    // (which calls oldSchoolCopy -> execCommand) only runs as a microtask,
    // after the user-gesture context has ended. Chrome 146 silently blocks
    // execCommand('copy') outside a synchronous user-gesture handler.
    //
    // A synchronous guard should detect the non-secure context and call
    // oldSchoolCopy immediately, before any async operation.
    expect(execCommandSpy).toHaveBeenCalledWith("copy");
  });
});
