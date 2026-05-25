import { afterEach, describe, expect, it, vi } from "vitest";
import { render } from "vitest-browser-react";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

function CopyButton({ value }: { value: string }) {
  const { isCopied, copyToClipboard } = useCopyToClipboard();
  return (
    <button
      data-testid="copy-btn"
      data-copied={String(isCopied)}
      onClick={() => copyToClipboard(value)}
    >
      {isCopied ? "copied" : "copy"}
    </button>
  );
}

describe("useCopyToClipboard", () => {
  afterEach(() => {
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
});
