import { afterEach, describe, expect, it, vi } from "vitest";

import { getEvents } from "@/entities/events/domain/use-cases/get-events";

import { render } from "../../../../tests/components/render";
import { generateEvent } from "../../../../tests/fake/event";
import { NodeEvents } from "./node-details-events";

vi.mock("@/entities/events/domain/use-cases/get-events", () => ({ getEvents: vi.fn() }));

const getEventsMock = vi.mocked(getEvents);

describe("NodeEvents", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("asks for 50 sub-activities, the most the events API returns in one request", async () => {
    // GIVEN
    getEventsMock.mockResolvedValue([generateEvent({ id: "child-0" })]);

    // WHEN
    await render(<NodeEvents parentId="parent-event" />);

    // THEN
    await expect
      .poll(() => getEventsMock.mock.calls[0]?.[0])
      .toEqual({ parentIds: ["parent-event"], relatedNodeIds: undefined, limit: 50 });
  });
});
