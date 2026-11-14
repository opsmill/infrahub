import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useConfig } from "@/entities/config/ui/config-provider";
import { InstanceFavicon } from "@/entities/preferences/ui/instance-favicon";

import { render } from "../../../../tests/components/render";
import { generateConfigWithInstance } from "../../../../tests/fake/config";

vi.mock("@/entities/config/ui/config-provider");

const ORIGINAL_FAVICON = "/favicons/favicon.ico";

function faviconHref(): string | null {
  return document.head.querySelector('link[rel="icon"]')?.getAttribute("href") ?? null;
}

describe("InstanceFavicon", () => {
  let favicon: HTMLLinkElement;

  beforeEach(() => {
    favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.setAttribute("href", ORIGINAL_FAVICON);
    document.head.prepend(favicon);
  });

  afterEach(() => {
    favicon.remove();
    vi.resetAllMocks();
  });

  test("shows the Infrahub mark in the preset color when a color is set", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance(null, "RED"));

    // WHEN
    await render(<InstanceFavicon />);

    // THEN
    const href = faviconHref() ?? "";
    expect(href.startsWith("data:image/svg+xml,")).toBe(true);
    expect(decodeURIComponent(href)).toContain('fill="#be123c"');
  });

  test("keeps the standard favicon when no color is set", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance("QA", null));

    // WHEN
    await render(<InstanceFavicon />);

    // THEN
    expect(faviconHref()).toBe(ORIGINAL_FAVICON);
  });

  test("restores the standard favicon when the color is cleared", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance(null, "BLUE"));
    const component = await render(<InstanceFavicon />);
    expect(decodeURIComponent(faviconHref() ?? "")).toContain('fill="#0369a1"');

    // WHEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance(null, null));
    await component.rerender(<InstanceFavicon />);

    // THEN
    expect(faviconHref()).toBe(ORIGINAL_FAVICON);
  });
});
