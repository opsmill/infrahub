import { describe, expect, test } from "vitest";

import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import { isReadOnlyRepository } from "@/entities/repository/domain/rules/is-read-only-repository";

import { generateNodeSchema } from "../../../../../tests/fake/schema";

describe("isReadOnlyRepository", () => {
  test("is true for the read-only repository kind", () => {
    expect(isReadOnlyRepository(generateNodeSchema({ kind: READONLY_REPOSITORY_KIND }))).toBe(true);
  });

  test("is true for a kind that inherits from the read-only repository", () => {
    expect(
      isReadOnlyRepository(
        generateNodeSchema({
          kind: "CustomReadOnlyRepository",
          inherit_from: [READONLY_REPOSITORY_KIND],
        })
      )
    ).toBe(true);
  });

  test("is false for a read-write repository", () => {
    expect(isReadOnlyRepository(generateNodeSchema({ kind: REPOSITORY_KIND }))).toBe(false);
  });
});
