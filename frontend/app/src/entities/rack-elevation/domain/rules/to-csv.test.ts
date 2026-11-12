import { describe, expect, it } from "vitest";

import {
  generateRackElevationItem,
  generateRackR1Elevation,
} from "../../../../../tests/fake/rack-elevation";
import { toCsv } from "./to-csv";

describe("toCsv", () => {
  it("writes a header and one line per item", () => {
    // GIVEN
    const { rack, items } = generateRackR1Elevation();

    // WHEN
    const lines = toCsv(rack, items).split("\n");

    // THEN
    expect(lines).toHaveLength(items.length + 1);
    expect(lines[0]).toBe("rack,unit,face,label,type,height,placement");
  });

  it("writes the unit, face and placement of each item", () => {
    // GIVEN
    const { rack, items } = generateRackR1Elevation();

    // WHEN
    const lines = toCsv(rack, items).split("\n");

    // THEN
    expect(lines).toContain("R1,12,front,leaf1,Switch 1U,1,mounted");
    expect(lines).toContain("R1,10,rear,pp1,Patch panel 1U,1,mounted");
    expect(lines).toContain("R1,,,spare1,Switch 1U,1,unpositioned");
    expect(lines).toContain("R1,,,pdu1,Vertical PDU,0,zero_u");
  });

  it("quotes a field that holds a comma or a quote", () => {
    // GIVEN
    const { rack } = generateRackR1Elevation();
    const items = [generateRackElevationItem({ display_label: 'a,"b"', label: 'a,"b"' })];

    // WHEN
    const lines = toCsv(rack, items).split("\n");

    // THEN
    expect(lines[1]).toBe('R1,,,"a,""b""",,1,mounted');
  });

  it("keeps a label that starts with a formula character from running as a formula", () => {
    // GIVEN
    const { rack } = generateRackR1Elevation();
    const items = [generateRackElevationItem({ display_label: "x", label: "=SUM(A1)" })];

    // WHEN
    const lines = toCsv(rack, items).split("\n");

    // THEN
    expect(lines[1]).toBe("R1,,,'=SUM(A1),,1,mounted");
  });
});
