import React from "react";
import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";
import { InfiniteTrigger, type InfiniteTriggerProps } from "./infinite-trigger";

const VISIBLE_HEIGHT = 100;
const CONTENT_HEIGHT = 400;
const THRESHOLD = 200;

interface ScrollableListProps
  extends Pick<InfiniteTriggerProps, "onLoadMore" | "isFetchingNextPage" | "threshold"> {
  hasNextPage?: boolean;
}

const ScrollableList = ({
  hasNextPage = true,
  threshold = THRESHOLD,
  ...props
}: ScrollableListProps) => {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  return (
    <div
      ref={scrollRef}
      data-testid="scroll-container"
      className="overflow-auto"
      style={{ height: VISIBLE_HEIGHT }}
    >
      <div style={{ height: CONTENT_HEIGHT }} />
      <InfiniteTrigger
        data-testid="infinite-trigger"
        hasNextPage={hasNextPage}
        threshold={threshold}
        rootRef={scrollRef}
        {...props}
      />
    </div>
  );
};

const getScrollContainer = (component: Awaited<ReturnType<typeof render>>) =>
  component.getByTestId("scroll-container").element() as HTMLElement;

const scrollTriggerToDistanceBelowView = (scrollContainer: HTMLElement, distance: number) => {
  scrollContainer.scrollTop = CONTENT_HEIGHT - VISIBLE_HEIGHT - distance;
};

// Observers are notified in creation order, so once this one reports, the trigger's observer has already reported the same scroll position.
const waitForIntersectionCheck = (component: Awaited<ReturnType<typeof render>>) => {
  const trigger = component.getByTestId("infinite-trigger").element();

  return new Promise<void>((resolve) => {
    const observer = new IntersectionObserver(
      () => {
        observer.disconnect();
        resolve();
      },
      { root: getScrollContainer(component), rootMargin: `${THRESHOLD}px 0px` }
    );
    observer.observe(trigger);
  });
};

describe("InfiniteTrigger", () => {
  test("loads more once the trigger is within the threshold below the scroll container's visible area", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await render(<ScrollableList onLoadMore={onLoadMore} />);

    // WHEN
    scrollTriggerToDistanceBelowView(getScrollContainer(component), THRESHOLD / 2);

    // THEN
    await expect.poll(() => onLoadMore).toHaveBeenCalledOnce();
  });

  test("does not load more while the trigger is further below the visible area than the threshold", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await render(<ScrollableList onLoadMore={onLoadMore} />);

    // WHEN
    scrollTriggerToDistanceBelowView(getScrollContainer(component), THRESHOLD + 50);
    await waitForIntersectionCheck(component);

    // THEN
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  test("loads more as early as a larger threshold allows", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const threshold = CONTENT_HEIGHT;

    // WHEN
    await render(<ScrollableList onLoadMore={onLoadMore} threshold={threshold} />);

    // THEN
    await expect.poll(() => onLoadMore).toHaveBeenCalledOnce();
  });

  test("does not load more when there is no next page", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await render(<ScrollableList onLoadMore={onLoadMore} hasNextPage={false} />);

    // WHEN
    scrollTriggerToDistanceBelowView(getScrollContainer(component), 0);
    await waitForIntersectionCheck(component);

    // THEN
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  test("does not request a page while the next page is still loading", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await render(<ScrollableList onLoadMore={onLoadMore} isFetchingNextPage />);

    // WHEN
    scrollTriggerToDistanceBelowView(getScrollContainer(component), 0);
    await waitForIntersectionCheck(component);

    // THEN
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  test("loads the following page when the trigger is still within the threshold after a page loads", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await render(<ScrollableList onLoadMore={onLoadMore} isFetchingNextPage />);
    scrollTriggerToDistanceBelowView(getScrollContainer(component), 0);
    await waitForIntersectionCheck(component);

    // WHEN
    await component.rerender(<ScrollableList onLoadMore={onLoadMore} isFetchingNextPage={false} />);

    // THEN
    await expect.poll(() => onLoadMore).toHaveBeenCalledOnce();
  });

  test("loads more when the trigger is in the browser viewport and no scroll container is given", async () => {
    // GIVEN
    const onLoadMore = vi.fn();

    // WHEN
    await render(<InfiniteTrigger hasNextPage onLoadMore={onLoadMore} />);

    // THEN
    await expect.poll(() => onLoadMore).toHaveBeenCalledOnce();
  });
});
