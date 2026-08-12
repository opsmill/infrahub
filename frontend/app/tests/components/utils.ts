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
