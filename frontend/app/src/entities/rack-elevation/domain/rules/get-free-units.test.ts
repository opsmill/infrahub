import { describe, expect, it } from "vitest";

import { RackItemPlacement } from "@/entities/rack-elevation/domain/model/rack-elevation";

import {
  generateRackElevationItem,
  generateRackR1Elevation,
} from "../../../../../tests/fake/rack-elevation";
import { getFreeUnits, getPlacementTargets } from "./get-free-units";

describe("getFreeUnits", () => {
  it("returns the units between the mounted items on each face", () => {
    // GIVEN
    const { rack, items } = generateRackR1Elevation();

    // WHEN
    const freeUnits = getFreeUnits({ items, uHeight: rack.u_height });

    // THEN
    expect(freeUnits.FRONT).toEqual([{ start: 3, end: 9 }]);
    expect(freeUnits.REAR).toEqual([{ start: 3, end: 9 }]);
  });

  it("treats the units of a full depth item as used on both faces", () => {
    // GIVEN
    const items = [
      generateRackElevationItem({
        display_label: "srv",
        position: 2,
        face: "FRONT",
        u_height: 2,
        full_depth: true,
      }),
    ];

    // WHEN
    const freeUnits = getFreeUnits({ items, uHeight: 5 });

    // THEN
    expect(freeUnits.REAR).toEqual([
      { start: 1, end: 1 },
      { start: 4, end: 5 },
    ]);
  });

  it("uses the units of a half depth item on its own face only", () => {
    // GIVEN
    const items = [
      generateRackElevationItem({
        display_label: "panel",
        position: 1,
        face: "REAR",
        full_depth: false,
      }),
    ];

    // WHEN
    const freeUnits = getFreeUnits({ items, uHeight: 3 });

    // THEN
    expect(freeUnits.FRONT).toEqual([{ start: 1, end: 3 }]);
    expect(freeUnits.REAR).toEqual([{ start: 2, end: 3 }]);
  });

  it("ignores items that are not mounted", () => {
    // GIVEN
    const items = [
      generateRackElevationItem({
        display_label: "spare",
        placement: RackItemPlacement.UNPOSITIONED,
      }),
    ];

    // WHEN
    const freeUnits = getFreeUnits({ items, uHeight: 2 });

    // THEN
    expect(freeUnits.FRONT).toEqual([{ start: 1, end: 2 }]);
  });
});

describe("getPlacementTargets", () => {
  it("lists the units where an item of the same height fits", () => {
    // GIVEN
    const { rack, items } = generateRackR1Elevation();
    const movingItem = items.find(({ display_label }) => display_label === "spare1");
    if (!movingItem) throw new Error("spare1 is missing from the fixture");

    // WHEN
    const targets = getPlacementTargets({ items, uHeight: rack.u_height, movingItem });

    // THEN
    expect([...targets.FRONT]).toEqual([3, 4, 5, 6, 7, 8, 9]);
    expect([...targets.REAR]).toEqual([3, 4, 5, 6, 7, 8, 9]);
  });

  it("counts the units the moving item uses now as free", () => {
    // GIVEN
    const { rack, items } = generateRackR1Elevation();
    const movingItem = items.find(({ display_label }) => display_label === "srv1");
    if (!movingItem) throw new Error("srv1 is missing from the fixture");

    // WHEN
    const targets = getPlacementTargets({ items, uHeight: rack.u_height, movingItem });

    // THEN
    expect([...targets.FRONT]).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  });

  it("offers no unit to a 0U item", () => {
    // GIVEN
    const { rack, items } = generateRackR1Elevation();
    const movingItem = items.find(({ display_label }) => display_label === "pdu1");
    if (!movingItem) throw new Error("pdu1 is missing from the fixture");

    // WHEN
    const targets = getPlacementTargets({ items, uHeight: rack.u_height, movingItem });

    // THEN
    expect(targets.FRONT.size).toBe(0);
    expect(targets.REAR.size).toBe(0);
  });
});
