import React from "react";
import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";
import { InfiniteTrigger } from "./infinite-trigger";

interface ScrollableListProps {
  onLoadMore: () => void;
}

const ScrollableList = ({ onLoadMore }: ScrollableListProps) => {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  return (
    <div ref={scrollRef} data-testid="scroll-container" className="h-25 overflow-auto">
      <div className="h-100" />
      <InfiniteTrigger hasNextPage onLoadMore={onLoadMore} rootRef={scrollRef} />
    </div>
  );
};

describe("InfiniteTrigger", () => {
  test("loads more once the trigger is within the threshold below a scroll container's visible area", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await render(<ScrollableList onLoadMore={onLoadMore} />);
    const scrollContainer = component.getByTestId("scroll-container").element();

    // WHEN
    scrollContainer.scrollTop = 150;

    // THEN
    await expect.poll(() => onLoadMore).toHaveBeenCalled();
  });
});
