import { ApolloProvider } from "@apollo/client";
import { afterEach, describe, expect, test } from "vitest";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { namespacesAtom } from "@/entities/schema/stores/schema.atom";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/types";
import { store } from "@/shared/stores";

import { render } from "../../../../tests/components/render";
import { Dropdown } from "./dropdown";

const field = { name: "status" } as AttributeSchema;
const items = [
  { value: "default", label: "Default" },
  { value: "internal", label: "Internal" },
];

const renderDropdown = (ui: React.ReactElement) =>
  render(<ApolloProvider client={graphqlClient}>{ui}</ApolloProvider>);

describe("Dropdown delete button", () => {
  afterEach(() => {
    store.set(namespacesAtom, []);
  });

  test("hides the delete button when the namespace is not user-editable", async () => {
    // GIVEN a field on a non-user-editable namespace (e.g. Core)
    store.set(namespacesAtom, [{ name: "Core", user_editable: false }]);
    const schema = { kind: "CoreStandardGroup", namespace: "Core" } as ModelSchema;

    // WHEN the dropdown options are shown
    const component = await renderDropdown(
      <Dropdown
        items={items}
        value="default"
        schema={schema}
        field={field}
        onChange={() => {}}
        defaultOpen
      />
    );

    // THEN no delete button is rendered for the protected options
    await expect.element(component.getByText("Internal")).toBeVisible();
    await expect
      .poll(() => component.getByRole("button", { name: "Delete option" }).query())
      .toBeNull();
  });

  test("shows the delete button when the namespace is user-editable", async () => {
    // GIVEN a field on a user-editable namespace
    store.set(namespacesAtom, [{ name: "Builtin", user_editable: true }]);
    const schema = { kind: "MyCustomNode", namespace: "Builtin" } as ModelSchema;

    // WHEN the dropdown options are shown
    const component = await renderDropdown(
      <Dropdown
        items={items}
        value="default"
        schema={schema}
        field={field}
        onChange={() => {}}
        defaultOpen
      />
    );

    // THEN a delete button is rendered for the editable options
    await expect.element(component.getByText("Internal")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Delete option" }).first())
      .toBeVisible();
  });
});
