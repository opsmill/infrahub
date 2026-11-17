import type React from "react";
import { TagGroup, TagList } from "react-aria-components";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { QSP } from "@/shared/config/qsp";
import { store } from "@/shared/stores";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { EventFilterTag, type EventFilterTagProps } from "./event-filter-tag";
import { GlobalEventsFilters } from "./global-events-filters";

const eventTypeFilter: Filter = { name: "eventType__value", value: "infrahub.node.created" };

function renderTag(props: Partial<EventFilterTagProps> = {}) {
  return render(
    <TagGroup aria-label="Filter group">
      <TagList>
        <EventFilterTag
          label="Event Type"
          renderValue={() => "Node created"}
          onRemove={() => {}}
          renderForm={() => <p className="min-w-64">Event type form</p>}
          {...props}
        />
      </TagList>
    </TagGroup>
  );
}

function seedFilters(filters: Filter[]) {
  window.history.replaceState(
    null,
    "",
    `/?${QSP.FILTER}=${encodeURIComponent(JSON.stringify(filters))}`
  );
}

function getAppliedFilters(): Filter[] {
  const raw = new URLSearchParams(window.location.search).get(QSP.FILTER);

  return raw ? JSON.parse(raw) : [];
}

function getIcon(container: HTMLElement, icon: string) {
  return container.querySelector(`iconify-icon[icon="${icon}"]`);
}

describe("EventFilterTag", () => {
  it("shows the add icon and does not format a value when the filter has none", async () => {
    // GIVEN
    const renderValue = vi.fn((): React.ReactNode => "Node created");

    // WHEN
    const component = await renderTag({ renderValue });

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Event Type", exact: true }))
      .toBeVisible();
    expect(getIcon(component.container, "mdi:plus-circle-outline")).not.toBeNull();
    expect(getIcon(component.container, "mdi:close-circle-outline")).toBeNull();
    expect(renderValue).not.toHaveBeenCalled();
  });

  it("shows a false value instead of the add icon", async () => {
    // GIVEN
    const currentFilter: Filter = { name: "hasChildren__value", value: false };

    // WHEN
    const component = await renderTag({
      label: "Has Children",
      currentFilter,
      renderValue: () => JSON.stringify(currentFilter.value),
    });

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Has Children false", exact: true }))
      .toBeVisible();
    expect(getIcon(component.container, "mdi:plus-circle-outline")).toBeNull();
  });

  it("removes the value without opening the form when the value is clicked", async () => {
    // GIVEN
    const onRemove = vi.fn();
    const component = await renderTag({ currentFilter: eventTypeFilter, onRemove });

    // WHEN
    await component.getByText("Node created", { exact: true }).click();

    // THEN
    expect(onRemove).toHaveBeenCalledOnce();
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the form under a 'Filter by' tab when the trigger is clicked", async () => {
    // GIVEN
    const component = await renderTag();

    // WHEN
    await component.getByRole("button", { name: "Event Type", exact: true }).click();

    // THEN
    const dialog = component.getByRole("dialog");
    await expect.element(dialog.getByText("Filter by")).toBeVisible();
    await expect.element(dialog.getByText("Event Type", { exact: true })).toBeVisible();
    await expect.element(dialog.getByText("Event type form")).toBeVisible();
  });

  it("closes the form when the form calls close", async () => {
    // GIVEN
    const component = await renderTag({
      renderForm: (close) => (
        <button type="button" className="min-w-64" onClick={close}>
          Done
        </button>
      ),
    });
    await component.getByRole("button", { name: "Event Type", exact: true }).click();

    // WHEN
    await component.getByRole("button", { name: "Done" }).click();

    // THEN
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
  });

  it("names the tag after its tag label and current value", async () => {
    // GIVEN
    const props = {
      label: "Branch",
      tagLabel: "branches",
      currentFilter: { name: "branches__value", value: "main" },
      renderValue: () => "main",
    };

    // WHEN
    const component = await renderTag(props);

    // THEN
    await expect
      .element(component.getByRole("row", { name: "branches contains main", exact: true }))
      .toBeVisible();
  });

  it("shows the tab label in the 'Filter by' tab", async () => {
    // GIVEN
    const component = await renderTag({ label: "Branch", tabLabel: "branch" });

    // WHEN
    await component.getByRole("button", { name: "Branch", exact: true }).click();

    // THEN
    await expect
      .element(component.getByRole("dialog").getByText("branch", { exact: true }))
      .toBeVisible();
  });
});

describe("GlobalEventsFilters", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({ kind: "BuiltinTag", display_labels: ["name__value"] }),
    ]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  it("removes only the event type filter when its value is clicked", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      eventTypeFilter,
      { name: "hasChildren__value", value: true },
    ]);
    const component = await render(<GlobalEventsFilters />);

    // WHEN
    await component.getByText("Node created", { exact: true }).click();

    // THEN
    await expect.poll(getAppliedFilters).toEqual([
      { name: "branches__value", value: "main" },
      { name: "hasChildren__value", value: true },
    ]);
  });

  it("keeps a null branch filter when the branch value is clicked", async () => {
    // GIVEN
    seedFilters([{ name: "branches__value", value: "main" }]);
    const component = await render(<GlobalEventsFilters />);

    // WHEN
    await component.getByText("main", { exact: true }).click();

    // THEN
    await expect.poll(getAppliedFilters).toEqual([{ name: "branches__value", value: null }]);
  });

  it("shows the branch tag with its own accessible name and value", async () => {
    // GIVEN
    seedFilters([{ name: "branches__value", value: "main" }]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("row", { name: "branches contains main" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Branch main", exact: true }))
      .toBeVisible();
  });

  it("shows a false Has Children value", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      { name: "hasChildren__value", value: false },
    ]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Has Children false", exact: true }))
      .toBeVisible();
  });

  it("shows the node labels of a primary node filter", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      {
        name: "primaryNodeIds__value",
        value: [{ id: "tag-1", __typename: "BuiltinTag", display_label: "blue" }],
      },
    ]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Primary Node blue", exact: true }))
      .toBeVisible();
  });

  it("shows a primary node filter without a value as empty", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      { name: "primaryNodeIds__value", value: null },
    ]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Primary Node", exact: true }))
      .toBeVisible();
  });

  it("applies a Has Children value and closes the form", async () => {
    // GIVEN
    seedFilters([{ name: "branches__value", value: "main" }]);
    const component = await render(<GlobalEventsFilters />);
    await component.getByRole("button", { name: "Has Children", exact: true }).click();
    await component.getByText("True", { exact: true }).click();

    // WHEN
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    await expect.poll(getAppliedFilters).toEqual([
      { name: "branches__value", value: "main" },
      { name: "hasChildren__value", value: true },
    ]);
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
  });
});
