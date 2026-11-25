import { describe, expect, test } from "vitest";

import infrahubMarkSvg from "@/assets/infrahub-mark.svg?raw";

import { recolorInfrahubMark } from "@/entities/preferences/domain/rules/recolor-infrahub-mark";

describe("recolorInfrahubMark", () => {
  test("replaces the accent and the outline colors and leaves every other color unchanged", () => {
    // GIVEN
    const svg = [
      '<path fill="#0B97BB" />',
      '<stop stop-color="#0B97BB" />',
      '<stop offset="1" stop-color="#0B1828" />',
      '<stop stop-color="#264D59" />',
      '<stop offset="1" stop-color="#0C3E54" />',
      '<path fill="white" />',
    ].join("");

    // WHEN
    const recolored = recolorInfrahubMark(svg, "#e11d48");

    // THEN
    expect(recolored).toBe(
      [
        '<path fill="#e11d48" />',
        '<stop stop-color="#e11d48" />',
        '<stop offset="1" stop-color="#0B1828" />',
        '<stop stop-color="#e11d48" />',
        '<stop offset="1" stop-color="#e11d48" />',
        '<path fill="white" />',
      ].join("")
    );
  });

  test("recolors the five accent and outline paints of the Infrahub mark", () => {
    // WHEN
    const recolored = recolorInfrahubMark(infrahubMarkSvg, "#e11d48");

    // THEN
    expect(recolored.split("#e11d48")).toHaveLength(6);
    expect(recolored).not.toMatch(/#0B97BB|#264D59|#0C3E54/i);
    expect(recolored.split("#0B1828")).toHaveLength(3);
  });
});
