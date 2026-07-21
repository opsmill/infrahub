import { afterEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import { IP_PREFIX_GENERIC, IPAM_QSP } from "@/entities/ipam/constants";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

import { generateNodeSchema } from "../../../tests/fake/schema";

const ipPrefixSchema = generateNodeSchema({
  kind: "BuiltinIPPrefix",
  name: "IPPrefix",
  namespace: "Builtin",
  inherit_from: [IP_PREFIX_GENERIC],
});

describe("getObjectDetailsUrl", () => {
  afterEach(() => {
    store.set(nodeSchemasAtom, []);
    store.set(genericSchemasAtom, []);
    store.set(profileSchemasAtom, []);
    store.set(templateSchemasAtom, []);
  });

  it("keeps the namespace context for an IP prefix link when passed as an override param", () => {
    store.set(nodeSchemasAtom, [ipPrefixSchema]);

    const url = getObjectDetailsUrl("BuiltinIPPrefix", "prefix-1", [
      { name: IPAM_QSP.NAMESPACE, value: "namespace-1" },
    ]);

    expect(url).toContain("/ipam/BuiltinIPPrefix/prefix-1");
    expect(url).toContain(`${IPAM_QSP.NAMESPACE}=namespace-1`);
  });

  it("does not add a namespace param to an IP prefix link when none is provided", () => {
    store.set(nodeSchemasAtom, [ipPrefixSchema]);

    const url = getObjectDetailsUrl("BuiltinIPPrefix", "prefix-1");

    expect(url).toBe("/ipam/BuiltinIPPrefix/prefix-1");
  });
});
