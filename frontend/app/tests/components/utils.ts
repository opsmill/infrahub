import { vi } from "vitest";
import { userEvent } from "vitest/browser";

/**
 * React Aria tooltips require a prior pointer interaction to "warm up"
 * before they respond to hover events. Call this once before any `.hover()`
 * that needs to trigger a tooltip.
 */
export async function initPointerTracking(locator: {
  click(options?: { position?: { x: number; y: number } }): Promise<void>;
}) {
  await locator.click({ position: { x: 0, y: 0 } });
}

/**
 * Pick an option (by its visible label) from a React Aria `Select` — the element
 * the @infrahub/ui `SelectField` renders.
 *
 * Driving the visible popover is unreliable: it plays an enter animation
 * (zoom/slide) and the field re-renders as React Aria settles selection on open,
 * so the option element keeps moving and detaching from the DOM. Under full-suite
 * CPU contention that window stays open long enough that even a forced click never
 * resolves a stable, attached target and times out.
 *
 * React Aria `Select` also renders a real, visually-hidden native `<select>` (its
 * form-submission element) carrying the same options. Selecting on that element
 * drives React Aria's selection state exactly as a popover click would — firing the
 * same change handler — without any animation or moving target, so it is
 * deterministic. We match the option by its label text (the native option's
 * `textContent`), matching how tests refer to options elsewhere.
 *
 * Scoped to the rendered component's `container` so renders from earlier tests in
 * the same file (vitest-browser does not unmount between tests) cannot match.
 * `name` disambiguates when one form has more than one `SelectField`.
 */
export async function selectOption(
  component: { container: ParentNode },
  label: string,
  options: { name?: string } = {}
) {
  const findSelects = () => {
    const selects = Array.from(component.container.querySelectorAll<HTMLSelectElement>("select"));
    return options.name ? selects.filter((s) => s.getAttribute("name") === options.name) : selects;
  };

  // React Aria mounts the Select's hidden native <select> lazily, once its
  // collection has been built — so it may not exist on first render. Polling lets
  // it appear without us having to drive the (animated, flaky) visible popover.
  let candidates = findSelects();
  if (candidates.length === 0) {
    await vi.waitFor(() => {
      candidates = findSelects();
      if (candidates.length === 0) throw new Error("no <select> mounted yet");
    });
  }

  if (candidates.length !== 1) {
    throw new Error(
      `selectOption expected exactly one matching <select>${
        options.name ? ` named "${options.name}"` : ""
      }, found ${candidates.length}`
    );
  }

  const select = candidates[0];
  const option = Array.from(select.options).find((o) => o.textContent?.trim() === label);
  if (!option) {
    const available = Array.from(select.options).map((o) => o.textContent?.trim());
    throw new Error(`option "${label}" not found; available: ${JSON.stringify(available)}`);
  }

  await userEvent.selectOptions(select, option.value);
}
