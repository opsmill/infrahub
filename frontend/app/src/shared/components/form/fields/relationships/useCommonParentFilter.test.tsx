import { useFormContext, useWatch } from "react-hook-form";
import { describe, expect, test } from "vitest";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import { generateRelationshipSchema } from "../../../../../../tests/fake/schema";
import { useCommonParentFilter } from "./useCommonParentFilter";

const Probe = ({ commonParent }: { commonParent?: string | null }) => {
  const relationship = generateRelationshipSchema({ common_parent: commonParent ?? null });
  const result = useCommonParentFilter(relationship, "dependent");
  return <div data-testid="result">{JSON.stringify(result)}</div>;
};

const parentValue = {
  source: { type: "user" as const },
  value: { id: "dev-1", display_label: "atl1-edge", __typename: "InfraDevice" },
};

describe("useCommonParentFilter", () => {
  test("is inactive when the relationship declares no common_parent", async () => {
    const component = await render(
      <TestForm>
        <Probe commonParent={null} />
      </TestForm>
    );

    await expect
      .element(component.getByTestId("result"))
      .toHaveTextContent(JSON.stringify({ isActive: false }));
  });

  test("returns no filter while the sibling field is empty", async () => {
    const component = await render(
      <TestForm>
        <Probe commonParent="device" />
      </TestForm>
    );

    await expect
      .element(component.getByTestId("result"))
      .toHaveTextContent(JSON.stringify({ isActive: true, parent: { name: "device" } }));
  });

  test("builds the single-hop filter from the picked sibling parent", async () => {
    const component = await render(
      <TestForm defaultValues={{ device: parentValue }}>
        <Probe commonParent="device" />
      </TestForm>
    );

    await expect.element(component.getByTestId("result")).toHaveTextContent(
      JSON.stringify({
        isActive: true,
        filterQuery: { device__ids: ["dev-1"] },
        parent: { name: "device", value: "dev-1" },
        addNewInitialObject: {
          device: { node: { id: "dev-1", display_label: "atl1-edge", __typename: "InfraDevice" } },
        },
      })
    );
  });
});

// Harness that reads the dependent field value and lets the test change the parent.
const ClearHarness = () => {
  const relationship = generateRelationshipSchema({ name: "profile", common_parent: "device" });
  useCommonParentFilter(relationship, "profile");
  const form = useFormContext();
  const dependent = useWatch({ name: "profile" });

  return (
    <div>
      <div data-testid="dependent">{JSON.stringify(dependent)}</div>
      <button
        type="button"
        onClick={() =>
          form.setValue("device", {
            source: { type: "user" as const },
            value: { id: "dev-2", display_label: "dc2", __typename: "InfraDevice" },
          })
        }
      >
        change parent
      </button>
    </div>
  );
};

describe("useCommonParentFilter - clears the selection on parent change", () => {
  test("keeps the pre-filled selection on mount but clears it when the parent changes", async () => {
    const selected = {
      source: { type: "user" as const },
      value: { id: "profile-1", display_label: "p1-alpha-dc1", __typename: "TestProfile" },
    };

    const component = await render(
      <TestForm defaultValues={{ device: parentValue, profile: selected }}>
        <ClearHarness />
      </TestForm>
    );

    // Preserved on mount.
    await expect.element(component.getByTestId("dependent")).toHaveTextContent("profile-1");

    // Changing the parent clears the now out-of-filter selection.
    await component.getByRole("button", { name: "change parent" }).click();
    await expect
      .element(component.getByTestId("dependent"))
      .toHaveTextContent(JSON.stringify({ source: null, value: null }));
  });
});
