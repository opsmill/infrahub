import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { getRackElevationFromApi } from "@/entities/rack-elevation/api/get-rack-elevation-from-api";
import { getRackElevationKindsFromApi } from "@/entities/rack-elevation/api/get-rack-elevation-kinds-from-api";
import { placeRackItemFromApi } from "@/entities/rack-elevation/api/place-rack-item-from-api";

import { render } from "../../../../tests/components/render";
import {
  generateRackElevationKinds,
  generateRackR1Elevation,
  RACK_ID,
} from "../../../../tests/fake/rack-elevation";
import { RackElevationView } from "./rack-elevation-view";

vi.mock("@/entities/rack-elevation/api/get-rack-elevation-from-api");
vi.mock("@/entities/rack-elevation/api/get-rack-elevation-kinds-from-api");
vi.mock("@/entities/rack-elevation/api/place-rack-item-from-api");

const REFUSAL_MESSAGE = "Units 12-13 do not exist in rack R1 (12U)";

const getElevationMock = vi.mocked(getRackElevationFromApi);
const getKindsMock = vi.mocked(getRackElevationKindsFromApi);
const placeItemMock = vi.mocked(placeRackItemFromApi);

const getMountedPosition = (name: string) =>
  document.querySelector(`[data-testid="rack-item-${name}"]`)?.getAttribute("data-position");

describe("RackElevationView", () => {
  beforeEach(() => {
    getElevationMock.mockResolvedValue({ data: { RackElevation: generateRackR1Elevation() } });
    getKindsMock.mockResolvedValue({ data: { RackElevationKinds: generateRackElevationKinds() } });
    placeItemMock.mockResolvedValue({
      data: {
        RackElevationPlace: {
          ok: true,
          item: { id: "item-spare1", position: 5, face: "FRONT", placement: "MOUNTED" },
        },
      },
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows the totals of the rack above the drawing", async () => {
    // WHEN
    const component = await render(<RackElevationView rackId={RACK_ID} />);

    // THEN
    await expect
      .element(component.getByTestId("rack-elevation-totals"))
      .toHaveTextContent("5 / 12 U used41% utilizationTotal weight: 57 kg");
  });

  test("lists the items without a unit and the 0U items next to the drawing", async () => {
    // WHEN
    const component = await render(<RackElevationView rackId={RACK_ID} />);

    // THEN
    await expect
      .element(component.getByTestId("rack-list-unpositioned").getByTestId("rack-item-spare1"))
      .toBeVisible();
    await expect
      .element(component.getByTestId("rack-list-zero-u").getByTestId("rack-item-pdu1"))
      .toBeVisible();
  });

  test("moves an item without a unit to the clicked unit and face", async () => {
    // GIVEN
    const component = await render(<RackElevationView rackId={RACK_ID} />);
    await component.getByTestId("rack-list-unpositioned").getByTestId("rack-item-spare1").click();

    // WHEN
    await component.getByTestId("rack-unit-front-5").click();

    // THEN
    await vi.waitFor(() =>
      expect(placeItemMock).toHaveBeenCalledWith(
        expect.objectContaining({
          rackId: RACK_ID,
          itemId: "item-spare1",
          position: 5,
          face: "FRONT",
          branchName: "test-branch",
        })
      )
    );
  });

  test("moves a mounted item from its Move button to the rear face", async () => {
    // GIVEN
    const component = await render(<RackElevationView rackId={RACK_ID} />);
    await component.getByTestId("rack-item-move-leaf2").click();

    // WHEN
    await component.getByTestId("rack-unit-rear-3").click();

    // THEN
    await vi.waitFor(() =>
      expect(placeItemMock).toHaveBeenCalledWith(
        expect.objectContaining({ itemId: "item-leaf2", position: 3, face: "REAR" })
      )
    );
  });

  test("moves an item dropped on a free unit", async () => {
    // GIVEN
    const component = await render(<RackElevationView rackId={RACK_ID} />);

    // WHEN
    await userEvent.dragAndDrop(
      component.getByTestId("rack-item-leaf2").first(),
      component.getByTestId("rack-unit-front-5")
    );

    // THEN
    await vi.waitFor(() =>
      expect(placeItemMock).toHaveBeenCalledWith(
        expect.objectContaining({ itemId: "item-leaf2", position: 5, face: "FRONT" })
      )
    );
  });

  test("shows the reason of a refused move and leaves the drawing unchanged", async () => {
    // GIVEN
    placeItemMock.mockRejectedValue(new Error(REFUSAL_MESSAGE));
    const component = await render(<RackElevationView rackId={RACK_ID} />);
    await component.getByTestId("rack-item-move-srv1").click();

    // WHEN
    await component.getByTestId("rack-unit-front-12").click();

    // THEN
    await expect.element(component.getByText(REFUSAL_MESSAGE)).toBeVisible();
    expect(getMountedPosition("srv1")).toBe("1");
    await expect.element(component.getByTestId("rack-list-unpositioned")).toBeVisible();
    expect(getElevationMock).toHaveBeenCalledTimes(1);
  });

  test("leaves move mode on Escape", async () => {
    // GIVEN
    const component = await render(<RackElevationView rackId={RACK_ID} />);
    await component.getByTestId("rack-list-unpositioned").getByTestId("rack-item-spare1").click();
    await expect.element(component.getByText(/press Escape to cancel/)).toBeVisible();

    // WHEN
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(component.getByText(/press Escape to cancel/).query()).toBeNull();
    expect(component.getByTestId("rack-unit-front-12").query()).toBeNull();
  });

  test("places an item without a unit from the sheet opened by a free unit", async () => {
    // GIVEN
    const component = await render(<RackElevationView rackId={RACK_ID} />);
    await component.getByTestId("rack-unit-front-7").click();

    // WHEN
    await component.getByTestId("rack-place-spare1").click();

    // THEN
    await vi.waitFor(() =>
      expect(placeItemMock).toHaveBeenCalledWith(
        expect.objectContaining({ itemId: "item-spare1", position: 7, face: "FRONT" })
      )
    );
  });
});
