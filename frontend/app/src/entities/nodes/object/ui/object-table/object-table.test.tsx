import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { Col } from "@/shared/components/container";

import { getObjects } from "@/entities/nodes/object/domain/use-cases/get-objects";
import { getObjectsCount } from "@/entities/nodes/object/domain/use-cases/get-objects-count";
import { ObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/domain/model/permission";

import { render } from "../../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../../tests/fake/schema";
import { ObjectTable } from "./object-table";

vi.mock("@/entities/nodes/object/domain/use-cases/get-objects");
vi.mock("@/entities/nodes/object/domain/use-cases/get-objects-count");

const schema = generateNodeSchema({
  kind: "TestingOnboardingStatus",
  label: "Device Onboarding Status",
  relationships: [],
  attributes: [
    "AAA Onboarded",
    "Monitoring Onboarded",
    "DNS Onboarded",
    "TACACS Key Updated",
    "Configuration Deployment",
  ].map((label, index) =>
    generateAttributeSchema({ name: `status_${index}`, label, kind: "Boolean" })
  ),
});

function TestTable({ className }: { className: string }) {
  return (
    <Col className={className} data-testid="table-container">
      <ObjectTableContext
        value={{
          filters: [],
          setFilters: vi.fn(),
          baseSchema: schema,
          selectedSchema: schema,
          permission: PERMISSION_ALLOW_ALL,
        }}
      >
        <ObjectTable />
      </ObjectTableContext>
    </Col>
  );
}

describe("ObjectTable horizontal scrolling", () => {
  beforeEach(() => {
    vi.mocked(getObjectsCount).mockResolvedValue(1);
    vi.mocked(getObjects).mockResolvedValue([
      {
        id: "device-1",
        __typename: schema.kind,
        status_0: { value: true },
        status_1: { value: false },
        status_2: { value: true },
        status_3: { value: false },
        status_4: { value: false },
      },
    ]);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows a usable horizontal scrollbar without hovering when columns overflow", async () => {
    // GIVEN
    const component = await render(<TestTable className="h-60 w-[600px]" />);

    // WHEN
    await expect.element(component.getByRole("link", { name: "device-1" })).toBeVisible();

    // THEN
    const viewport = component.container.querySelector<HTMLElement>(
      "[data-radix-scroll-area-viewport]"
    );
    expect(viewport).not.toBeNull();
    if (!viewport) throw new Error("Table viewport is missing");
    expect(viewport.scrollWidth).toBeGreaterThan(viewport.clientWidth);
    await expect
      .poll(() => component.container.querySelector('[data-orientation="horizontal"]'))
      .not.toBeNull();
    const scrollbar = component.container.querySelector<HTMLElement>(
      '[data-orientation="horizontal"]'
    );
    if (!scrollbar) throw new Error("Horizontal scrollbar is missing");
    await expect.element(scrollbar).toBeVisible();
    expect(scrollbar.getBoundingClientRect().height).toBeGreaterThanOrEqual(8);
    viewport.scrollLeft = viewport.scrollWidth;
    expect(viewport.scrollLeft).toBeGreaterThan(0);
  });

  test.each([
    { from: "w-[1200px]", to: "w-[600px]", visible: true },
    { from: "w-[600px]", to: "w-[1200px]", visible: false },
  ])("sets scrollbar visibility to $visible after resizing from $from to $to", async ({
    from,
    to,
    visible,
  }) => {
    // GIVEN
    const component = await render(<TestTable className={`h-60 ${from}`} />);
    await expect.element(component.getByRole("link", { name: "device-1" })).toBeVisible();

    // WHEN
    await component.rerender(<TestTable className={`h-60 ${to}`} />);

    // THEN
    await expect
      .poll(() => !!component.container.querySelector('[data-orientation="horizontal"]'))
      .toBe(visible);
  });
});
