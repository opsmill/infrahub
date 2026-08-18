import { afterEach, describe, expect, test } from "vitest";

import { useResolvedTheme } from "@/shared/hooks/use-resolved-theme";

import { render } from "../../../tests/components/render";

const Probe = () => <span data-testid="theme">{useResolvedTheme()}</span>;

describe("useResolvedTheme", () => {
  afterEach(() => {
    document.documentElement.classList.remove("dark");
  });

  test("reads dark from a document that already carries the class", async () => {
    document.documentElement.classList.add("dark");

    const component = await render(<Probe />);

    await expect.element(component.getByTestId("theme")).toHaveTextContent("dark");
  });

  test("follows the class as it is toggled while mounted", async () => {
    const component = await render(<Probe />);
    await expect.element(component.getByTestId("theme")).toHaveTextContent("light");

    // WHEN something outside React flips the theme, as the pre-paint script and devtools both do
    document.documentElement.classList.add("dark");
    await expect.element(component.getByTestId("theme")).toHaveTextContent("dark");

    document.documentElement.classList.remove("dark");
    await expect.element(component.getByTestId("theme")).toHaveTextContent("light");
  });

  test("ignores unrelated class churn on the document element", async () => {
    const component = await render(<Probe />);

    document.documentElement.classList.add("some-other-class");
    await expect.element(component.getByTestId("theme")).toHaveTextContent("light");

    document.documentElement.classList.remove("some-other-class");
  });
});
