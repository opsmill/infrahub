import { afterAll, afterEach, describe, expect, test, vi } from "vitest";

import ObjectForm from "@/shared/components/form/object-form";
import { store } from "@/shared/stores";

import type {
  NodeAttributeWithMetadata,
  NodeCore,
  NodeFieldsWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { IpPoolForm } from "./ip-pool-form";

vi.mock("@/entities/nodes/object/ui/queries/create-object.mutation", () => ({
  useCreateObjectMutation: vi.fn(),
}));

vi.mock("@/entities/nodes/object/ui/queries/update-object.mutation", () => ({
  useUpdateObjectMutation: vi.fn(),
}));

const POOL_CASES = [
  {
    poolKind: IP_PREFIX_POOL,
    poolSchemaLabel: "IP Prefix Pool",
    poolLabel: "IP prefix pool",
    genericKind: "BuiltinIPPrefix",
    fieldName: "default_prefix_type",
    fieldLabel: "Default Prefix Type",
    resource: { kind: "IpamIPPrefix", label: "IP Prefix", namespace: "Ipam" },
    otherResource: { kind: "InfraSubnet", label: "Subnet", namespace: "Infra" },
  },
  {
    poolKind: IP_ADDRESS_POOL,
    poolSchemaLabel: "IP Address Pool",
    poolLabel: "IP address pool",
    genericKind: "BuiltinIPAddress",
    fieldName: "default_address_type",
    fieldLabel: "Default Address Type",
    resource: { kind: "IpamIPAddress", label: "IP Address", namespace: "Ipam" },
    otherResource: { kind: "InfraLoopback", label: "Loopback", namespace: "Infra" },
  },
] as const;

type PoolCase = (typeof POOL_CASES)[number];

const initialNodeSchemas = store.get(nodeSchemasAtom);
const initialGenericSchemas = store.get(genericSchemasAtom);

const savedPool: NodeCore = { id: "pool-id", display_label: "pool-1", __typename: "CorePool" };

interface PoolSchemaOptions {
  usedBy: string[] | null;
  relationships?: RelationshipSchema[];
}

function buildSchemas(poolCase: PoolCase, { usedBy, relationships = [] }: PoolSchemaOptions) {
  const poolSchema = generateNodeSchema({
    kind: poolCase.poolKind,
    namespace: "Core",
    label: poolCase.poolSchemaLabel,
    attributes: [
      generateAttributeSchema({ name: "name", label: "Name", optional: false, order_weight: 1 }),
      generateAttributeSchema({
        name: poolCase.fieldName,
        label: poolCase.fieldLabel,
        optional: true,
        order_weight: 2,
      }),
    ],
    relationships,
  });
  return {
    poolSchema,
    nodeSchemas: [
      poolSchema,
      ...[poolCase.resource, poolCase.otherResource].map((resource) =>
        generateNodeSchema({
          kind: resource.kind,
          label: resource.label,
          namespace: resource.namespace,
        })
      ),
    ],
    genericSchemas: usedBy
      ? [generateGenericSchema({ kind: poolCase.genericKind, used_by: usedBy })]
      : [],
  };
}

function setSchemas(poolCase: PoolCase, options: PoolSchemaOptions) {
  const { poolSchema, nodeSchemas, genericSchemas } = buildSchemas(poolCase, options);
  store.set(nodeSchemasAtom, nodeSchemas);
  store.set(genericSchemasAtom, genericSchemas);
  return poolSchema;
}

function mockMutations() {
  const respond = async (
    _params: unknown,
    callbacks?: { onSuccess?: (node: NodeCore) => unknown }
  ) => {
    await callbacks?.onSuccess?.(savedPool);
    return savedPool;
  };
  const create = vi.fn(respond);
  const update = vi.fn(respond);
  vi.mocked(useCreateObjectMutation).mockReturnValue({ mutateAsync: create } as never);
  vi.mocked(useUpdateObjectMutation).mockReturnValue({ mutateAsync: update } as never);
  return { create, update };
}

function attributeValue(value: string | null): NodeAttributeWithMetadata {
  return {
    value,
    updated_at: "2024-01-01T00:00:00Z",
    is_default: false,
    is_from_profile: false,
    is_protected: false,
    is_visible: true,
    source: null,
    owner: null,
  };
}

function defaultTypeSelect(component: Awaited<ReturnType<typeof render>>, poolCase: PoolCase) {
  return component.getByRole("button", { name: new RegExp(poolCase.fieldLabel) });
}

describe("IpPoolForm", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
    store.set(genericSchemasAtom, initialGenericSchemas);
  });

  test.each(POOL_CASES)(
    "lists every kind that inherits from $genericKind in the $fieldName select",
    async (poolCase) => {
      // GIVEN
      mockMutations();
      setSchemas(poolCase, { usedBy: [poolCase.resource.kind, poolCase.otherResource.kind] });
      const component = await render(<ObjectForm kind={poolCase.poolKind} />);

      // WHEN
      await defaultTypeSelect(component, poolCase).click();

      // THEN
      const options = component.getByRole("option");
      await expect
        .element(options.nth(0))
        .toHaveTextContent(`${poolCase.resource.label}${poolCase.resource.namespace}`);
      await expect
        .element(options.nth(1))
        .toHaveTextContent(`${poolCase.otherResource.label}${poolCase.otherResource.namespace}`);
      expect(options.elements()).toHaveLength(2);
    }
  );

  test.each(POOL_CASES)(
    "preselects the only kind that inherits from $genericKind on create",
    async (poolCase) => {
      // GIVEN
      mockMutations();
      const schema = setSchemas(poolCase, { usedBy: [poolCase.resource.kind] });

      // WHEN
      const component = await render(<IpPoolForm poolKind={poolCase.poolKind} schema={schema} />);

      // THEN
      await expect
        .element(defaultTypeSelect(component, poolCase))
        .toHaveTextContent(`${poolCase.resource.label}${poolCase.resource.namespace}`);
    }
  );

  test.each(POOL_CASES)(
    "preselects nothing when several kinds inherit from $genericKind",
    async (poolCase) => {
      // GIVEN
      mockMutations();
      const schema = setSchemas(poolCase, {
        usedBy: [poolCase.resource.kind, poolCase.otherResource.kind],
      });

      // WHEN
      const component = await render(<IpPoolForm poolKind={poolCase.poolKind} schema={schema} />);

      // THEN
      const select = defaultTypeSelect(component, poolCase);
      await expect.element(select).toBeVisible();
      await expect.element(select).not.toHaveTextContent(poolCase.resource.label);
      await expect.element(select).not.toHaveTextContent(poolCase.otherResource.label);
    }
  );

  test.each(POOL_CASES)(
    "keeps the stored empty $fieldName when editing, even with one kind",
    async (poolCase) => {
      // GIVEN
      mockMutations();
      const schema = setSchemas(poolCase, { usedBy: [poolCase.resource.kind] });
      const currentObject: NodeFieldsWithMetadata = {
        id: "pool-id",
        name: attributeValue("pool-1"),
        [poolCase.fieldName]: attributeValue(null),
      };

      // WHEN
      const component = await render(
        <IpPoolForm
          poolKind={poolCase.poolKind}
          schema={schema}
          currentObject={currentObject}
          isUpdate
        />
      );

      // THEN
      const select = defaultTypeSelect(component, poolCase);
      await expect.element(select).toBeVisible();
      await expect.element(select).not.toHaveTextContent(poolCase.resource.label);
    }
  );

  test.each(POOL_CASES)(
    "shows the raw kind for a $genericKind kind whose schema is not loaded",
    async (poolCase) => {
      // GIVEN
      mockMutations();
      const schema = setSchemas(poolCase, {
        usedBy: [poolCase.resource.kind, "CustomUnloadedKind"],
      });
      const component = await render(<IpPoolForm poolKind={poolCase.poolKind} schema={schema} />);

      // WHEN
      await defaultTypeSelect(component, poolCase).click();

      // THEN
      await expect
        .element(component.getByRole("option", { name: "CustomUnloadedKind", exact: true }))
        .toBeVisible();
    }
  );

  test.each(POOL_CASES)(
    "keeps $fieldName as a text input when $genericKind is not loaded",
    async (poolCase) => {
      // GIVEN
      mockMutations();
      const schema = setSchemas(poolCase, { usedBy: null });

      // WHEN
      const component = await render(<IpPoolForm poolKind={poolCase.poolKind} schema={schema} />);

      // THEN
      await expect
        .element(component.getByRole("textbox", { name: poolCase.fieldLabel, exact: true }))
        .toBeVisible();
    }
  );

  test.each(POOL_CASES)("creates a $poolKind and confirms it", async (poolCase) => {
    // GIVEN
    const { create, update } = mockMutations();
    const onSuccess = vi.fn();
    setSchemas(poolCase, { usedBy: [poolCase.resource.kind] });
    const component = await render(<ObjectForm kind={poolCase.poolKind} onSuccess={onSuccess} />);
    await component.getByRole("textbox", { name: "Name *" }).fill("pool-1");

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect
      .element(component.getByText(`${poolCase.poolLabel} created`, { exact: true }))
      .toBeVisible();
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0]![0]).toEqual({
      objectKind: poolCase.poolKind,
      data: {
        name: { value: "pool-1" },
        [poolCase.fieldName]: { value: poolCase.resource.kind },
      },
    });
    expect(update).not.toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalledWith(savedPool);
  });

  test.each(POOL_CASES)(
    "confirms a $poolKind created while the other IP pool kind's confirmation is on screen",
    async (poolCase) => {
      // GIVEN
      mockMutations();
      const otherCase = POOL_CASES.find(({ poolKind }) => poolKind !== poolCase.poolKind)!;
      const schemas = [otherCase, poolCase].map((pool) =>
        buildSchemas(pool, { usedBy: [pool.resource.kind] })
      );
      store.set(
        nodeSchemasAtom,
        schemas.flatMap(({ nodeSchemas }) => nodeSchemas)
      );
      store.set(
        genericSchemasAtom,
        schemas.flatMap(({ genericSchemas }) => genericSchemas)
      );
      const component = await render(
        <>
          <ObjectForm kind={otherCase.poolKind} />
          <ObjectForm kind={poolCase.poolKind} />
        </>
      );
      const nameInputs = component.getByRole("textbox", { name: "Name *" });
      const saveButtons = component.getByRole("button", { name: "Save" });
      await nameInputs.nth(0).fill("pool-1");
      await saveButtons.nth(0).click();
      await expect
        .element(component.getByText(`${otherCase.poolLabel} created`, { exact: true }))
        .toBeVisible();
      await nameInputs.nth(1).fill("pool-2");

      // WHEN
      await saveButtons.nth(1).click();

      // THEN
      await expect
        .element(component.getByText(`${poolCase.poolLabel} created`, { exact: true }))
        .toBeVisible();
    }
  );

  test.each(POOL_CASES)(
    "updates a $poolKind and confirms it when editing without onSubmit",
    async (poolCase) => {
      // GIVEN
      const { create, update } = mockMutations();
      const schema = setSchemas(poolCase, { usedBy: [poolCase.resource.kind] });
      const currentObject: NodeFieldsWithMetadata = {
        id: "pool-id",
        name: attributeValue("pool-1"),
        [poolCase.fieldName]: attributeValue(poolCase.resource.kind),
      };
      const component = await render(
        <IpPoolForm
          poolKind={poolCase.poolKind}
          schema={schema}
          currentObject={currentObject}
          isUpdate
        />
      );
      await component.getByRole("textbox", { name: "Name *" }).fill("pool-2");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect
        .element(component.getByText(`${poolCase.poolLabel} updated`, { exact: true }))
        .toBeVisible();
      expect(update).toHaveBeenCalledTimes(1);
      expect(update.mock.calls[0]![0]).toMatchObject({
        objectKind: poolCase.poolKind,
        data: { id: "pool-id", name: { value: "pool-2" } },
      });
      expect(create).not.toHaveBeenCalled();
    }
  );

  test.each(POOL_CASES)(
    "hands the values to onSubmit instead of saving a $poolKind",
    async (poolCase) => {
      // GIVEN
      const { create, update } = mockMutations();
      const onSubmit = vi.fn();
      const schema = setSchemas(poolCase, { usedBy: [poolCase.resource.kind] });
      const component = await render(
        <IpPoolForm poolKind={poolCase.poolKind} schema={schema} onSubmit={onSubmit} />
      );
      await component.getByRole("textbox", { name: "Name *" }).fill("pool-1");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSubmit).toHaveBeenCalledTimes(1);
      expect(onSubmit).toHaveBeenCalledWith({
        formData: expect.objectContaining({
          name: { source: { type: "user" }, value: "pool-1" },
          [poolCase.fieldName]: { source: { type: "user" }, value: poolCase.resource.kind },
        }),
        fields: expect.arrayContaining([
          expect.objectContaining({ name: poolCase.fieldName, type: "select" }),
        ]),
      });
      expect(create).not.toHaveBeenCalled();
      expect(update).not.toHaveBeenCalled();
    }
  );

  test.each(POOL_CASES)(
    "creates a $poolKind from the add-new action that pre-fills its parent",
    async (poolCase) => {
      // GIVEN
      const { create, update } = mockMutations();
      // A schema extension can give a pool a parent, which a common_parent relationship then pre-fills.
      setSchemas(poolCase, {
        usedBy: [poolCase.resource.kind],
        relationships: [
          generateRelationshipSchema({
            name: "site",
            label: "Site",
            peer: "LocationSite",
            kind: "Parent",
            cardinality: "one",
            optional: false,
          }),
        ],
      });
      const initialObject: NodeFieldsWithMetadata = {
        site: {
          node: { id: "site-id", display_label: "atl1", __typename: "LocationSite" },
          properties: { is_protected: null, updated_at: null, source: null, owner: null },
        },
      };
      const component = await render(
        <AddRelationshipAction peer={poolCase.poolKind} initialObject={initialObject} />
      );
      await component
        .getByRole("button", { name: `+ Add new ${poolCase.poolSchemaLabel}` })
        .click();
      await component.getByRole("textbox", { name: "Name *" }).fill("pool-1");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect
        .element(component.getByText(`${poolCase.poolLabel} created`, { exact: true }))
        .toBeVisible();
      expect(create).toHaveBeenCalledTimes(1);
      expect(create.mock.calls[0]![0]).toMatchObject({
        objectKind: poolCase.poolKind,
        data: { name: { value: "pool-1" }, site: { id: "site-id" } },
      });
      expect(update).not.toHaveBeenCalled();
    }
  );
});
