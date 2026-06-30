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
 * Pick an option from the shared {@link Combobox} (a Radix popover wrapping a cmdk
 * `Command`) — the element our `ComboboxField`/`TimezoneField` render.
 *
 * The trigger is a `<button role="combobox">` whose accessible name is the field
 * label; opening it mounts a cmdk list whose items are `role="option"`. Unlike the
 * React Aria `Select`, the popover has no enter animation that detaches the target,
 * so opening the trigger and clicking the option by its exact visible label is
 * deterministic. cmdk auto-focuses the search input on open, so passing a `filter`
 * narrows the list first (the input is auto-focused, so we type via keyboard rather
 * than relying on its accessible name) — useful for long lists such as timezones.
 *
 * `triggerName` matches the field label (e.g. /date format/i); `optionName` is the
 * option's exact visible text (for the preferences combobox this equals the stored
 * value). Matching is exact so e.g. "yyyy-MM-dd" cannot also match "yyyy-MM-dd HH:mm".
 */
export async function selectComboboxOption(
  component: {
    getByRole: (
      role: string,
      options?: { name?: string | RegExp; exact?: boolean }
    ) => { click(): Promise<void> };
  },
  triggerName: string | RegExp,
  optionName: string,
  filter?: string
) {
  await component.getByRole("combobox", { name: triggerName }).click();
  if (filter !== undefined) {
    // The cmdk search box auto-focuses on open; type into the focused element.
    const { userEvent } = await import("vitest/browser");
    await userEvent.keyboard(filter);
  }
  await component.getByRole("option", { name: optionName, exact: true }).click();
}
