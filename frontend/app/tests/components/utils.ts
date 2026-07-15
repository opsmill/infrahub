/** React Aria tooltips need a prior pointer interaction; call once before a `.hover()` that opens one. */
export async function initPointerTracking(locator: {
  click(options?: { position?: { x: number; y: number } }): Promise<void>;
}) {
  await locator.click({ position: { x: 0, y: 0 } });
}

interface Locator {
  click(): Promise<void>;
  fill(value: string): Promise<void>;
}

interface QueryableComponent {
  getByRole: (role: string, options?: { name?: string | RegExp; exact?: boolean }) => Locator;
}

/**
 * Open the design-system searchable select (`triggerName` = field label) and click the option whose
 * exact visible text is `optionName` (exact so "yyyy-MM-dd" can't match "yyyy-MM-dd HH:mm"). The
 * trigger is a react-aria `Button` (`role="button"`, accessible name = the field label); the
 * `Autocomplete` renders a `searchbox`; `ListBox` items are `role="option"`. For long lists (e.g.
 * timezones), pass `filter` to narrow the list first (also required so a virtualized option is
 * rendered before clicking).
 */
export async function selectComboboxOption(
  component: QueryableComponent,
  triggerName: string | RegExp,
  optionName: string,
  filter?: string
) {
  await component.getByRole("button", { name: triggerName }).click();
  if (filter !== undefined) {
    await component.getByRole("searchbox").fill(filter);
  }
  await component.getByRole("option", { name: optionName, exact: true }).click();
}
