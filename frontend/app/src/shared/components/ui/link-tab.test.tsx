import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, test, vi } from "vitest";

import { render } from "@/../tests/components/render";

import { LinkTab } from "@/shared/components/ui/link";

function renderAt(path: string, ui: React.ReactElement) {
  // Override the default BrowserRouter wrapper with a MemoryRouter so we can
  // control the active URL per test without conflicting with the browser URL.
  return render(ui, {
    wrapper: ({ children }) => (
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/parent/*" element={<>{children}</>} />
        </Routes>
      </MemoryRouter>
    ),
  });
}

describe("LinkTab", () => {
  test("renders children and href", async () => {
    const component = await renderAt("/parent", <LinkTab href="/parent/data">Data</LinkTab>);
    const link = component.container.querySelector("a");
    expect(link).not.toBeNull();
    expect(link?.textContent).toBe("Data");
    expect(link?.getAttribute("href")).toBe("/parent/data");
  });

  test("applies active border when URL matches", async () => {
    const component = await renderAt("/parent/data", <LinkTab href="/parent/data">Data</LinkTab>);
    const link = component.container.querySelector("a");
    expect(link?.className).toMatch(/border-custom-blue-600/);
  });

  test("does not apply active border when URL does not match", async () => {
    const component = await renderAt("/parent/files", <LinkTab href="/parent/data">Data</LinkTab>);
    const link = component.container.querySelector("a");
    expect(link?.className).not.toMatch(/border-custom-blue-600/);
  });

  test("end matching is exact — child paths do not activate the parent tab", async () => {
    const component = await renderAt(
      "/parent/data/123",
      <LinkTab href="/parent/data">Data</LinkTab>
    );
    const link = component.container.querySelector("a");
    expect(link?.className).not.toMatch(/border-custom-blue-600/);
  });

  test("scrolls into view when active and scrollIntoViewOnActive is true", async () => {
    const scrollIntoView = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    await renderAt(
      "/parent/data",
      <LinkTab href="/parent/data" scrollIntoViewOnActive>
        Data
      </LinkTab>
    );
    expect(scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ behavior: "smooth" }));
    scrollIntoView.mockRestore();
  });

  test("does not scroll when inactive", async () => {
    const scrollIntoView = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    await renderAt(
      "/parent/files",
      <LinkTab href="/parent/data" scrollIntoViewOnActive>
        Data
      </LinkTab>
    );
    expect(scrollIntoView).not.toHaveBeenCalled();
    scrollIntoView.mockRestore();
  });

  test("does not scroll when active but scrollIntoViewOnActive is absent", async () => {
    const scrollIntoView = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    await renderAt("/parent/data", <LinkTab href="/parent/data">Data</LinkTab>);
    expect(scrollIntoView).not.toHaveBeenCalled();
    scrollIntoView.mockRestore();
  });
});
