/**
 * React Aria tooltips require a prior pointer interaction to "warm up"
 * before they respond to hover events. Call this once before any `.hover()`
 * that needs to trigger a tooltip.
 */
export async function initPointerTracking(locator: PointerLocator) {
  await locator.click({ position: { x: 0, y: 0 } });
}

/**
 * Moves the pointer off whatever it is hovering, so an open React Aria tooltip closes before the
 * next interaction or render.
 */
export async function closeTooltip(locator: PointerLocator) {
  await locator.click({ position: { x: 0, y: 0 } });
}

interface PointerLocator {
  click(options?: { position?: { x: number; y: number } }): Promise<void>;
}
