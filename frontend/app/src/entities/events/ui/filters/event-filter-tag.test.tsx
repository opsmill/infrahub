import type React from "react";
import { TagGroup, TagList } from "react-aria-components";
import { describe, expect, it, vi } from "vitest";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

import { render } from "../../../../../tests/components/render";
import { EventFilterTag, type EventFilterTagProps } from "./event-filter-tag";

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
