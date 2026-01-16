---
Title: File object feature
Author:
  - Wim Van Deun
  - Yvonne Jouffrault
Status: draft
JPD: INFP-403
---
# File object feature

## Backend

### Schema

#### CoreFileObject generic

A new `CoreFileObject` generic will be implemented, custom file object types need to be defined by the user, inheriting from this generic.

```yaml
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
---
version: "1.0"
generics:
  - name: FileObject # In Infrahub internal schema
    namespace: Core
    attributes:
      - name: file_name
        kind: Text
        optional: false
        read_only: true
        optional: false
      - name: checksum
        kind: Text
        read_only: true
        optional: false
      - name: file_size
        kind: Number
        read_only: true
        optional: false
      - name: file_type
        kind: Text
        read_only: true
        optional: false
      - name: storage_id
        kind: Text
        read_only: true
        optional: false
```

The following attributes will have to be defined:

- `file_name` (read-only, required) : the name of the file, as uploaded by the user
- `checksum` (read-only, required): checksum (md5 or sha1) calculated on the uploaded file
- `file_size` (read-only, required): the size of the file in bytes
- `file_type` (read-only, required): the type of the file, derived from the uploaded file’s file extension, or derived from the mime-type.
- `storage_id` (read-only, required): the id of the uploaded file in Infrahub’s storage

#### User-defined file object type

A user will have to define their own file attachment types in their schema. Multiple file attachment types can be defined.

For example here we define a CircuitContract type that we can attach to the Circuit type in the user’s schema

```yaml
---
- name: CircuitContract
  namespace: Network
  inherit_from:
    - CoreFileObject
  attributes:
    - name: contract_start
      kind: DateTime
      optional: false
    - name: active
      kind: Boolean
    - name: contract_end
      kind: DateTime
      optional: false
  relationships:
    - name: signed_by
      peer: CoreAccount
      kind: Attribute
      optional: false
      cardinality: one
    - name: circuit
      label: Circuit
      peer: NetworkCircuit
      kind: Attribute
      cardinality: one
      optional: true
```

Then on the specific type that you want to attach a file

```yaml
---
- name: Circuit
  namespace: Network
  attributes:
    - name: circuit_id
      kind: Text
      optional: false
    - name: bandwidth
      kind: Number
      optional: false
  relationships:
    - name: provider
      peer: OrganisationProvider
      kind: Attribute
      cardinality: one
      optional: false
    - name: contracts
      peer: NetworkCircuitContract
      kind: Generic
      cardinality: many
      optional: true
```

Here we define a new cardinality many relationship named contracts with the peer `NetworkCircuitContract`, meaning multiple contracts can be attached to the circuit object.

You can also use cardinality one relationships, if you want to create a file attachment of which you want to only have one. For example, you may want to only have the latest/current contract available on each circuit. In that case you can use a cardinality one relationship and modify the existing attachment as new contracts get closed for this circuit. Which would leverage Infrahub’s version control features to store previous versions of a file attachment.

The user will be able to use the different relationship kinds that are already available in Infrahub, to influence how the attachment will be displayed in the UI.

Another example of a file attachment could be a maintenance notification, that we also want to attach to a circuit

```yaml
---
- name: CircuitMaintenance
  namespace: Network
  inherit_from:
    - CoreFileObject
  attributes:
    - name: maintenance_start
      kind: DateTime
      optional: false
    - name: maintenance_end
      kind: DateTime
      optional: false
    - name: acknowledged
      kind: Boolean
      optional: false
      default_value: false
  relationships:
    - name: circuit
      label: Circuit
      peer: NetworkCircuit
      kind: Attribute
      cardinality: one
      optional: true
    - name: acknowledged_by
      peer: CoreAccount
      kind: Attribute
      cardinality: one
      optional: true
```

Then on the circuit type

```yaml
---
- name: Circuit
  namespace: Network
  attributes:
    - name: circuit_id
      kind: Text
      optional: false
    - name: bandwidth
      kind: Number
      optional: false
  relationships:
    - name: provider
      peer: OrganisationProvider
      kind: Attribute
      cardinality: one
      optional: false
    - name: contracts
      peer: NetworkCircuitContract
      kind: Generic
      cardinality: many
      optional: true
    - name: maintenance_notifications
      kind: Generic
      peer: NetworkCircuitMaintenance
      cardinality: many
      optional: true
```

While implementing this part, we do not require to write tests. The definition and inheritance of generics and nodes in the schema is already something very well tested. We do not need to write tests when adding more to the schema.

### Version control

File objects should be able to be version controlled, similar to other objects in Infrahub's database.

This means that the file object can be modified over time and that Infrahub will keep track of the state of the object.

This also implies that the storage object in Infrahub's storage system will have to exist forever, and when a file object is "deleted" from the database, that the storage object will not be deleted. This implies that we need to find a way to store multiple time the same file, and have a way to tell when a file has been deleted, edited and in which branch did the action happen.

We should be able to create file objects in a branch, and use the branch merge or proposed change functionality to merge that change into the main branch.

Users should also have the capability to define file objects as branch agnostic.

### Permission system

File object's need to be integrated with Infrahub's permission system, so that you can control who can view/edit/create file objects.

It's important that the permission system not only considers the permission on the file object, but also on the storage object itself. A user who has no permission to view a `FileObject` object should also not have a capability to download the object using the storage API.

### File size limitation

We should be able to configure a maximum file size for CoreFileObject. When a user tries to upload an file object that is to big, we should be able to deny the creation of this file object.

The feature is scoped to add small file objects (config, office-type documents, images), IE no multi-GB size of files, for example device firmware.

In Infrahub's configuration file, we need add a new setting that allows us to set the maximum file size of file objects.

If this configuration setting is not provided, we should provide a default value

```toml
[storage]
driver = "local"
max_file_size=50 #in MB
```

### GraphQL API

New GraphQL queries and mutations should be added to create file objects

#### Querying for file object

Using the generic `CoreFileObject`

```graphql
query {
  CoreFileObject {
    edges {
      node_metadata {
        created_at
        created_by {
          id
          name {
            value
          }
        }
        updated_at
        updated_by {
          id
        }
        node {
          file_name {
            value
          }
          checksum {
            value
          }
          file_size {
            value
          }
          file_type {
            value
          }
          storage_id {
            value
          }
        }
      }
    }
  }
}
```

Using the specific type query, using the above schema as an example

```graphql
query {
  NetworkCircuitContract {
    edges {
      node {
        name {
          value
        }
        file_name {
          value
        }
        checksum {
          value
        }
        file_size {
          value
        }
        file_type {
          value
        }
        storage_id {
          value
        }
        circuit {
          node {
            id
          }
        }
        contract_start {
          value
        }
        contract_end {
          value
        }
        signed_by {
          node {
            value
          }
        }
      }
    }
  }
}
```

#### GraphQL query filters

For the above example, the following filters should be available:

- `name__value`
- `name__values`
- `checksum__value`
- `checksum__values`
- `file_name__value`
- `file_names__value`
- `name__values`
- `file__size__value`
- `file__size__values`
- `file__type__value`
- `file__type__values`
- `storage__id__value`
- `storage__id__values`
- `contract_start__value`
- `contract_start__values`
- `contract_end__value`
- `contract_end__values`
- `circuit__ids`
- `circuit__attribute__value`
- `signed_by__ids`
- `signed_by__attribute__value`

Technically these filters should be auto-generated by our GraphQL manager code. However these should appear in tests to ensure that:
1. They are properly generated and exposed at the GraphQL layer
2. They work as expected when we try using them

#### Mutations

The following mutations need to be implemented, although the goal is that they should probably not be used by the end-users directly.

```graphql
mutation {
  NetworkCircuitContractCreate(
    data: {
      # These are here for reference but as they are read-only field, they should not appear in the mutation
      # file_name: {value: ""},
      # checksum: {value: ""},
      # file_size: {value: 123},
      # file_type: {value: ""},
      # storage_id: {value: ""},
      circuit: {id: ""},
      contract_start: {value: ""},
      contract_end: {value: ""},
      signed_by: {id: ""},
    }
  ) {
    ok
    __typename
    object {
      id
    }
  }
}
```

```graphql
mutation {
  NetworkCircuitContractUpdate(
    data: {
      id: "",
      hfid: [""],
      # These are here for reference but as they are read-only field, they should not appear in the mutation
      # file_name: {value: ""},
      # checksum: {value: ""},
      # file_size: {value: 123},
      # file_type: {value: ""},
      # storage_id: {value: ""},
      circuit: {id: ""},
      contract_start: {value: ""},
      contract_end: {value: ""},
      signed_by: {id: ""},
    }
  ) {
    ok
    __typename
    object {
      id
    }
  }
}
```

```graphql
mutation {
  NetworkCircuitContractUpsert(
    data: {
      id: "",
      hfid: [""],
      # These are here for reference but as they are read-only field, they should not appear in the mutation
      # file_name: {value: ""},
      # checksum: {value: ""},
      # file_size: {value: 123},
      # file_type: {value: ""},
      # storage_id: {value: ""},
      circuit: {id: ""},
      contract_start: {value: ""},
      contract_end: {value: ""},
      signed_by: {id: ""},
    }
  ) {
    ok
    __typename
    object {
      id
    }
  }
}
```

```graphql
mutation {
  NetworkCircuitContractDelete(
    data: {
      id: "",
      hfid: [""],
    }
  ) {
    ok
    __typename
  }
}
```

Same as the filters, the GraphQL queries and mutations should be auto-generated by our GraphQL manager code. However these should appear in tests to ensure that:
1. They are properly generated and exposed at the GraphQL layer
2. They work as expected when we try using them

### REST API

Infrahub already has the `/api/storage` API endpoints. However these endpoints do not take Infrahub's permission system into account.

We need to add new REST API endpoints that allow you to upload and download `FileObject` objects, that also take the permission system into account.

Endpoints for nodes implementing the `FileObject` generic should be exposed via the REST API like `/api/{node_kind}/object/`. We currently do not have any mechanism capable of doing that. This can create a significant amount of work to implement this. For instance, if we have `NetworkCircuitContract` inheriting from `CoreFileObject` in the schema, we should have endpoints like `/api/NetworkCircuitContract/object/{identifier}` and `/api/NetworkCircuitContract/upload` generated automatically.

#### Download FileObject

```text
GET /api/CoreFileObject/object/{identifier}
Return headers:
- Content-Length
- Content-Type > derrived from the FileObject
- Content-Disposition > contains the file name derrived from the FileObject
Return: {content}
```

When receiving this HTTP request, Infrahub should look up the CoreFileObject object using the `storage_id__value` filter.

We can then validate that the user has the correct permission to view/download the `CoreFileObject` object.

#### Upload FileObject

```text
POST /api/CoreFileObject/upload
Body: {"file": "String"} # binary
Return: {"identifier": {identifier}, "checksum": "String"}
```

We also have to explore if [uploading a file via our GraphQL API](https://graphql.org/learn/file-uploads/) is something sustainable.

#### Open questions

- What is the right order of operation? Do we first create the `CoreFileObject` object and then the object in the storage system, or the other way around?

### Python SDK

We need to add the ability to create `CoreFileObjects` and relate them to other objects using the Python SDK.

#### Adding a new FileObject

This method, would allow the user to upload and attach a new attachment to an object.
This method should work for cardinality one or many attachment relationships.

Mainly a convenience method to avoid the user having to upload and create the CoreFileAttachment object in a separate step.

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

# Creating a CoreFileAttachment

account = client.get(kind=CoreUserAccount, id=<uuid>)
circuit = client.get(kind=InfraCircuit, id=<uuid>)

identifier = client.file_object.upload(content=Path("/tmp/contract.pdf").read())
circuit_contract = client.create(
    kind=NetworkCircuitContract,
    circuit=circuit,
    name="contract",
    contract_start="2026-01-01",
    contract_end="2026-12-31",
    signed_by=account,
    storage_id=identifier
)
circuit_contract.save()
```

#### Downloading a FileObject

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

account = client.get(kind=CoreUserAccount, id=<uuid>)

# for card many
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contracts"], prefetch_relationships=True)
contract: NetworkCircuitContract = circuit.contracts.peers[0].peer
content = client.file_object.get(identifier=contract.storage_id.value)

with open(f"/tmp/{contract.file_name.value}", "wb") as f:
    f.write(content)

# for card one
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contract"], prefetch_relationships=True)

contract: NetworkCircuitContract = circuit.contract.peer
content = client.file_object.get(identifier=contract.storage_id.value)
with open(f"/tmp/{contract.file_name.value}", "wb") as f:
    f.write(content)
```

#### Updating a FileObject

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

# Creating a CoreFileAttachment

account = client.get(kind=CoreUserAccount, id=<uuid>)

# card many
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contracts"], prefetch_relationships=True)

contract: NetworkCircuitContract = circuit.contracts.peers[0].peer
contract.contract_start = "2026-02-01"
contract.save(allow_upsert=True)

# card one
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contract"], prefetch_relationships=True)

contract: NetworkCircuitContract = circuit.contract.peer
contract.contract_start = "2026-02-01"
contract.save(allow_upsert=True)
```

#### Uploading a new version of a FileObject

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

# Creating a CoreFileAttachment

account = client.get(kind=CoreUserAccount, id=<uuid>)

# Card many
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contracts"], prefetch_relationships=True)
contract: NetworkCircuitContract = circuit.contracts.peers[0].peer

identifier = client.file_object.upload(content=Path("/tmp/contract.pdf").read())

contract.storage_id = identifier
contract.save()

# Card one
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contract"], prefetch_relationships=True)

contract: NetworkCircuitContract = circuit.contract.peer
identifier = client.file_object.upload(content=Path("/tmp/contract.pdf").read())

contract.storage_id = identifier
contract.save()
```

### Open issues

- A known issue will occur when there is a merge conflict. For example, a branch was created after which a file object is updated in the main branch and the newly created branch. When opening a proposed change the user will be asked to resolve a conflict. Today conflict resolution works at the attribute or relationship level, not at the object-level. This means it is possible for the user to pick the checksum of the main branch and the storage_id of the other branch, invalidating the file object. For the first implementation this will be a documented limitation, but we should look at object level conflict resolution (new card to be created)
- What should be default file size limitation that we implement
- Are we going to implement the file upload feature using the GraphQL API, or do we implement a separate REST API. An implementation for Graphene seems to exist here: https://github.com/lmcgartland/graphene-file-upload
  - The current storage system only supports text based files
  - REST API is currently not branch aware, meaning we can't automatically generate rest endpoints for new `FileObjects` in the schema, but we can probably just work with one generic Rest API endpoint
  - If we implement a REST API endpoint, we need to make sure we cannot download object files using the storage api, since it doesn't have permission enforcement. For this there's 2 options 1) introduce permissions for artifacts 2) have separate storage "directories" so that object files with permissions cannot be retrieved using the storage API.

### Future considerations

- How can we implement a `FileObject` for which the actual file will not be stored in Infrahub's storage system, for example a config backup in an external system
- Can we implement a system where permissions are automatically inherited from the object that the `FileObject` relates too. For example, a circuit contract would automatically inherit the permissions of the circuit.
  - Probably this effort could be part of a bigger effort around revisiting the permission system (more granular permission system)
  - What do we do in the case where a `FileObject` is related to many other objects
- What is the overlap with the existing Artifacts feature in Infrahub and how can we consolidate some of the functionality
- Can we implement a file type restriction for a given `FileObject` type. For example, I only want to have PDF files for `NetworkCircuitContract` file objects
  - Should be defined in the schema
  - Special type of attribute kind?
  - How do we handle migrations?

## Frontend Scope

### Schema-Driven Display

- FileObjects should behave like any other object type in Infrahub
  - File object list view
  - File object detailed view
- FileObject detailed view will have a section at the bottom that renders the content of the file object, if it is of a supported file type. This section is similar to what the artifact detailed page has today and will be displayed at the bottom of the FileObject detailed page.
- The FileObject create/update form, will have a "file upload" widget that allows you to upload the file that should be stored for this FileObject object.

### Relations

FileObjects can be related to any other object in Infrahub, by creating relationships to other object types in the schema.
This give the user the impression of attachments.

### API Integration Needs

- **Query**: Fetch `FileObject` objects via GraphQL using relationship (e.g., circuit.contracts)
- **Update**: Mutate the file object data
- **Delete**: Delete file  object
- **Upload**: POST to /api/CoreFileObject/upload → Create storage object
- **Download**: GET /api/CoreFileObject/object/{identifier}

### Key Frontend Considerations

- **Permission-aware**: Only show Upload/Edit/Delete if user has permission
- **Branch-aware**: Display file objects for current branch context
- **Relationship kind handling**: Respect Generic vs Attribute kind for display style
- **Error handling**: File size exceeded, upload failures, permission denied
- **Loading states**: Upload progress, file preview loading

### Open Questions [UI]

- ‘delete’ :  do we allow ‘delete file’ and allow the ‘file object’ to be saved with custom fields but no file' OR do we only allow ‘delete’ file object in which case the user must delete the entire file object and then ‘create/upload’ a new one.  [there might be a use case where they want to replace the file but delete existing and then save/come back to upload a new one]
- What metadata do we want to display for the file (file size, upload date, type, who uploaded it?)
- Do we want to give the user the option to preview/replace/delete inline in the Object detail view or ONLY on the ‘edit modal’ in the right panel.  [the simpler option]
- For cardinality ‘many’ :  will we also allow min + max ?  from paul: “so when creating an object that has attachments, we won't be able to have a min count since we don't provide file attachments in the object creation form, only afterwardswe can see later if that's an issue but having it as 2 steps for now and figure it out”.
