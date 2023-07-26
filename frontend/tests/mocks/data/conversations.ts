export const proposedChangesId = "1cec1fe9-fcc4-4f5b-af30-9d661de65bd8";

export const conversationMocksSchema = [
  {
    id: "c277c2ff-39cf-4891-a018-2b58a0f35f8a",
    name: "ProposedChange",
    namespace: "Core",
    description: "Metadata related to a proposed change",
    default_filter: "name__value",
    order_by: null,
    display_labels: ["name__value"],
    attributes: [
      {
        id: "2d67ce8f-5192-4acc-981d-5a7e7de1ded0",
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
        id: "48cce2c0-8c91-41ae-a63a-12669d3b7210",
        name: "source_branch",
        kind: "Text",
        namespace: "Attribute",
        label: "Source Branch",
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
        order_weight: 2000,
      },
      {
        id: "6ee398e3-2221-494b-94ee-9da3dd88c651",
        name: "destination_branch",
        kind: "Text",
        namespace: "Attribute",
        label: "Destination Branch",
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
        id: "9e872e86-d9b0-4a96-aace-ace686860c15",
        name: "approved_by",
        peer: "CoreAccount",
        kind: "Attribute",
        label: "Approved By",
        description: null,
        identifier: "coreaccount__proposedchange_approved_by",
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
        order_weight: 4000,
      },
      {
        id: "d5d2876c-2c83-4d63-be1b-38bdef01b793",
        name: "reviewers",
        peer: "CoreAccount",
        kind: "Attribute",
        label: "Reviewers",
        description: null,
        identifier: "coreaccount__proposedchange_reviewed_by",
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
        id: "887b88ee-4bae-4938-ae08-e79ca1f9f93c",
        name: "created_by",
        peer: "CoreAccount",
        kind: "Generic",
        label: "Created By",
        description: null,
        identifier: "coreaccount__proposedchange_created_by",
        inherited: false,
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
        order_weight: 6000,
      },
      {
        id: "c3e9dd13-a476-4b43-84d6-980a6d27655d",
        name: "comments",
        peer: "CoreChangeComment",
        kind: "Component",
        label: "Comments",
        description: null,
        identifier: "corechangecomment__coreproposedchange",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [{ name: "id", kind: "Text", enum: null, object_kind: null, description: null }],
        order_weight: 7000,
      },
      {
        id: "7cdde1b4-81fc-407a-9c2a-df4f42bb784f",
        name: "threads",
        peer: "CoreThread",
        kind: "Component",
        label: "Threads",
        description: null,
        identifier: "proposedchange__thread",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "resolved__value",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 8000,
      },
      {
        id: "0459736e-6195-404e-8e0d-6d0d24368ca2",
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
        order_weight: 9000,
      },
      {
        id: "a54b3c01-ac8b-40e3-b580-c2ae690a7f15",
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
        order_weight: 10000,
      },
    ],
    label: "Proposed Change",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [
      { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
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
      {
        name: "approved_by__id",
        kind: "Object",
        enum: null,
        object_kind: "CoreAccount",
        description: null,
      },
      {
        name: "reviewers__id",
        kind: "Object",
        enum: null,
        object_kind: "CoreAccount",
        description: null,
      },
    ],
    kind: "CoreProposedChange",
  },
];

export const conversationMocksQuery = `query {
  CoreProposedChange(ids: ["${proposedChangesId}"]) {
    count
    edges {
      node {
        id
        display_label
        __typename
        _updated_at

          name {
              value
          }
          source_branch {
              value
          }
          destination_branch {
              value
          }

          approved_by {
              edges {
              node {
                id
                display_label
              }
              }
          }
          reviewers {
              edges {
              node {
                id
                display_label
              }
              }
          }

        created_by {
          node {
            id
            display_label
          }
        }

        threads {
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
        comments {
          count
          edges {
            node {
              __typename
              id
              display_label
              _updated_at
              created_by {
                node {
                  display_label
                }
              }
              created_at {
                value
              }
            }
          }
        }
      }
    }
  }
}
`;

export const conversationMocksData = {
  CoreProposedChange: {
    count: 1,
    edges: [
      {
        node: {
          id: proposedChangesId,
          display_label: "PR",
          __typename: "CoreProposedChange",
          _updated_at: "2023-07-24T12:27:10.730710+00:00",
          name: { value: "PR", __typename: "TextAttribute" },
          source_branch: { value: "test", __typename: "TextAttribute" },
          destination_branch: { value: "main", __typename: "TextAttribute" },
          approved_by: { edges: [], __typename: "NestedPaginatedCoreAccount" },
          reviewers: { edges: [], __typename: "NestedPaginatedCoreAccount" },
          created_by: {
            node: {
              id: "9806def4-8c09-4489-bffb-181c427165f5",
              display_label: "Administrator",
              __typename: "CoreAccount",
            },
            __typename: "NestedEdgedCoreAccount",
          },
          threads: {
            count: 1,
            edges: [
              {
                node: {
                  __typename: "CoreChangeThread",
                  id: "3bcc2686-8d86-4916-8e4e-2aaf06be7cdb",
                  display_label: "CoreChangeThread(ID: 3bcc2686-8d86-4916-8e4e-2aaf06be7cdb)",
                  resolved: { value: false, __typename: "CheckboxAttribute" },
                  created_by: { node: null, __typename: "NestedEdgedCoreAccount" },
                  comments: {
                    count: 3,
                    edges: [
                      {
                        node: {
                          id: "48eecc83-61da-4bdd-b07b-dad28f446ec2",
                          display_label: "First thread with comment",
                          created_by: {
                            node: { display_label: "Administrator", __typename: "CoreAccount" },
                            __typename: "NestedEdgedCoreAccount",
                          },
                          created_at: {
                            value: "2023-07-24T14:27:19+02:00",
                            __typename: "TextAttribute",
                          },
                          text: {
                            value: "First thread with comment",
                            __typename: "TextAttribute",
                          },
                          __typename: "CoreThreadComment",
                        },
                        __typename: "NestedEdgedCoreThreadComment",
                      },
                      {
                        node: {
                          id: "d13a25a8-67fe-42c9-82b9-172a5eb69619",
                          display_label: "third comment",
                          created_by: {
                            node: { display_label: "Administrator", __typename: "CoreAccount" },
                            __typename: "NestedEdgedCoreAccount",
                          },
                          created_at: {
                            value: "2023-07-24T14:27:30+02:00",
                            __typename: "TextAttribute",
                          },
                          text: { value: "third comment", __typename: "TextAttribute" },
                          __typename: "CoreThreadComment",
                        },
                        __typename: "NestedEdgedCoreThreadComment",
                      },
                      {
                        node: {
                          id: "fd37cce5-19a8-478f-b816-5e592ecc1169",
                          display_label: "Second comment",
                          created_by: {
                            node: { display_label: "Administrator", __typename: "CoreAccount" },
                            __typename: "NestedEdgedCoreAccount",
                          },
                          created_at: {
                            value: "2023-07-24T14:27:25+02:00",
                            __typename: "TextAttribute",
                          },
                          text: { value: "Second comment", __typename: "TextAttribute" },
                          __typename: "CoreThreadComment",
                        },
                        __typename: "NestedEdgedCoreThreadComment",
                      },
                    ],
                    __typename: "NestedPaginatedCoreThreadComment",
                  },
                },
                __typename: "NestedEdgedCoreThread",
              },
            ],
            __typename: "NestedPaginatedCoreThread",
          },
          comments: { count: 0, edges: [], __typename: "NestedPaginatedCoreChangeComment" },
        },
        __typename: "EdgedCoreProposedChange",
      },
    ],
    __typename: "PaginatedCoreProposedChange",
  },
};
