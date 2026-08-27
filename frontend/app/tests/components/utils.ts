/**
 * React Aria tooltips require a prior pointer interaction to "warm up" before they respond to hover
 * events, and parking the pointer away again is what closes an open one. Call it before any
 * `.hover()` that needs to trigger a tooltip, and after asserting on one so it closes before the
 * next interaction or render.
 */
export async function initPointerTracking(locator: PointerLocator) {
  await locator.click({ position: { x: 0, y: 0 } });
}

/** The same gesture, named for the intent callers have once a tooltip is already open. */
export const closeTooltip = initPointerTracking;

interface PointerLocator {
  click(options?: { position?: { x: number; y: number } }): Promise<void>;
}
