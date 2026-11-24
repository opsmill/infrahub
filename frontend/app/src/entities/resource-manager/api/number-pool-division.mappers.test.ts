import { describe, expect, it } from "vitest";

import type { NumberPoolDivisionsNode } from "./get-number-pool-divisions-from-api";
import { mapToNumberPoolDivisions } from "./number-pool-division.mappers";

const figures = { size: 100, used: 30, used_default_branch: 28, used_branches: 2, utilization: 30 };

const entry = (path: string, value: unknown, display_label: string, peer_kind: string | null) => ({
  path,
  value,
  display_label,
  peer_kind,
});

describe("mapToNumberPoolDivisions", () => {
  it("maps the fields, the entries and the usage in the backend order", () => {
    // GIVEN
    const node = {
      allocation_scope: [
        { id: "field-1", name: "device" },
        { id: "field-2", name: "role" },
      ],
      divisions: [
        {
          display_label: "atl1-core1 / leaf",
          entries: [
            entry("device", "device-id", "atl1-core1", "InfraDevice"),
            entry("role", "leaf", "leaf", null),
          ],
          figures,
        },
        {
          display_label: "ord1-edge2 / spine",
          entries: [
            entry("device", "other-id", "ord1-edge2", "InfraDevice"),
            entry("role", "spine", "spine", null),
          ],
          figures,
        },
      ],
    } as NumberPoolDivisionsNode;

    // WHEN
    const result = mapToNumberPoolDivisions(node);

    // THEN
    expect(result).toEqual({
      fields: ["device", "role"],
      divisions: [
        {
          label: "atl1-core1 / leaf",
          entries: [
            { path: "device", value: "device-id", label: "atl1-core1", peerKind: "InfraDevice" },
            { path: "role", value: "leaf", label: "leaf", peerKind: null },
          ],
          usage: { size: 100, used: 30, usedDefaultBranch: 28, usedBranches: 2, utilization: 30 },
        },
        {
          label: "ord1-edge2 / spine",
          entries: [
            { path: "device", value: "other-id", label: "ord1-edge2", peerKind: "InfraDevice" },
            { path: "role", value: "spine", label: "spine", peerKind: null },
          ],
          usage: { size: 100, used: 30, usedDefaultBranch: 28, usedBranches: 2, utilization: 30 },
        },
      ],
    });
  });

  it("keeps number and boolean values typed and turns any other value into text", () => {
    // GIVEN
    const node = {
      allocation_scope: [
        { id: "field-1", name: "speed" },
        { id: "field-2", name: "enabled" },
        { id: "field-3", name: "tags" },
      ],
      divisions: [
        {
          display_label: "100 / true / a,b",
          entries: [
            entry("speed", 100, "100", null),
            entry("enabled", true, "true", null),
            entry("tags", ["a", "b"], "a,b", null),
          ],
          figures,
        },
      ],
    } as NumberPoolDivisionsNode;

    // WHEN
    const result = mapToNumberPoolDivisions(node);

    // THEN
    expect(result.divisions[0]?.entries.map(({ value }) => value)).toEqual([100, true, "a,b"]);
  });
});
