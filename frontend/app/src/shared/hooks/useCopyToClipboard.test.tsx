import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render } from "vitest-browser-react";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

function CopyButton({ value }: { value: string }) {
  const { isCopied, copyCount, copyToClipboard } = useCopyToClipboard();
  return (
    <button
      data-testid="copy-btn"
      data-copied={String(isCopied)}
      data-copy-count={copyCount}
      onClick={() => copyToClipboard(value)}
    >
      {isCopied ? "copied" : "copy"}
    </button>
  );
}

describe("useCopyToClipboard", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("uses navigator.clipboard.writeText in a secure context", async () => {
    // GIVEN
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    const component = await render(<CopyButton value="test-value" />);

    // WHEN
    await component.getByTestId("copy-btn").click();

    // THEN
    expect(writeText).toHaveBeenCalledWith("test-value");
    await expect.element(component.getByText("copied")).toBeVisible();
  });

  it("falls back to selection-based copy when not in a secure context", async () => {
    // GIVEN
    vi.stubGlobal("isSecureContext", false);
    const execCommand = vi.spyOn(document, "execCommand").mockReturnValue(true);

    const component = await render(<CopyButton value="test-value" />);

    // WHEN
    await component.getByTestId("copy-btn").click();

    // THEN
    expect(execCommand).toHaveBeenCalledWith("copy");
    await expect.element(component.getByText("copied")).toBeVisible();
  });

  it("falls back to selection-based copy when navigator.clipboard is unavailable", async () => {
    // GIVEN
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      configurable: true,
    });
    const execCommand = vi.spyOn(document, "execCommand").mockReturnValue(true);

    const component = await render(<CopyButton value="test-value" />);

    // WHEN
    await component.getByTestId("copy-btn").click();

    // THEN
    expect(execCommand).toHaveBeenCalledWith("copy");
    await expect.element(component.getByText("copied")).toBeVisible();
  });

  it("falls back to selection-based copy when navigator.clipboard.writeText rejects", async () => {
    // GIVEN
    const writeText = vi.fn().mockRejectedValue(new Error("Permission denied"));
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    const execCommand = vi.spyOn(document, "execCommand").mockReturnValue(true);

    const component = await render(<CopyButton value="test-value" />);

    // WHEN
    await component.getByTestId("copy-btn").click();

    // THEN
    expect(execCommand).toHaveBeenCalledWith("copy");
    await expect.element(component.getByText("copied")).toBeVisible();
  });

  it("counts every successful copy so repeated copies can be announced again", async () => {
    // GIVEN
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    const component = await render(<CopyButton value="test-value" />);
    const button = component.getByTestId("copy-btn");
    await expect.element(button).toHaveAttribute("data-copy-count", "0");

    // WHEN
    await button.click();
    await expect.element(button).toHaveAttribute("data-copy-count", "1");
    await button.click();

    // THEN
    await expect.element(button).toHaveAttribute("data-copy-count", "2");
  });

  it("keeps the copied state for the full duration after the latest copy", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    vi.stubGlobal("isSecureContext", false);
    vi.spyOn(document, "execCommand").mockReturnValue(true);
    const component = await render(<CopyButton value="test-value" />);
    const button = component.getByTestId("copy-btn").element();
    const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
    await act(() => button.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await advance(1500);

    // WHEN
    await act(() => button.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await advance(1999);

    // THEN
    expect(button).toHaveAttribute("data-copy-count", "2");
    expect(button).toHaveAttribute("data-copied", "true");
    await advance(1);
    expect(button).toHaveAttribute("data-copied", "false");
  });
});
