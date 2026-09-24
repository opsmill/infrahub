import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { createObject } from "@/entities/nodes/object/domain/use-cases/create-object";
import { getObject } from "@/entities/nodes/object/domain/use-cases/get-object";
import { getNumberPools } from "@/entities/resource-manager/domain/use-cases/get-number-pools";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";
import { nodeSchemasAtom, templateSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ServiceCatalogEntry } from "@/entities/service-portal/domain/model/service-catalog";
import { submitServiceRequest } from "@/entities/service-portal/domain/use-cases/submit-service-request";

import { render } from "../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
  generateTemplateSchema,
} from "../../../../tests/fake/schema";
import { ServiceOrderForm } from "./service-order-form";

vi.mock("@/entities/service-portal/domain/use-cases/submit-service-request");
vi.mock("@/entities/resource-manager/domain/use-cases/get-number-pools");
vi.mock("@/entities/nodes/object/domain/use-cases/get-object");
vi.mock("@/entities/nodes/object/domain/use-cases/create-object");

const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router")>()),
  useNavigate: () => mockNavigate,
}));

const attribute = (
  name: string,
  kind: string,
  label: string,
  overrides?: Partial<AttributeSchema>
) =>
  generateAttributeSchema({
    name,
    kind,
    label,
    description: null,
    ...overrides,
  } as Partial<AttributeSchema>);

// Schema order differs from the allowlist order on purpose
const ATTRIBUTES = [
  attribute("name", "Text", "Service name"),
  attribute("hidden_note", "Text", "Internal note"),
  attribute("notes", "TextArea", "Notes"),
  attribute("vlan_id", "Number", "VLAN id"),
  attribute("bandwidth", "Bandwidth", "Bandwidth"),
  attribute("enabled", "Boolean", "Enabled"),
  attribute("managed", "Checkbox", "Managed"),
  attribute("color", "Color", "Color"),
  attribute("start_date", "DateTime", "Start date"),
  attribute("contact_email", "Email", "Contact email"),
  attribute("portal_url", "URL", "Portal URL"),
  attribute("gateway", "IPHost", "Gateway"),
  attribute("subnet", "IPNetwork", "Subnet"),
  attribute("mac", "MacAddress", "MAC address"),
  attribute("secret", "Password", "Secret"),
  attribute("tier", "Dropdown", "Tier", {
    choices: [
      { id: null, state: "present", name: "gold", label: "Gold", description: null, color: null },
    ],
  } as unknown as Partial<AttributeSchema>),
  attribute("dns_servers", "List", "DNS servers"),
  attribute("settings", "JSON", "Settings"),
  attribute("extra", "Any", "Extra"),
];

const ALLOWLIST = [
  "site",
  "tier",
  "vlan_id",
  "name",
  "notes",
  "bandwidth",
  "enabled",
  "managed",
  "color",
  "start_date",
  "contact_email",
  "portal_url",
  "gateway",
  "subnet",
  "mac",
  "secret",
  "dns_servers",
  "settings",
  "extra",
];

const LABEL_BY_NAME: Record<string, string> = {
  site: "Site",
  ...Object.fromEntries(ATTRIBUTES.map((a) => [a.name, a.label])),
};

const targetSchema = generateNodeSchema({
  kind: "ServiceL2Vpn",
  name: "L2Vpn",
  namespace: "Service",
  label: "L2 VPN",
  inherit_from: [],
  attributes: ATTRIBUTES,
  relationships: [
    generateRelationshipSchema({
      name: "site",
      peer: "LocationSite",
      label: "Site",
      cardinality: "one",
      identifier: "service_site",
    }),
    generateRelationshipSchema({
      name: "object_template",
      peer: "TemplateServiceL2Vpn",
      label: "Template",
      kind: "Template",
      cardinality: "one",
      identifier: "node__objecttemplate",
    }),
  ],
});

const templateSchema = generateTemplateSchema({
  kind: "TemplateServiceL2Vpn",
  name: "L2Vpn",
  namespace: "Template",
  attributes: ATTRIBUTES,
  relationships: [],
});

const entry: ServiceCatalogEntry = {
  id: "entry-1",
  name: "Layer 2 VPN",
  description: null,
  icon: null,
  tags: [],
  targetKind: "ServiceL2Vpn",
  mode: "review",
  fields: ALLOWLIST,
  generators: [],
  templateId: null,
};

const getFieldLabels = (container: HTMLElement) =>
  Array.from(container.querySelectorAll("form label[for]")).map((label) =>
    label.textContent?.replace("*", "").trim()
  );

describe("ServiceOrderForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    store.set(nodeSchemasAtom, [targetSchema]);
    store.set(templateSchemasAtom, [templateSchema]);
    vi.mocked(getNumberPools).mockResolvedValue([]);
    vi.mocked(submitServiceRequest).mockResolvedValue({ requestId: "request-1" });
  });

  afterEach(() => {
    store.set(nodeSchemasAtom, []);
    store.set(templateSchemasAtom, []);
  });

  test("renders exactly the allowlisted fields, in allowlist order, with standard widgets", async () => {
    const component = await render(<ServiceOrderForm entry={entry} />);

    await expect.element(component.getByRole("button", { name: "Submit request" })).toBeVisible();

    expect(getFieldLabels(component.container)).toEqual(
      ALLOWLIST.map((name) => LABEL_BY_NAME[name])
    );
    expect(component.container.textContent).not.toContain("Internal note");

    await expect.element(component.getByRole("textbox", { name: "Service name" })).toBeVisible();
    await expect.element(component.getByRole("spinbutton", { name: "VLAN id" })).toBeVisible();
    await expect.element(component.getByRole("checkbox", { name: "True" }).first()).toBeVisible();
    expect(component.container.querySelector("textarea")).not.toBeNull();
  });

  test("submits the create input of the allowlisted fields to ServiceRequestSubmit and opens the request", async () => {
    const component = await render(<ServiceOrderForm entry={entry} />);

    await component.getByRole("textbox", { name: "Service name" }).fill("vpn-paris-lyon");
    await component.getByRole("spinbutton", { name: "VLAN id" }).fill("42");
    await component.getByRole("button", { name: "Submit request" }).click();

    await vi.waitFor(() => expect(submitServiceRequest).toHaveBeenCalledTimes(1));
    const { entryId, inputs = {} } = vi.mocked(submitServiceRequest).mock.lastCall?.[0] ?? {};

    expect(entryId).toBe("entry-1");
    expect(inputs).toMatchObject({ name: { value: "vpn-paris-lyon" }, vlan_id: { value: 42 } });
    for (const key of Object.keys(inputs)) {
      expect(ALLOWLIST).toContain(key.replace(/_from_resource_pool$/, ""));
    }
    expect(inputs).not.toHaveProperty("object_template");
    expect(createObject).not.toHaveBeenCalled();
    await vi.waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith("/service-portal/requests/request-1")
    );
  });

  test("pre-fills visible fields from the entry template without sending untouched template values", async () => {
    vi.mocked(getObject).mockResolvedValue({
      id: "template-1",
      display_label: "Gold VPN",
      __typename: "TemplateServiceL2Vpn",
      name: { value: "gold-vpn", is_from_profile: false },
      hidden_note: { value: "set by the template", is_from_profile: false },
    } as any);

    const component = await render(
      <ServiceOrderForm entry={{ ...entry, templateId: "template-1" }} />
    );

    await expect
      .element(component.getByRole("textbox", { name: "Service name" }))
      .toHaveValue("gold-vpn");
    await component.getByRole("spinbutton", { name: "VLAN id" }).fill("7");
    await component.getByRole("button", { name: "Submit request" }).click();

    await vi.waitFor(() => expect(submitServiceRequest).toHaveBeenCalledTimes(1));
    expect(vi.mocked(submitServiceRequest).mock.lastCall?.[0].inputs).toEqual({
      vlan_id: { value: 7 },
    });
  });

  test("shows a backend field error against the matching field, and other errors on the form", async () => {
    vi.mocked(submitServiceRequest).mockRejectedValue(
      new Error("Bandwidth exceeds the site capacity at bandwidth; Service is paused")
    );

    const component = await render(<ServiceOrderForm entry={entry} />);

    await component.getByRole("textbox", { name: "Service name" }).fill("vpn");
    await component.getByRole("button", { name: "Submit request" }).click();

    const fieldError = component.getByText("Bandwidth exceeds the site capacity at bandwidth");
    await expect.element(fieldError).toBeVisible();
    const bandwidthInput = component.getByRole("spinbutton", { name: "Bandwidth" }).element();
    expect(fieldError.element().previousElementSibling?.contains(bandwidthInput)).toBe(true);
    await expect.element(component.getByText("Service is paused")).toBeVisible();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
