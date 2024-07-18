export const tokenSchema = {
  id: "17e2a71e-2ac0-bf55-3105-c516dbe1b504",
  state: "present",
  name: "AccountToken",
  namespace: "Core",
  description: "A User Token used for API access.",
  label: "Account Token",
  branch: "aware",
  default_filter: null,
  human_friendly_id: null,
  display_labels: ["name__value"],
  include_in_menu: true,
  menu_placement: null,
  icon: null,
  order_by: null,
  uniqueness_constraints: null,
  documentation: null,
  attributes: [
    {
      id: "17e2a71e-4faa-2e82-3109-c51dff39f069",
      state: "present",
      name: "name",
      kind: "Text",
      enum: null,
      choices: null,
      regex: null,
      max_length: null,
      min_length: null,
      label: "Name",
      description: "Name of the user token.",
      read_only: false,
      unique: false,
      optional: false,
      branch: "aware",
      order_weight: 1000,
      default_value: null,
      inherited: false,
      allow_override: "any",
    },
    {
      id: "17e2a71e-7c88-723c-3102-c51bff58788b",
      state: "present",
      name: "expiration",
      kind: "DateTime",
      enum: null,
      choices: null,
      regex: null,
      max_length: null,
      min_length: null,
      label: "Expiration",
      description: "Expiration date.",
      read_only: false,
      unique: false,
      optional: true,
      branch: "aware",
      order_weight: 4000,
      default_value: null,
      inherited: false,
      allow_override: "any",
    },
  ],
  relationships: [
    {
      id: "17e2a71e-7cc4-5cf0-3102-c51c52a91d5d",
      state: "present",
      name: "profiles",
      peer: "CoreProfile",
      kind: "Profile",
      label: "Profiles",
      description: null,
      identifier: "node__profile",
      cardinality: "many",
      min_count: 0,
      max_count: 0,
      order_weight: 5000,
      optional: true,
      branch: "aware",
      inherited: false,
      direction: "bidirectional",
      hierarchical: null,
      filters: [
        {
          id: null,
          state: "present",
          name: "ids",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_name__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_name__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_name__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_name__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_name__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_name__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_priority__value",
          kind: "Number",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_priority__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_priority__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_priority__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_priority__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "profile_priority__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
      ],
      on_delete: "no-action",
      allow_override: "any",
      read_only: false,
    },
    {
      id: "17e2a71e-9473-d5cd-3100-c51bb9b15af9",
      state: "present",
      name: "member_of_groups",
      peer: "CoreGroup",
      kind: "Group",
      label: "Member Of Groups",
      description: null,
      identifier: "group_member",
      cardinality: "many",
      min_count: 0,
      max_count: 0,
      order_weight: 6000,
      optional: true,
      branch: "aware",
      inherited: false,
      direction: "bidirectional",
      hierarchical: null,
      filters: [
        {
          id: null,
          state: "present",
          name: "ids",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
      ],
      on_delete: "no-action",
      allow_override: "any",
      read_only: false,
    },
    {
      id: "17e2a71e-94c6-5b74-3106-c51c9f5a46bc",
      state: "present",
      name: "subscriber_of_groups",
      peer: "CoreGroup",
      kind: "Group",
      label: "Subscriber Of Groups",
      description: null,
      identifier: "group_subscriber",
      cardinality: "many",
      min_count: 0,
      max_count: 0,
      order_weight: 7000,
      optional: true,
      branch: "aware",
      inherited: false,
      direction: "bidirectional",
      hierarchical: null,
      filters: [
        {
          id: null,
          state: "present",
          name: "ids",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "name__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "label__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          id: null,
          state: "present",
          name: "description__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
      ],
      on_delete: "no-action",
      allow_override: "any",
      read_only: false,
    },
  ],
  inherit_from: [],
  generate_profile: false,
  hierarchy: null,
  parent: null,
  children: null,
  kind: "CoreAccountToken",
  hash: "2cfd9af9d6fcac49527fca295de251b8",
};

export const apiSchema = `{
  "version": "string",
  "schemas": [
    {
      "version": "string",
      "nodes": [
        {
          "state": "present",
          "name": "AccountToken",
          "namespace": "Test",
          "description": "A User Token used for API access.",
          "label": "Account Token",
          "branch": "aware",
          "display_labels": [
            "name__value"
          ],
          "include_in_menu": true,
          "attributes": [
            {
              "name": "name",
              "kind": "Text",
              "description": "Name of the user token."
            },
            {
              "name": "api_key",
              "kind": "Text",
              "description": "API key associated with the user token."
            },
            {
              "name": "status",
              "kind": "Dropdown",
              "choices": [
                {
                  "name": "active",
                  "label": "Active",
                  "description": "Token is active and usable.",
                  "color": "#009933"
                },
                {
                  "name": "inactive",
                  "label": "Inactive",
                  "description": "Token is inactive and not usable.",
                  "color": "#cc0000"
                }
              ],
              "description": "Status of the user token."
            },
            {
              "name": "timestamp",
              "kind": "DateTime",
              "description": "Timestamp of when the token was created or last used."
            }
          ],
          "relationships": []
        }
      ]
    }
  ]
}`;
