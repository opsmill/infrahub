import { permissionsAllow } from "./permissions";

export const deviceDetailsMocksId = "bd3110b9-5923-45e9-b643-776b8151c074";
export const deviceSiteMocksId = "06c3ab9e-535e-41af-bf4b-ec9134cc4353";
export const deviceSiteOwnerMocksId = "1790adb9-7030-259c-35c7-d8e28044d715";
export const deviceSiteSourceMocksId = "1790adb9-7030-259c-35c7-d8e28044d715";
export const deviceDetailsName = "atl1-edge1";
export const deviceDetailsMocksASNName = "AS64496 64496";
export const deviceDetailsMocksOwnerName = "Engineering Team";
export const deviceDetailsMocksTagName = "green";
export const interfaceLabelName = "Interfaces";
export const interfacesArrayCount = 14;
export const interfaceDescription = "Connected to atl1-edge1 Ethernet1";
export const interfacesArray = [
  {
    node: {
      id: "17f7e4af-075f-fd59-3c00-c51c3a7a3baf",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL3",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to jfk1-edge2 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4ae-dc67-47eb-3c0c-c51255b84026",
          display_label: "jfk1-edge1",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4aa-3e8c-4ee7-3c0a-c519ea0a1385",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL3",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to ord1-edge2 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4aa-10b1-f858-3c05-c51509f26b59",
          display_label: "ord1-edge1",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4ac-c6b5-7f37-3c04-c5129f5e3f5e",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL2",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to ord1-leaf2 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4ac-9024-261f-3c06-c51fabba52ed",
          display_label: "ord1-leaf1",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4ad-a6ea-d0bb-3c05-c514f9079347",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL2",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to ord1-leaf1 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4ad-755b-c028-3c0c-c5195bae7f5e",
          display_label: "ord1-leaf2",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4a7-0fa9-bdfe-3c08-c51fcb6a6259",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL2",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to atl1-leaf2 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4a6-ef49-0a54-3c0c-c51e55a4072c",
          display_label: "atl1-leaf1",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4a4-0d92-bbd4-3c0f-c51ea8414feb",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL3",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to atl1-edge2 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4a3-696f-f36a-3c0b-c51842797159",
          display_label: "atl1-edge1",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4a8-1f99-a656-3c0a-c51938622496",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL2",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to atl1-leaf1 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4a7-ccf0-5597-3c02-c513092964fa",
          display_label: "atl1-leaf2",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4ab-6095-fc92-3c02-c51fea74f3a8",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL3",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to ord1-edge1 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4ab-3b7a-a176-3c03-c517623bdda0",
          display_label: "ord1-edge2",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4a5-af62-2052-3c0e-c519f4c7ebba",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL3",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to atl1-edge1 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4a5-872e-76f8-3c01-c51df8b37fac",
          display_label: "atl1-edge2",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
  {
    node: {
      id: "17f7e4b0-02c1-f8fc-3c09-c510805683ff",
      display_label: "Ethernet1",
      __typename: "InfraInterfaceL3",
      name: {
        value: "Ethernet1",
        __typename: "TextAttribute",
      },
      description: {
        value: "Connected to jfk1-edge1 Ethernet1",
        __typename: "TextAttribute",
      },
      speed: {
        value: 10000,
        __typename: "NumberAttribute",
      },
      mtu: {
        value: 1500,
        __typename: "NumberAttribute",
      },
      enabled: {
        value: true,
        __typename: "CheckboxAttribute",
      },
      status: {
        value: "active",
        color: "#7fbf7f",
        description: "Fully operational and currently in service",
        label: "Active",
        __typename: "Dropdown",
      },
      role: {
        value: "peer",
        color: "#faa446",
        description: "Equal-status connections for direct interchange",
        label: "Peer",
        __typename: "Dropdown",
      },
      device: {
        node: {
          id: "17f7e4af-df53-e2d5-3c0a-c51729e215a3",
          display_label: "jfk1-edge2",
          __typename: "InfraDevice",
        },
        __typename: "NestedEdgedInfraDevice",
      },
      tags: {
        edges: [],
        __typename: "NestedPaginatedBuiltinTag",
      },
    },
    __typename: "EdgedInfraInterface",
  },
];

export const deviceDetailsMocksGenerics = [
  {
    id: "61b71893-8dac-4dfa-91fd-fe7fae7d51aa",
    name: "Interface",
    namespace: "Infra",
    description: null,
    default_filter: null,
    order_by: null,
    display_labels: ["name__value"],
    attributes: [
      {
        id: "ca4b4149-2498-4a83-a8be-d63e3bbc3e1f",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
        label: "Name",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 1000,
      },
      {
        id: "79a6abf5-9e89-41d9-bd38-b4bb22d8c883",
        name: "description",
        kind: "Text",
        namespace: "Attribute",
        label: "Description",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
      {
        id: "7ae3500d-b350-4e01-8172-6d8ea514f62e",
        name: "speed",
        kind: "Number",
        namespace: "Attribute",
        label: "Speed",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 3000,
      },
      {
        id: "b6b74631-4f15-4811-801c-b813ce1c9ebe",
        name: "mtu",
        kind: "Number",
        namespace: "Attribute",
        label: "MTU",
        description: null,
        default_value: 1500,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 4000,
      },
      {
        id: "cc0dd07c-4721-414b-8df8-d9a9ccab462f",
        name: "enabled",
        kind: "Boolean",
        namespace: "Attribute",
        label: "Enabled",
        description: null,
        default_value: true,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 5000,
      },
    ],
    relationships: [
      {
        id: "61fb337b-0186-4fe1-ba45-32ccf30cb95e",
        name: "status",
        peer: "BuiltinStatus",
        kind: "Attribute",
        label: "Status",
        description: null,
        identifier: "builtinstatus__infrainterface",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [],
        order_weight: 6000,
      },
      {
        id: "f9301d6d-bf75-4079-b613-39fb3775646e",
        name: "role",
        peer: "BuiltinRole",
        kind: "Attribute",
        label: "Role",
        description: null,
        identifier: "builtinrole__infrainterface",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [],
        order_weight: 7000,
      },
      {
        id: "c96e9046-1bb4-4245-8e67-66c57fc9e71e",
        name: "device",
        peer: "InfraDevice",
        kind: "Parent",
        label: "Device",
        description: null,
        identifier: "device__interface",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [],
        order_weight: 8000,
      },
      {
        id: "61856a1e-afaf-41b0-b958-d2f0726e36f7",
        name: "tags",
        peer: "BuiltinTag",
        kind: "Attribute",
        label: "Tags",
        description: null,
        identifier: "builtintag__infrainterface",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [],
        order_weight: 9000,
      },
    ],
    branch: true,
    label: "Interface",
    used_by: ["InfraInterfaceL2", "InfraInterfaceL3"],
    kind: "InfraInterface",
  },
];

export const deviceDetailsMocksSchema = [
  {
    id: "caa97e78-fbe2-4898-8d58-a647b28c7a86",
    name: "Device",
    namespace: "Infra",
    description: null,
    default_filter: "name__value",
    order_by: ["name__value"],
    display_labels: ["name__value"],
    generate_profile: true,
    attributes: [
      {
        id: "e9268a46-073b-4f15-9f01-b3b0cc909264",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
        label: "Name",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: true,
        branch: true,
        optional: false,
        order_weight: 1000,
      },
      {
        id: "63b462ff-4c5b-44dc-86e2-288e508c81c9",
        name: "description",
        kind: "Text",
        namespace: "Attribute",
        label: "Description",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
      {
        id: "9e4b1532-8b85-4053-8420-0f03af848c6b",
        name: "type",
        kind: "Text",
        namespace: "Attribute",
        label: "Type",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 3000,
      },
    ],
    relationships: [
      {
        id: "a82f016c-37b7-41b2-b2e4-e478cb650114",
        name: "site",
        peer: "BuiltinLocation",
        kind: "Attribute",
        label: "Site",
        description: null,
        identifier: "builtinlocation__infradevice",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          { name: "type__value", kind: "Text", enum: null, object_kind: null, description: null },
        ],
        order_weight: 4000,
      },
      {
        id: "143c3cab-ff0f-4cc0-a72a-39d542e0ba4b",
        name: "status",
        peer: "BuiltinStatus",
        kind: "Attribute",
        label: "Status",
        description: null,
        identifier: "builtinstatus__infradevice",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 5000,
      },
      {
        id: "86b71b3e-2b6b-4a5c-a0f0-d1a992854c23",
        name: "role",
        peer: "BuiltinRole",
        kind: "Attribute",
        label: "Role",
        description: null,
        identifier: "builtinrole__infradevice",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 6000,
      },
      {
        id: "89bbf70d-1b86-4ecd-b8ad-fa1640088973",
        name: "interfaces",
        peer: "InfraInterface",
        kind: "Component",
        label: "Interfaces",
        description: null,
        identifier: "device__interface",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "speed__value",
            kind: "Number",
            enum: null,
            object_kind: null,
            description: null,
          },
          { name: "mtu__value", kind: "Number", enum: null, object_kind: null, description: null },
          {
            name: "enabled__value",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 7000,
      },
      {
        id: "c335b447-a740-426d-bb59-fa817ca8e623",
        name: "asn",
        peer: "InfraAutonomousSystem",
        kind: "Attribute",
        label: "Asn",
        description: null,
        identifier: "infraautonomoussystem__infradevice",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "asn__value", kind: "Number", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 8000,
      },
      {
        id: "8e75f518-4c4c-4280-9b6e-fcc1b931b958",
        name: "tags",
        peer: "BuiltinTag",
        kind: "Attribute",
        label: "Tags",
        description: null,
        identifier: "builtintag__infradevice",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 9000,
      },
      {
        id: "b8027931-9a4f-44ab-8a50-652b1c8a2569",
        name: "primary_address",
        peer: "InfraIPAddress",
        kind: "Attribute",
        label: "Primary IP Address",
        description: null,
        identifier: "infradevice__infraipaddress",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 10000,
      },
      {
        id: "124f37be-8218-4838-b45e-6e6109eead33",
        name: "platform",
        peer: "InfraPlatform",
        kind: "Attribute",
        label: "Platform",
        description: null,
        identifier: "infradevice__infraplatform",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "nornir_platform__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "napalm_driver__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "netmiko_device_type__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "ansible_network_os__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 11000,
      },
    ],
    label: "Device",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [
      { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
      { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
      {
        name: "description__value",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      { name: "type__value", kind: "Text", enum: null, object_kind: null, description: null },
      {
        name: "site__id",
        kind: "Object",
        enum: null,
        object_kind: "BuiltinLocation",
        description: null,
      },
      {
        name: "status__id",
        kind: "Object",
        enum: null,
        object_kind: "BuiltinStatus",
        description: null,
      },
      {
        name: "role__id",
        kind: "Object",
        enum: null,
        object_kind: "BuiltinRole",
        description: null,
      },
      {
        name: "asn__id",
        kind: "Object",
        enum: null,
        object_kind: "InfraAutonomousSystem",
        description: null,
      },
      {
        name: "tags__id",
        kind: "Object",
        enum: null,
        object_kind: "BuiltinTag",
        description: null,
      },
      {
        name: "primary_address__id",
        kind: "Object",
        enum: null,
        object_kind: "InfraIPAddress",
        description: null,
      },
      {
        name: "platform__id",
        kind: "Object",
        enum: null,
        object_kind: "InfraPlatform",
        description: null,
      },
    ],
    kind: "InfraDevice",
  },
];

export const deviceDetailsMocksQuery = `
query InfraDevice {
  InfraDevice (ids: ["${deviceDetailsMocksId}"]) {
    edges {
      node {
        id
        display_label
        profiles {
          edges {
            node {
              display_label
              id
              profile_priority {
                value
              }
            }
          }
        }
        name {
            id
            value
            updated_at
            is_default
            is_from_profile
            is_protected
            is_visible
            source {
              id
              display_label
              __typename
            }
            owner {
              id
              display_label
              __typename
            }
        }
        description {
            id
            value
            updated_at
            is_default
            is_from_profile
            is_protected
            is_visible
            source {
              id
              display_label
              __typename
            }
            owner {
              id
              display_label
              __typename
            }
        }
        type {
            id
            value
            updated_at
            is_default
            is_from_profile
            is_protected
            is_visible
            source {
              id
              display_label
              __typename
            }
            owner {
              id
              display_label
              __typename
            }
        }
          site {
              node {
                id
                display_label
                __typename
              }
              properties {
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
                __typename
              }
          }
          status {
              node {
                id
                display_label
                __typename
              }
              properties {
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
                __typename
              }
          }
          role {
              node {
                id
                display_label
                __typename
              }
              properties {
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
                __typename
              }
          }
          asn {
              node {
                id
                display_label
                __typename
              }
              properties {
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
                __typename
              }
          }
          tags(limit: 100) {
              edges {
              node {
                id
                display_label
                __typename
              }
              properties {
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
                __typename
              }
            }
          }
          primary_address {
              node {
                id
                display_label
                __typename
              }
              properties {
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
                __typename
              }
          }
          platform {
              node {
                id
                display_label
                __typename
              }
              properties {
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
                __typename
              }
          }
        interfaces(limit: 100) {
          count
        }
      }
    }
    permissions {
      edges {
        node {
          kind
          view
          create
          update
          delete
        }
      }
    }
  }
  InfrahubTask(related_node__ids: ["${deviceDetailsMocksId}"]) {
    count
  }
}
`;

export const deviceDetailsMocksData = {
  InfraDevice: {
    edges: [
      {
        node: {
          id: deviceDetailsMocksId,
          display_label: deviceDetailsName,
          name: {
            value: deviceDetailsName,
            updated_at: "2023-07-10T15:01:29.806543+00:00",
            is_protected: true,
            is_visible: true,
            source: {
              id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
              display_label: "Pop-Builder",
              __typename: "CoreAccount",
            },
            owner: null,
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            updated_at: "2023-07-10T15:01:29.806543+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          type: {
            value: "7280R3",
            updated_at: "2023-07-10T15:01:29.806543+00:00",
            is_protected: false,
            is_visible: true,
            source: {
              id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
              display_label: "Pop-Builder",
              __typename: "CoreAccount",
            },
            owner: null,
            __typename: "TextAttribute",
          },
          site: {
            node: {
              id: deviceSiteMocksId,
              display_label: "atl1",
              __typename: "BuiltinLocation",
            },
            properties: {
              updated_at: "2023-07-10T15:01:29.806543+00:00",
              is_protected: true,
              is_visible: true,
              source: {
                id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
                display_label: "Pop-Builder",
                __typename: "CoreAccount",
              },
              owner: null,
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedBuiltinLocation",
          },
          status: {
            node: {
              id: "6c96efcf-acec-449c-9a8f-b3b069c94e76",
              display_label: "Active",
              __typename: "BuiltinStatus",
            },
            properties: {
              updated_at: "2023-07-10T15:01:29.806543+00:00",
              is_protected: null,
              is_visible: true,
              source: null,
              owner: {
                id: "9622f4c6-2a61-4e71-8d78-36dcab0d219c",
                display_label: "Operation Team",
                __typename: "CoreAccount",
              },
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedBuiltinStatus",
          },
          role: {
            node: {
              id: "4ad3a31b-6446-4149-8498-da531776fc5f",
              display_label: "Edge",
              __typename: "BuiltinRole",
            },
            properties: {
              updated_at: "2023-07-10T15:01:29.806543+00:00",
              is_protected: true,
              is_visible: true,
              source: {
                id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
                display_label: "Pop-Builder",
                __typename: "CoreAccount",
              },
              owner: {
                id: "0552d2d5-e38f-414b-8891-a718c1fa0657",
                display_label: "Engineering Team",
                __typename: "CoreAccount",
              },
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedBuiltinRole",
          },
          asn: {
            node: {
              id: "74bb08a5-30fa-4c96-99d9-a9a8f91716e7",
              display_label: "AS64496 64496",
              __typename: "InfraAutonomousSystem",
            },
            properties: {
              updated_at: "2023-07-10T15:01:29.806543+00:00",
              is_protected: true,
              is_visible: true,
              source: {
                id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
                display_label: "Pop-Builder",
                __typename: "CoreAccount",
              },
              owner: {
                id: "0552d2d5-e38f-414b-8891-a718c1fa0657",
                display_label: "Engineering Team",
                __typename: "CoreAccount",
              },
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedInfraAutonomousSystem",
          },
          tags: {
            edges: [
              {
                node: {
                  id: "134f3f6d-1d53-4b00-8a3d-3e4dce3f2996",
                  display_label: "green",
                  __typename: "BuiltinTag",
                },
                properties: {
                  updated_at: "2023-07-10T15:01:29.806543+00:00",
                  is_protected: null,
                  is_visible: true,
                  source: null,
                  owner: null,
                  __typename: "RelationshipProperty",
                },
                __typename: "NestedEdgedBuiltinTag",
              },
              {
                node: {
                  id: "25efcc5c-407f-404e-9a77-0161bb9558e8",
                  display_label: "red",
                  __typename: "BuiltinTag",
                },
                properties: {
                  updated_at: "2023-07-10T15:01:29.806543+00:00",
                  is_protected: null,
                  is_visible: true,
                  source: null,
                  owner: null,
                  __typename: "RelationshipProperty",
                },
                __typename: "NestedEdgedBuiltinTag",
              },
            ],
            __typename: "NestedPaginatedBuiltinTag",
          },
          primary_address: {
            node: {
              id: "034c8cf0-337b-4e0f-9915-2b50d69224ed",
              display_label: "172.20.20.19/24",
              __typename: "InfraIPAddress",
            },
            properties: {
              updated_at: "2023-07-10T15:01:30.985897+00:00",
              is_protected: null,
              is_visible: true,
              source: null,
              owner: null,
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedInfraIPAddress",
          },
          platform: {
            node: {
              id: "a04c3ca4-865a-458c-81c4-51e50205da44",
              display_label: "Arista EOS",
              __typename: "InfraPlatform",
            },
            properties: {
              updated_at: "2023-07-10T15:01:29.806543+00:00",
              is_protected: true,
              is_visible: true,
              source: {
                id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
                display_label: "Pop-Builder",
                __typename: "CoreAccount",
              },
              owner: null,
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedInfraPlatform",
          },
          interfaces: { count: 14, __typename: "NestedPaginatedInfraInterface" },
          __typename: "InfraDevice",
        },
        __typename: "EdgedInfraDevice",
      },
    ],
    permissions: permissionsAllow,
    __typename: "PaginatedInfraDevice",
  },
};

export const deviceDetailsInterfacesMocksQuery = `
query GetObjectRelationships_InfraDevice($offset: Int, $limit: Int) {
  InfraDevice(ids: ["${deviceDetailsMocksId}"]) {
    count
    edges {
      node {
        interfaces(offset: $offset, limit: $limit) {
          count
          edges {
            node {
              id
              display_label
              __typename
              ... on InfraInterface {
                name {
                  id
                  value
                }
                description {
                  id
                  value
                }
                speed {
                  id
                  value
                }
                mtu {
                  id
                  value
                }
                enabled {
                  id
                  value
                }
                status {
                  node {
                    id
                    display_label
                  }
                }
                role {
                  node {
                    id
                    display_label
                  }
                }
                device {
                  node {
                    id
                    display_label
                  }
                }
                tags {
                  edges {
                    node {
                      id
                      display_label
                    }
                  }
                }
              }
            }
            properties {
              updated_at
              is_protected
              is_visible
              source {
                id
                display_label
                __typename
              }
              owner {
                id
                display_label
                __typename
              }
            }
            properties {
              updated_at
              is_protected
              is_visible
              source {
                id
                display_label
                __typename
              }
              owner {
                id
                display_label
                __typename
              }
            }
          }
        }
      }
    }
  }
}
`;

export const deviceDetailsInterfacesMocksData = {
  InfraDevice: {
    count: 1,
    edges: [
      {
        node: {
          interfaces: {
            count: interfacesArrayCount,
            edges: interfacesArray,
            __typename: "NestedPaginatedInterface",
          },
          __typename: "InfraDevice",
        },
        __typename: "EdgedDevice",
      },
    ],
    __typename: "PaginatedDevice",
  },
};

export const newDataForMetaEdit = {
  owner: deviceSiteOwnerMocksId,
  source: deviceSiteSourceMocksId,
  is_visible: true,
  is_protected: true,
};

export const updatedObjectForMetaEdit = {
  id: deviceDetailsMocksId,
  site: {
    id: deviceSiteMocksId,
    _relation__owner: deviceSiteOwnerMocksId,
    _relation__source: deviceSiteSourceMocksId,
    _relation__is_visible: true,
    _relation__is_protected: true,
  },
};

export const mutationStringForMetaEdit = `
mutation InfraDeviceUpdate {
  InfraDeviceUpdate (data: {
    id: "${deviceDetailsMocksId}",
    site: {
        id: "${deviceSiteMocksId}",
        _relation__owner: "${deviceSiteOwnerMocksId}",
        _relation__source: "${deviceSiteSourceMocksId}",
        _relation__is_visible: true,
        _relation__is_protected: true
    }
}) {
      ok
  }
}
`;
