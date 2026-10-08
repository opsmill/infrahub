import { createRef } from "react";
import { afterAll, beforeAll, describe, expect, test } from "vitest";

import type { FormRef } from "@/shared/components/ui/form";
import { store } from "@/shared/stores";

import { AllocatesBlock } from "@/entities/resource-manager/ui/number-pool-form/allocates-block";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";

const interfaceSchema = generateNodeSchema({
  id: "interface",
  kind: "InfraInterface",
  name: "Interface",
  namespace: "Infra",
  label: "Interface",
  attributes: [
    generateAttributeSchema({ name: "speed", label: "Speed", kind: "Number" }),
    generateAttributeSchema({ name: "mtu", label: "MTU", kind: "Number" }),
    generateAttributeSchema({
      name: "if_index",
      label: "Interface index",
      kind: "Number",
      unique: true,
    }),
  ],
});
const vlanSchema = generateNodeSchema({
  id: "vlan",
  kind: "InfraVLAN",
  name: "VLAN",
  namespace: "Infra",
  label: "VLAN",
  attributes: [generateAttributeSchema({ name: "vlan_id", label: "VLAN ID", kind: "Number" })],
});
const tagSchema = generateNodeSchema({ id: "tag", kind: "BuiltinTag" });

describe("AllocatesBlock", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);
  const initialGenericSchemas = store.get(genericSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [interfaceSchema, vlanSchema, tagSchema]);
    store.set(genericSchemasAtom, []);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
    store.set(genericSchemasAtom, initialGenericSchemas);
  });

  describe("read-only variant", () => {
    test("shows the node, attribute and scope as text and badges, without controls", async () => {
      // GIVEN
      const pool = { node: "InfraInterface", attribute: "speed", scope: ["device", "role"] };

      // WHEN
      const component = await render(<AllocatesBlock variant="read-only" {...pool} />);

      // THEN
      await expect.element(component.getByText("Interface Infra")).toBeVisible();
      await expect.element(component.getByText("Speed")).toBeVisible();
      await expect.element(component.getByText("device")).toBeVisible();
      await expect.element(component.getByText("role")).toBeVisible();
      expect(component.getByRole("combobox").elements()).toHaveLength(0);
      expect(component.getByRole("button").elements()).toHaveLength(0);
    });

    test("labels the values without the required asterisk", async () => {
      // GIVEN
      const pool = { node: "InfraInterface", attribute: "speed", scope: [] };

      // WHEN
      const component = await render(<AllocatesBlock variant="read-only" {...pool} />);

      // THEN
      await expect.element(component.getByText("Node", { exact: true })).toBeVisible();
      await expect.element(component.getByText("Attribute", { exact: true })).toBeVisible();
      await expect.element(component.getByText("Node *")).not.toBeInTheDocument();
      await expect.element(component.getByText("Attribute *")).not.toBeInTheDocument();
    });

    test("shows the scope fields with the labels the scope picker uses", async () => {
      // GIVEN
      const pool = { node: "InfraInterface", attribute: "speed", scope: ["mtu", "unknown"] };

      // WHEN
      const component = await render(<AllocatesBlock variant="read-only" {...pool} />);

      // THEN
      const allocates = component.getByRole("group", { name: "What it allocates" });
      await expect.element(allocates.getByText("MTU")).toBeVisible();
      await expect.element(allocates.getByText("unknown")).toBeVisible();
      await expect.element(allocates.getByText("mtu", { exact: true })).not.toBeInTheDocument();
    });

    test("states that a pool without scope is not scoped", async () => {
      // GIVEN
      const pool = { node: "InfraInterface", attribute: "speed", scope: [] };

      // WHEN
      const component = await render(<AllocatesBlock variant="read-only" {...pool} />);

      // THEN
      await expect.element(component.getByText("Not scoped")).toBeVisible();
    });
  });

  describe("input variant", () => {
    test("offers only the nodes that have a number attribute", async () => {
      // GIVEN
      const component = await render(
        <TestForm>
          <AllocatesBlock variant="input" />
        </TestForm>
      );

      // WHEN
      await component.getByRole("combobox", { name: "Node *" }).click();

      // THEN
      await expect
        .element(component.getByRole("option", { name: "Interface Infra" }))
        .toBeVisible();
      await expect.element(component.getByRole("option", { name: "VLAN Infra" })).toBeVisible();
      await expect.element(component.getByRole("option", { name: /Tag/ })).not.toBeInTheDocument();
    });

    test("lists the number attributes of the selected node", async () => {
      // GIVEN
      const component = await render(
        <TestForm defaultValues={{ node: { source: { type: "user" }, value: "InfraInterface" } }}>
          <AllocatesBlock variant="input" />
        </TestForm>
      );

      // WHEN
      await component.getByRole("combobox", { name: "Attribute *" }).click();

      // THEN
      await expect.element(component.getByRole("option", { name: "Speed" })).toBeVisible();
      await expect.element(component.getByRole("option", { name: "MTU" })).toBeVisible();
    });

    test("clears the attribute and the scope when the node changes", async () => {
      // GIVEN
      const formRef = createRef<FormRef>();
      const component = await render(
        <TestForm
          ref={formRef}
          defaultValues={{
            node: { source: { type: "user" }, value: "InfraInterface" },
            node_attribute: { source: { type: "user" }, value: "speed" },
            allocation_scope: ["device"],
          }}
        >
          <AllocatesBlock variant="input" />
        </TestForm>
      );
      await expect
        .element(component.getByRole("combobox", { name: "Attribute *" }))
        .toHaveTextContent("Speed");
      await component.getByRole("combobox", { name: "Node *" }).click();

      // WHEN
      await component.getByRole("option", { name: "VLAN Infra" }).click();

      // THEN
      await expect
        .element(component.getByRole("combobox", { name: "Attribute *" }))
        .not.toHaveTextContent("Speed");
      expect(formRef.current?.getValues()).toMatchObject({
        node_attribute: { source: null, value: null },
        allocation_scope: [],
      });
    });

    test("removes the newly chosen attribute from the scope", async () => {
      // GIVEN
      const formRef = createRef<FormRef>();
      const component = await render(
        <TestForm
          ref={formRef}
          defaultValues={{
            node: { source: { type: "user" }, value: "InfraInterface" },
            node_attribute: { source: { type: "user" }, value: "speed" },
            allocation_scope: ["device", "mtu"],
          }}
        >
          <AllocatesBlock variant="input" />
        </TestForm>
      );
      await component.getByRole("combobox", { name: "Attribute *" }).click();

      // WHEN
      await component.getByRole("option", { name: "MTU" }).click();

      // THEN
      await expect
        .element(component.getByRole("combobox", { name: "Attribute *" }))
        .toHaveTextContent("MTU");
      expect(formRef.current?.getValues("allocation_scope")).toEqual(["device"]);
    });

    test("clears the scope when a unique attribute is chosen", async () => {
      // GIVEN
      const formRef = createRef<FormRef>();
      const component = await render(
        <TestForm
          ref={formRef}
          defaultValues={{
            node: { source: { type: "user" }, value: "InfraInterface" },
            node_attribute: { source: { type: "user" }, value: "speed" },
            allocation_scope: ["device", "mtu"],
          }}
        >
          <AllocatesBlock variant="input" />
        </TestForm>
      );
      await component.getByRole("combobox", { name: "Attribute *" }).click();

      // WHEN
      await component.getByRole("option", { name: "Interface index" }).click();

      // THEN
      await expect
        .element(component.getByRole("combobox", { name: "Attribute *" }))
        .toHaveTextContent("Interface index");
      expect(formRef.current?.getValues("allocation_scope")).toEqual([]);
    });

    test("labels the scope picker with Scoped by", async () => {
      // GIVEN
      const props = { variant: "input" } as const;

      // WHEN
      const component = await render(
        <TestForm>
          <AllocatesBlock {...props} />
        </TestForm>
      );

      // THEN
      const scope = component.getByRole("group", { name: "Scoped by" });
      await expect
        .element(scope.getByRole("button", { name: "No relationship or attribute" }))
        .toBeVisible();
      await expect.element(component.getByText(/The scope is optional/)).toBeVisible();
    });
  });
});
