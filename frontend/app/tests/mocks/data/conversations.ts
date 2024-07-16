export const proposedChangesId = "1cec1fe9-fcc4-4f5b-af30-9d661de65bd8";

export const conversationMocksSchema = [
  {
    id: "988f13b9-88d1-46ac-9aee-771ab6660add",
    name: "ChangeThread",
    namespace: "Core",
    description: "A thread on proposed change",
    default_filter: null,
    order_by: null,
    display_labels: null,
    attributes: [
      {
        id: "9cee690c-dea0-403f-88f0-f3b6b7a86887",
        name: "resolved",
        kind: "Boolean",
        namespace: "Attribute",
        label: "Resolved",
        description: null,
        default_value: false,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: true,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 1000,
      },
      {
        id: "801024c5-e987-4b39-8425-d9231ed862a3",
        name: "created_at",
        kind: "DateTime",
        namespace: "Attribute",
        label: "Created At",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: true,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
    ],
    relationships: [
      {
        id: "2932e32a-c666-42b0-a4b6-1c949cd4b000",
        name: "change",
        peer: "CoreProposedChange",
        kind: "Parent",
        label: "Change",
        description: null,
        identifier: "proposedchange__thread",
        inherited: true,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "source_branch__value",
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
        ],
        order_weight: 3000,
      },
      {
        id: "8a7f01e2-1f8f-4aee-8a1b-650e1f4d1647",
        name: "comments",
        peer: "CoreThreadComment",
        kind: "Component",
        label: "Comments",
        description: null,
        identifier: "thread__threadcomment",
        inherited: true,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [{ name: "id", kind: "Text", enum: null, object_kind: null, description: null }],
        order_weight: 4000,
      },
      {
        id: "78f5a19d-9f08-4845-a8ab-61c8a6e22865",
        name: "created_by",
        peer: "CoreAccount",
        kind: "Generic",
        label: "Created By",
        description: null,
        identifier: "coreaccount__corethread",
        inherited: true,
        cardinality: "one",
        branch: true,
        optional: true,
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
          {
            name: "type__value",
            kind: "Text",
            enum: ["User", "Script", "Bot", "Git"],
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
        ],
        order_weight: 5000,
      },
      {
        id: "136a218a-39ec-46f5-8b7a-619e24a39cb3",
        name: "member_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Member Of Groups",
        description: null,
        identifier: "group_member",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
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
        id: "e8e7d6ec-31fc-4a30-abc1-dd64430cf678",
        name: "subscriber_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Subscriber Of Groups",
        description: null,
        identifier: "group_subscriber",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
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
        order_weight: 7000,
      },
    ],
    label: "Change Thread",
    inherit_from: ["CoreThread"],
    groups: [],
    branch: true,
    filters: [
      { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
      {
        name: "resolved__value",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        name: "change__id",
        kind: "Object",
        enum: null,
        object_kind: "CoreProposedChange",
        description: null,
      },
    ],
    kind: "CoreChangeThread",
  },
];

export const conversationMocksQuery = `query {
  CoreThread(change__ids: "${proposedChangesId}") {
    count
    edges {
      node {
        __typename
        id
        display_label
        label {
          value
        }
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
  CoreAccount {
    edges {
      node {
        id
        display_label
      }
    }
  }
}
`;

export const conversationMocksData = {
  CoreThread: {
    count: 1,
    edges: [
      {
        node: {
          __typename: "CoreChangeThread",
          id: "25c4ffd2-b027-4d51-890f-6695953f99b5",
          display_label: "CoreChangeThread(ID: 25c4ffd2-b027-4d51-890f-6695953f99b5)",
          label: {
            value: "Conversation",
          },
          resolved: { value: false, __typename: "CheckboxAttribute" },
          created_by: { node: null, __typename: "NestedEdgedCoreAccount" },
          comments: {
            count: 3,
            edges: [
              {
                node: {
                  id: "38a32ad7-2873-4370-b403-04070465fc60",
                  display_label: "#1",
                  created_by: {
                    node: { display_label: "Admin", __typename: "CoreAccount" },
                    __typename: "NestedEdgedCoreAccount",
                  },
                  created_at: { value: "2023-07-27T18:51:50+02:00", __typename: "TextAttribute" },
                  text: { value: "#1", __typename: "TextAttribute" },
                  __typename: "CoreThreadComment",
                },
                __typename: "NestedEdgedCoreThreadComment",
              },
              {
                node: {
                  id: "904a407a-bb09-4443-980e-d0f0255cff86",
                  display_label: "#2",
                  created_by: {
                    node: { display_label: "Admin", __typename: "CoreAccount" },
                    __typename: "NestedEdgedCoreAccount",
                  },
                  created_at: { value: "2023-07-27T18:51:53+02:00", __typename: "TextAttribute" },
                  text: { value: "#2", __typename: "TextAttribute" },
                  __typename: "CoreThreadComment",
                },
                __typename: "NestedEdgedCoreThreadComment",
              },
              {
                node: {
                  id: "c8384ef4-3bbb-4530-99c0-bfa785c4343d",
                  display_label: "#3",
                  created_by: {
                    node: { display_label: "Admin", __typename: "CoreAccount" },
                    __typename: "NestedEdgedCoreAccount",
                  },
                  created_at: { value: "2023-07-27T18:51:55+02:00", __typename: "TextAttribute" },
                  text: { value: "#3", __typename: "TextAttribute" },
                  __typename: "CoreThreadComment",
                },
                __typename: "NestedEdgedCoreThreadComment",
              },
            ],
            __typename: "NestedPaginatedCoreThreadComment",
          },
        },
        __typename: "EdgedCoreChangeThread",
      },
    ],
    __typename: "PaginatedCoreChangeThread",
  },
};
