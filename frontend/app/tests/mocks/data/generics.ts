import { iGenericSchema } from "../../../src/state/atoms/schema.atom";
import { deviceDetailsMocksGenerics } from "./devices";

export const genericsMocks: iGenericSchema[] = [
  {
    id: "da5ab3da-621b-4e90-b543-f6f8eb9860a2",
    name: "Endpoint",
    namespace: "Infra",
    description: undefined,
    default_filter: undefined,
    order_by: undefined,
    display_labels: undefined,
    attributes: [],
    relationships: [
      {
        id: "41b42400-daf4-4d07-a270-bde920061c01",
        name: "connected_endpoint",
        peer: "InfraEndpoint",
        kind: "Attribute",
        label: "Connected Endpoint",
        description: undefined,
        identifier: "connected__endpoint",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: true,
        filters: [],
        order_weight: 1000,
      },
    ],
    branch: true,
    label: "Endpoint",
    used_by: ["InfraCircuitEndpoint", "InfraInterfaceL2", "InfraInterfaceL3"],
    kind: "InfraEndpoint",
  },
  {
    id: "76c153b2-d580-43ec-b4de-50ec67ee1881",
    name: "Group",
    namespace: "Core",
    description: undefined,
    default_filter: "name__value",
    order_by: ["name__value"],
    display_labels: ["label__value"],
    attributes: [
      {
        id: "001e93e4-b02a-4b3a-ba0c-626915395358",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
        label: "Name",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: true,
        branch: true,
        optional: false,
        order_weight: 1000,
      },
      {
        id: "93a01cde-b121-43ec-ad66-92aa868e6c0d",
        name: "label",
        kind: "Text",
        namespace: "Attribute",
        label: "Label",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
      {
        id: "58d1777f-13bc-4937-a3ca-7d889fd7def4",
        name: "description",
        kind: "Text",
        namespace: "Attribute",
        label: "Description",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 3000,
      },
    ],
    relationships: [
      {
        id: "7fdb61ff-95d4-40d0-bb6a-8e6a87bb77db",
        name: "members",
        peer: "CoreNode",
        kind: "Generic",
        label: "Members",
        description: undefined,
        identifier: "group_member",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [],
        order_weight: 4000,
      },
      {
        id: "f3b41911-e110-4cf7-b7a9-6708702d0764",
        name: "subscribers",
        peer: "CoreNode",
        kind: "Generic",
        label: "Subscribers",
        description: undefined,
        identifier: "group_subscriber",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [],
        order_weight: 5000,
      },
    ],
    branch: true,
    label: "Group",
    used_by: ["CoreStandardGroup"],
    kind: "CoreGroup",
  },
  deviceDetailsMocksGenerics[0],
  {
    id: "f069caa4-0f8b-425b-bc18-ef57d69e1ce2",
    name: "Node",
    namespace: "Core",
    description: undefined,
    default_filter: undefined,
    order_by: undefined,
    display_labels: undefined,
    attributes: [],
    relationships: [],
    branch: true,
    label: "Node",
    used_by: [],
    kind: "CoreNode",
  },
  {
    id: "757c1d52-ba8a-4686-9e2d-f09ab41336c6",
    name: "Owner",
    namespace: "Lineage",
    description: undefined,
    default_filter: undefined,
    order_by: undefined,
    display_labels: ["name__value"],
    attributes: [
      {
        id: "2f4d3921-3ea6-43af-bb5c-45b7019c32ba",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
        label: "Name",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: true,
        branch: true,
        optional: false,
        order_weight: 1000,
      },
      {
        id: "b2aa80d8-2a9f-4493-a7aa-e6f4689a21be",
        name: "description",
        kind: "Text",
        namespace: "Attribute",
        label: "Description",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
    ],
    relationships: [],
    branch: true,
    label: "Owner",
    used_by: ["CoreAccount", "CoreRepository"],
    kind: "LineageOwner",
  },
  {
    id: "1260ab98-5d35-4479-96dd-3d7ad261a19c",
    name: "Source",
    namespace: "Lineage",
    description: "Any Entities that stores or produces data.",
    default_filter: undefined,
    order_by: undefined,
    display_labels: ["name__value"],
    attributes: [
      {
        id: "3fa53678-7023-4413-8cb5-e9bae1ef7fe0",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
        label: "Name",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: true,
        branch: true,
        optional: false,
        order_weight: 1000,
      },
      {
        id: "739d1b9e-6605-498d-b2c3-cb5aaba39789",
        name: "description",
        kind: "Text",
        namespace: "Attribute",
        label: "Description",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
    ],
    relationships: [],
    branch: true,
    label: "Source",
    used_by: ["CoreAccount", "CoreRepository"],
    kind: "LineageSource",
  },
];