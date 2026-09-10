import { afterEach, describe, expect, test } from "vitest";

import { CountBadge } from "@/shared/components/buttons/count-badge";

import { render } from "../../../../tests/components/render";

// The raised highlight on this badge used to be two hand-written literals — a near-white catch for
// light mode and a fainter one for dark — kept in sync by hand through a dark: variant. It is now
// the single --inset-shadow-raised token, whose value is swapped by :root/.dark.
//
// These assertions read the *computed* box-shadow instead of the class string on purpose. Tailwind
// bakes a theme value into the utility at build time unless it is bridged through `@theme inline`,
// and when that goes wrong the .dark override becomes dead CSS: the class is still there, the
// markup still says `inset-shadow-raised`, and only the rendered pixels are wrong. A class-name
// assertion would pass in exactly that case, which is the failure this test exists to catch.
//
// The badge also carries `shadow-xs dark:shadow-none`, so the *whole* box-shadow string differs
// between themes no matter what the inset token does. Comparing full strings therefore proves
// nothing — verified by mutation: deleting the .dark override still passed. Hence the split below,
// which isolates the inset layer and compares only that.
const topLevelParts = (boxShadow: string): Array<string> => {
  const parts: Array<string> = [];
  let depth = 0;
  let current = "";
  for (const char of boxShadow) {
    if (char === "(") depth += 1;
    if (char === ")") depth -= 1;
    if (char === "," && depth === 0) {
      parts.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  if (current.trim()) parts.push(current.trim());
  return parts;
};

const insetLayer = (container: Element): string | undefined => {
  const badge = container.querySelector("span");
  if (!badge) return undefined;
  return topLevelParts(getComputedStyle(badge).boxShadow).find((part) => part.includes("inset"));
};

describe("CountBadge raised highlight", () => {
  afterEach(() => {
    document.documentElement.classList.remove("dark");
  });

  test("the inset-shadow-raised token resolves to a different value in each theme", async () => {
    const component = await render(<CountBadge count={3} />);

    const light = insetLayer(component.container);
    expect(light).toBeDefined();

    // Flip the theme on the same element rather than re-rendering: the token is swapped by CSS, so
    // if the override is live the computed value must change without React doing anything.
    document.documentElement.classList.add("dark");
    const dark = insetLayer(component.container);

    expect(dark).toBeDefined();
    expect(dark).not.toBe(light);
  });
});
