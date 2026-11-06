import { afterEach, describe, expect, test, vi } from "vitest";

import { useTitle } from "@/shared/hooks/useTitle";

import { useConfig } from "@/entities/config/ui/config-provider";
import { APPLICATION_TITLE, DocumentTitle } from "@/entities/preferences/ui/document-title";

import { render } from "../../../../tests/components/render";
import { generateConfigWithInstance } from "../../../../tests/fake/config";

vi.mock("@/entities/config/ui/config-provider");

const withLabel = (label: string | null) => generateConfigWithInstance(label, null);

function Page({ title }: { title: string }) {
  useTitle(title);
  return <h1>{title}</h1>;
}

function Layout({ children }: { children?: React.ReactNode }) {
  return <main>{children}</main>;
}

describe("DocumentTitle", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows the instance label and the application name when no page sets a title", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));

    // WHEN
    await render(<DocumentTitle />);

    // THEN
    expect(document.title).toBe(`QA · ${APPLICATION_TITLE}`);
  });

  test("keeps the page title when the owner, a layout and the page mount in the same commit", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));

    // WHEN
    await render(
      <>
        <DocumentTitle />
        <Layout>
          <Page title="Branches" />
        </Layout>
      </>
    );

    // THEN
    expect(document.title).toBe("QA · Branches");
  });

  test("follows the instance label when it changes while a page is open", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));
    const component = await render(
      <>
        <DocumentTitle />
        <Page title="Schema" />
      </>
    );
    vi.mocked(useConfig).mockReturnValue(withLabel("Staging"));

    // WHEN
    await component.rerender(
      <>
        <DocumentTitle />
        <Page title="Schema" />
      </>
    );

    // THEN
    expect(document.title).toBe("Staging · Schema");
  });

  test("falls back to the instance label and the application name when the page unmounts", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));
    const component = await render(
      <>
        <DocumentTitle />
        <Page title="Schema" />
      </>
    );

    // WHEN
    await component.rerender(<DocumentTitle />);

    // THEN
    expect(document.title).toBe("QA · Infrahub");
  });
});
