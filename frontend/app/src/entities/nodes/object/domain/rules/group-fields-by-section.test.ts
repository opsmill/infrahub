import { describe, expect, it } from "vitest";

import { groupFieldsBySection } from "@/entities/nodes/object/domain/rules/group-fields-by-section";

import { generateContainerSchema } from "../../../../../../tests/fake/schema";

type Item = { name: string; container?: string | null; display?: string };

const getContainer = (item: Item) => item.container;

const sectionNames = (sections: { container: { name: string } }[]) =>
  sections.map((section) => section.container.name);

describe("groupFieldsBySection", () => {
  it("places the Details section first", () => {
    // GIVEN
    const containers = [generateContainerSchema({ name: "lacp", label: "LACP" })];
    const items: Item[] = [
      { name: "lag_mode", container: "lacp" },
      { name: "name", container: null },
    ];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sectionNames(sections)).toEqual(["details", "lacp"]);
    expect(sections[0]).toEqual({
      container: { name: "details", label: "Details", collapsible: false, collapsed: false },
      items: [items[1]],
    });
  });

  it("orders weighted containers before unweighted ones and unweighted ones in declaration order", () => {
    // GIVEN
    const containers = [
      generateContainerSchema({ name: "first_unweighted", order_weight: null }),
      generateContainerSchema({ name: "heavy", order_weight: 2000 }),
      generateContainerSchema({ name: "second_unweighted" }),
      generateContainerSchema({ name: "light", order_weight: 1000 }),
    ];
    const items: Item[] = [
      { name: "a", container: "first_unweighted" },
      { name: "b", container: "heavy" },
      { name: "c", container: "second_unweighted" },
      { name: "d", container: "light" },
    ];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sectionNames(sections)).toEqual([
      "light",
      "heavy",
      "first_unweighted",
      "second_unweighted",
    ]);
  });

  it("places containers with a negative order weight above Details and the others below it", () => {
    // GIVEN
    const containers = [
      generateContainerSchema({ name: "unweighted", order_weight: null }),
      generateContainerSchema({ name: "zero", order_weight: 0 }),
      generateContainerSchema({ name: "near_above", order_weight: -1 }),
      generateContainerSchema({ name: "positive", order_weight: 100 }),
      generateContainerSchema({ name: "far_above", order_weight: -200 }),
    ];
    const items: Item[] = [
      { name: "a", container: "unweighted" },
      { name: "b", container: "zero" },
      { name: "c", container: "near_above" },
      { name: "d", container: "positive" },
      { name: "e", container: "far_above" },
      { name: "name", container: null },
    ];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sectionNames(sections)).toEqual([
      "far_above",
      "near_above",
      "details",
      "zero",
      "positive",
      "unweighted",
    ]);
  });

  it("groups items under a declared container named advanced like any other container", () => {
    // GIVEN
    const containers = [
      generateContainerSchema({
        name: "advanced",
        label: "Tuning",
        collapsed: false,
        order_weight: 1000,
      }),
      generateContainerSchema({ name: "lacp", label: "LACP", order_weight: 2000 }),
    ];
    const items: Item[] = [
      { name: "max_bundle", container: "advanced" },
      { name: "lag_mode", container: "lacp" },
      { name: "name", container: null },
    ];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sectionNames(sections)).toEqual(["details", "advanced", "lacp"]);
    expect(sections[1]?.container).toMatchObject({ label: "Tuning", collapsed: false });
    expect(sections[1]?.items).toEqual([items[0]]);
  });

  it("places an item with container advanced in Details when no such container is declared", () => {
    // GIVEN
    const containers = [generateContainerSchema({ name: "lacp" })];
    const items: Item[] = [
      { name: "max_bundle", container: "advanced" },
      { name: "lag_mode", container: "lacp" },
    ];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sectionNames(sections)).toEqual(["details", "lacp"]);
    expect(sections[0]?.items).toEqual([items[0]]);
  });

  it("drops a container with no item", () => {
    // GIVEN
    const containers = [
      generateContainerSchema({ name: "lacp" }),
      generateContainerSchema({ name: "empty" }),
    ];
    const items: Item[] = [{ name: "lag_mode", container: "lacp" }];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sectionNames(sections)).toEqual(["lacp"]);
  });

  it("keeps extra items in their section", () => {
    // GIVEN
    const containers = [generateContainerSchema({ name: "lacp" })];
    const items: Item[] = [
      { name: "lag_mode", container: "lacp" },
      { name: "lacp_rate", container: "lacp", display: "extra" },
    ];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sections).toHaveLength(1);
    expect(sections[0]?.items).toEqual(items);
    expect(sections[0]?.items[1]).toBe(items[1]);
  });

  it("yields one Details section for a schema without containers", () => {
    // GIVEN
    const items: Item[] = [{ name: "name" }, { name: "description", container: null }];

    // WHEN
    const sections = groupFieldsBySection(undefined, items, getContainer);

    // THEN
    expect(sections).toEqual([
      {
        container: { name: "details", label: "Details", collapsible: false, collapsed: false },
        items,
      },
    ]);
  });

  it("places an item with an undeclared container name in Details", () => {
    // GIVEN
    const containers = [generateContainerSchema({ name: "lacp" })];
    const items: Item[] = [{ name: "orphan", container: "missing" }];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sectionNames(sections)).toEqual(["details"]);
    expect(sections[0]?.items).toEqual(items);
  });

  it("ignores a declared container named details", () => {
    // GIVEN a container named like the Details section, which the schema API refuses
    const containers = [
      generateContainerSchema({ name: "details", label: "General", collapsed: true }),
      generateContainerSchema({ name: "lacp", label: "LACP" }),
    ];
    const items: Item[] = [
      { name: "name", container: null },
      { name: "description", container: "details" },
      { name: "lag_mode", container: "lacp" },
    ];

    // WHEN
    const sections = groupFieldsBySection(containers, items, getContainer);

    // THEN
    expect(sections.map((section) => section.container.label)).toEqual(["Details", "LACP"]);
    expect(sections[0]?.items).toEqual([items[0], items[1]]);
    expect(sections[0]?.container.collapsed).toBe(false);
  });
});
