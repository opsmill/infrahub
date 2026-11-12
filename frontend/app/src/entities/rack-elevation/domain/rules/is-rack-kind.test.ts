import { describe, expect, it } from "vitest";

import { RackElevationRole } from "@/entities/rack-elevation/domain/model/rack-elevation";

import { generateRackElevationKinds } from "../../../../../tests/fake/rack-elevation";
import { generateGenericSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { isRackKind } from "./is-rack-kind";

describe("isRackKind", () => {
  it("accepts a kind that has the rack role", () => {
    const schema = generateNodeSchema({ kind: "LocationRack", inherit_from: [] });

    expect(isRackKind(schema, generateRackElevationKinds())).toBe(true);
  });

  it("accepts a kind that inherits from a generic with the rack role", () => {
    const schema = generateNodeSchema({
      kind: "LocationCabinet",
      inherit_from: ["LocationRackLike"],
    });
    const kinds = [{ kind: "LocationRackLike", role: RackElevationRole.RACK }];

    expect(isRackKind(schema, kinds)).toBe(true);
  });

  it("accepts a generic that has the rack role", () => {
    const schema = generateGenericSchema({ kind: "LocationRackLike" });
    const kinds = [{ kind: "LocationRackLike", role: RackElevationRole.RACK }];

    expect(isRackKind(schema, kinds)).toBe(true);
  });

  it("refuses a kind that has another role", () => {
    const schema = generateNodeSchema({ kind: "DcimDevice", inherit_from: [] });

    expect(isRackKind(schema, generateRackElevationKinds())).toBe(false);
  });

  it("refuses every kind when no kind has a rack role", () => {
    const schema = generateNodeSchema({ kind: "BuiltinTag", inherit_from: [] });

    expect(isRackKind(schema, [])).toBe(false);
  });
});
