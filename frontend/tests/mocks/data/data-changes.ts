export const objectThreadSchema = {
  id: "17a53fb0-8191-7969-2d03-c51b08c9b696",
  name: "ObjectThread",
  namespace: "Core",
  description: "A thread related to an object on a proposed change",
  default_filter: null,
  branch: "agnostic",
  order_by: null,
  display_labels: null,
  attributes: [
    {
      id: "17a53fb0-87c9-e1fd-2d03-c5155a15ff42",
      name: "object_path",
      kind: "Text",
      label: "Object Path",
      description: null,
      default_value: null,
      enum: null,
      regex: null,
      max_length: null,
      min_length: null,
      read_only: false,
      inherited: false,
      unique: false,
      branch: "agnostic",
      optional: false,
      order_weight: 1000,
      choices: null,
    },
    {
      id: "17a53fb0-88a1-592b-2d05-c5153ecc3abe",
      name: "label",
      kind: "Text",
      label: "Label",
      description: null,
      default_value: null,
      enum: null,
      regex: null,
      max_length: null,
      min_length: null,
      read_only: false,
      inherited: true,
      unique: false,
      branch: "agnostic",
      optional: true,
      order_weight: 2000,
      choices: null,
    },
    {
      id: "17a53fb0-89bb-c2db-2d00-c5177efd3b50",
      name: "resolved",
      kind: "Boolean",
      label: "Resolved",
      description: null,
      default_value: false,
      enum: null,
      regex: null,
      max_length: null,
      min_length: null,
      read_only: false,
      inherited: true,
      unique: false,
      branch: "agnostic",
      optional: true,
      order_weight: 3000,
      choices: null,
    },
    {
      id: "17a53fb0-8af7-2523-2d0c-c51f25e2d550",
      name: "created_at",
      kind: "DateTime",
      label: "Created At",
      description: null,
      default_value: null,
      enum: null,
      regex: null,
      max_length: null,
      min_length: null,
      read_only: false,
      inherited: true,
      unique: false,
      branch: "agnostic",
      optional: true,
      order_weight: 4000,
      choices: null,
    },
  ],
  relationships: [
    {
      id: "17a53fb0-8bd3-600b-2d0e-c5154b38eac6",
      name: "change",
      peer: "CoreProposedChange",
      kind: "Parent",
      direction: "bidirectional",
      label: "Change",
      description: null,
      identifier: "proposedchange__thread",
      inherited: true,
      cardinality: "one",
      branch: "agnostic",
      optional: false,
      filters: [
        { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "name__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "source_branch__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "source_branch__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "source_branch__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "source_branch__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "source_branch__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "source_branch__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "destination_branch__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "destination_branch__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "destination_branch__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "destination_branch__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "destination_branch__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "destination_branch__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "state__value",
          kind: "Text",
          enum: ["open", "merged", "closed", "canceled"],
          object_kind: null,
          description: null,
        },
        { name: "state__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "state__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "state__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "state__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "state__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
      ],
      order_weight: 5000,
    },
    {
      id: "17a53fb0-8c82-44ab-2d06-c51be086e749",
      name: "comments",
      peer: "CoreThreadComment",
      kind: "Component",
      direction: "bidirectional",
      label: "Comments",
      description: null,
      identifier: "thread__threadcomment",
      inherited: true,
      cardinality: "many",
      branch: "agnostic",
      optional: true,
      filters: [{ name: "ids", kind: "Text", enum: null, object_kind: null, description: null }],
      order_weight: 6000,
    },
    {
      id: "17a53fb0-8cec-f6a2-2d05-c518429232f0",
      name: "created_by",
      peer: "CoreAccount",
      kind: "Generic",
      direction: "bidirectional",
      label: "Created By",
      description: null,
      identifier: "coreaccount__corethread",
      inherited: true,
      cardinality: "one",
      branch: "agnostic",
      optional: true,
      filters: [
        { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "name__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "label__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "label__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "type__value",
          kind: "Text",
          enum: ["User", "Script", "Bot", "Git"],
          object_kind: null,
          description: null,
        },
        { name: "type__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "type__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "type__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "type__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "type__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "role__value",
          kind: "Text",
          enum: ["admin", "read-only", "read-write"],
          object_kind: null,
          description: null,
        },
        { name: "role__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "role__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "role__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "role__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "role__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
      ],
      order_weight: 7000,
    },
    {
      id: "17a53fb0-8d5c-751d-2d04-c517647f7a8e",
      name: "member_of_groups",
      peer: "CoreGroup",
      kind: "Group",
      direction: "bidirectional",
      label: "Member Of Groups",
      description: null,
      identifier: "group_member",
      inherited: false,
      cardinality: "many",
      branch: "aware",
      optional: true,
      filters: [
        { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "name__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "label__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "label__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
      ],
      order_weight: 8000,
    },
    {
      id: "17a53fb0-8dc4-f2a0-2d00-c517e9f46163",
      name: "subscriber_of_groups",
      peer: "CoreGroup",
      kind: "Group",
      direction: "bidirectional",
      label: "Subscriber Of Groups",
      description: null,
      identifier: "group_subscriber",
      inherited: false,
      cardinality: "many",
      branch: "aware",
      optional: true,
      filters: [
        { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "name__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "name__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "name__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
        { name: "label__values", kind: "Text", enum: null, object_kind: null, description: null },
        {
          name: "label__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "label__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__value",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__values",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__is_visible",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__is_protected",
          kind: "Boolean",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__source__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
        {
          name: "description__owner__id",
          kind: "Text",
          enum: null,
          object_kind: null,
          description: null,
        },
      ],
      order_weight: 9000,
    },
  ],
  filters: [
    { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
    {
      name: "object_path__value",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "object_path__values",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "object_path__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "object_path__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "object_path__source__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "object_path__owner__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
    { name: "label__values", kind: "Text", enum: null, object_kind: null, description: null },
    {
      name: "label__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "label__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    { name: "label__source__id", kind: "Text", enum: null, object_kind: null, description: null },
    { name: "label__owner__id", kind: "Text", enum: null, object_kind: null, description: null },
    {
      name: "resolved__value",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    { name: "resolved__values", kind: "Text", enum: null, object_kind: null, description: null },
    {
      name: "resolved__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "resolved__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "resolved__source__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "resolved__owner__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    { name: "any__value", kind: "Text", enum: null, object_kind: null, description: null },
    {
      name: "any__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "any__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    { name: "any__source__id", kind: "Text", enum: null, object_kind: null, description: null },
    { name: "any__owner__id", kind: "Text", enum: null, object_kind: null, description: null },
    {
      name: "change__ids",
      kind: "Text",
      enum: null,
      object_kind: "CoreProposedChange",
      description: null,
    },
    {
      name: "change__name__value",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__name__values",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__name__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__name__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__name__source__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__name__owner__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__source_branch__value",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__source_branch__values",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__source_branch__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__source_branch__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__source_branch__source__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__source_branch__owner__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__destination_branch__value",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__destination_branch__values",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__destination_branch__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__destination_branch__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__destination_branch__source__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__destination_branch__owner__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__state__value",
      kind: "Text",
      enum: ["open", "merged", "closed", "canceled"],
      object_kind: null,
      description: null,
    },
    {
      name: "change__state__values",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__state__is_visible",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__state__is_protected",
      kind: "Boolean",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__state__source__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
    {
      name: "change__state__owner__id",
      kind: "Text",
      enum: null,
      object_kind: null,
      description: null,
    },
  ],
  include_in_menu: false,
  menu_placement: null,
  icon: null,
  label: "Thread - Object",
  inherit_from: ["CoreThread"],
  groups: [],
  kind: "CoreObjectThread",
  hash: "5a92f8a14bf7c4dd08da69e168d1c4b7",
};

export const DataDiffProposedChangesState = {
  id: "17a54304-4b2a-264a-2d02-c51eae9cdde6",
  display_label: "pc-data-changes",
  __typename: "CoreProposedChange",
  _updated_at: "2023-12-29T09:21:59.750848+00:00",
  name: {
    value: "pc-data-changes",
    __typename: "TextAttribute",
  },
  source_branch: {
    value: "branch-data-changes",
    __typename: "TextAttribute",
  },
  destination_branch: {
    value: "main",
    __typename: "TextAttribute",
  },
  state: {
    value: "open",
    __typename: "TextAttribute",
  },
  approved_by: {
    edges: [],
    __typename: "NestedPaginatedCoreAccount",
  },
  reviewers: {
    edges: [],
    __typename: "NestedPaginatedCoreAccount",
  },
  created_by: {
    node: {
      id: "17a53fb1-512b-ae9e-2d0d-c51fade6639c",
      display_label: "Admin",
      __typename: "CoreAccount",
    },
    __typename: "NestedEdgedCoreAccount",
  },
};

export const getAllCoreObjectThreadMockQuery = `query getThreadsAndChecksForCoreObjectThread {
  CoreObjectThread(
    change__ids: "1cec1fe9-fcc4-4f5b-af30-9d661de65bd8"
  ) {
    count
    edges {
      node {
        __typename
        id
        object_path {
          value
        }
        comments {
          count
        }
      }
    }
  }
}`;

export const getAllCoreObjectThreadMockData = {
  data: {
    CoreObjectThread: {
      count: 1,
      edges: [
        {
          node: {
            __typename: "CoreObjectThread",
            id: "17a54a5c-55d1-0620-2d0a-c51d250954a9",
            object_path: {
              value: "data/17a53fbd-e27b-784b-393c-c5127a1b1be3",
              __typename: "TextAttribute",
            },
            comments: {
              count: 1,
              __typename: "NestedPaginatedCoreThreadComment",
            },
          },
          __typename: "EdgedCoreObjectThread",
        },
      ],
      __typename: "PaginatedCoreObjectThread",
    },
  },
};

export const getCoreObjectThreadMockQuery = `query getProposedChangesThreadsForCoreObjectThread {
  CoreObjectThread(
    change__ids: "1cec1fe9-fcc4-4f5b-af30-9d661de65bd8"
    object_path__value: "data/17a53fbd-e27b-784b-393c-c5127a1b1be3"
  ) {
    count
    edges {
      node {
        __typename
        id
        comments {
          count
        }
      }
    }
  }
}`;

export const getCoreObjectThreadMockData = {
  data: {
    CoreObjectThread: {
      count: 1,
      edges: [
        {
          node: {
            __typename: "CoreObjectThread",
            id: "17a54a5c-55d1-0620-2d0a-c51d250954a9",
            object_path: {
              value: "data/17a53fbd-e27b-784b-393c-c5127a1b1be3",
              __typename: "TextAttribute",
            },
            comments: {
              count: 1,
              __typename: "NestedPaginatedCoreThreadComment",
            },
          },
          __typename: "EdgedCoreObjectThread",
        },
      ],
      __typename: "PaginatedCoreObjectThread",
    },
  },
};

export const getCoreObjectWithoutThreadMockData = {
  data: {
    CoreObjectThread: {
      count: 0,
      edges: [],
      __typename: "PaginatedCoreObjectThread",
    },
  },
};

export const getProposedChangesCommentsMockQuery = `query getProposedChangesObjectThreadCommentsForCoreObjectThread{
  CoreObjectThread(
    change__ids: "1cec1fe9-fcc4-4f5b-af30-9d661de65bd8"
    object_path__value: "data/17a53fbd-e27b-784b-393c-c5127a1b1be3"
  ) {
    count
    edges {
      node {
        __typename
        id
        display_label
        resolved {
          value
        }
        created_by {
          node {
            display_label
          }
        }
        comments {
          count
          edges {
            node {
              id
              display_label
              created_by {
                node {
                  display_label
                }
              }
              created_at {
                value
              }
              text {
                value
              }
            }
          }
        }
      }
    }
  }
}`;

export const createThreadMockData = {
  data: {
    CoreObjectThreadCreate: {
      object: {
        id: "17a55dee-acc3-3df9-2d04-c51c5bd2161d",
        display_label: "CoreObjectThread(ID: 17a55dee-acc3-3df9-2d04-c51c5bd2161d)",
        __typename: "CoreObjectThread",
      },
      ok: true,
      __typename: "CoreObjectThreadCreate",
    },
  },
};

export const getProposedChangesCommentsMockData = {
  data: {
    CoreObjectThread: {
      count: 1,
      edges: [
        {
          node: {
            __typename: "CoreObjectThread",
            id: "17a55fb5-7d2f-f712-2d0e-c5154fe1bf17",
            display_label: "CoreObjectThread(ID: 17a55fb5-7d2f-f712-2d0e-c5154fe1bf17)",
            resolved: {
              value: false,
              __typename: "CheckboxAttribute",
            },
            created_by: {
              node: null,
              __typename: "NestedEdgedCoreAccount",
            },
            comments: {
              count: 1,
              edges: [
                {
                  node: {
                    id: "17a55fb5-82a1-197c-2d0e-c512237d7fa5",
                    display_label: "new comment",
                    created_by: {
                      node: {
                        display_label: "Admin",
                        __typename: "CoreAccount",
                      },
                      __typename: "NestedEdgedCoreAccount",
                    },
                    created_at: {
                      value: "2023-12-29T19:07:47+01:00",
                      __typename: "TextAttribute",
                    },
                    text: {
                      value: "new comment",
                      __typename: "TextAttribute",
                    },
                    __typename: "CoreThreadComment",
                  },
                  __typename: "NestedEdgedCoreThreadComment",
                },
              ],
              __typename: "NestedPaginatedCoreThreadComment",
            },
          },
          __typename: "EdgedCoreObjectThread",
        },
      ],
      __typename: "PaginatedCoreObjectThread",
    },
  },
};

export const createThreadCommentMockQuery = `mutation CoreThreadCommentCreate {
  CoreThreadCommentCreate(
    data: {text: {value: "new reply"}, thread: {id: "17a55fb5-7d2f-f712-2d0e-c5154fe1bf17"}, created_by: {id: "d07bb58e-8394-4053-a198-9cef84e7d6c0"}, created_at: {value: "2023-12-24T12:24:36+01:00"}}
  ) {
    object {
      id
      display_label
      __typename
    }
    ok
    __typename
  }
}`;
