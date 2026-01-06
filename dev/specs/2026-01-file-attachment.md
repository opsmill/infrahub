---
Title: Object file attachment feature
Author: 
  - Wim Van Deun
  - Yvonne Jouffrault
Status: draft
JPD: INFP-403
---
# Object File attachment feature

## Backend

### Schema

#### CoreFileAttachment generic

A new `CoreFileAttachment` generic will be implemented, custom file attachment types need to be defined by the user, inheriting from this generic.

```yaml
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
---
version: "1.0"
generics:
  - name: FileAttachment # In Infrahub internal schema
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
    relationships:
      - name: attached_object
        peer: CoreNode
        kind: Attribute
        cardinality: one
        optional: false
        read_only: true
```

The following attributes will have to be defined:

- `file_name` (read-only, required) : the name of the file, as uploaded by the user
- `checksum` (read-only, required): checksum (md5 or sha1) calculated on the uploaded file
- `file_size` (read-only, required): the size of the file in bytes
- `file_type` (read-only, required): the type of the file, derived from the uploaded file’s file extension
- `storage_id` (read-only, required): the id of the uploaded file in Infrahub’s storage

The following relationship will be defined:

- `attached_object` (read-only, required) : The object that the file will be attached to. An file can only be attached to one single object (cardinality one). Since a file object can be attached to any type of object, the peer of the relationship needs to be the CoreNode generic.

#### User defined file attachment type

A user will have to define their own file attachment types in their schema. Multiple file attachment types can be defined.

For example here we define a CircuitContract type that we can attach to the Circuit type in the user’s schema

```yaml
  - name: CircuitContract
    namespace: Attachment
    inherit_from:
      - CoreFileAttachment
    attributes:
      - name: contract_start
        kind: DateTime
        optional: false
      - name: contract_end
        kind: DateTime
        optional: false
    relationships:
      - name: signed_by
        peer: CoreAccount
        kind: Attribute
        optional: false
        cardinality: one
```

Then on the specific type that you want to attach a file

```yaml
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
        peer: AttachmentCircuitContract
        kind: Generic
        cardinality: many
        optional: true
```

Here we define a new cardinality many relationship named contracts with the peer `AttachmentCircuitContract`, meaning multiple contracts can be attached to the circuit object.

You can also use cardinality one relationships, if you want to create a file attachment of which you want to only have one. For example, you may want to only have the latest/current contract available on each circuit. In that case you can use a cardinality one relationship and modify the existing attachment as new contracts get closed for this circuit. Which would leverage Infrahub’s version control features to store previous versions of a file attachment.

The user will be able to use the different relationship kinds that are already available in Infrahub, to influence how the attachment will be displayed in the UI.

Another example of a file attachment could be a maintenance notification, that we also want to attach to a circuit

```yaml
  - name: CircuitMaintenance
    namespace: Attachment
    inherit_from:
      - CoreFileAttachment
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
      - name: acknowledged_by
        peer: CoreAccount
        kind: Attribute
        cardinality: one
        optional: true
```

Then on the circuit type

```yaml
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
        peer: AttachmentCircuitContract
        kind: Generic
        cardinality: many
        optional: true
      - name: maintenance_notifications
        kind: Generic
        peer: AttachmentCircuitMaintenance
        cardinality: many
        optional: true
```

### Version control

File attachment objects should be able to be version controlled, similar to other objects in Infrahub's database.

This means that the file attachment object can be modified over time and that Infrahub will keep track of the state of the object.

This also implies that the storage object in Infrahub's storage system will have to exist forever, and when an attachment object is "deleted" from the database, that the storage object will not be deleted.

We should be able to create file attachments for a specific object in a branch, and use the branch merge or proposed change functionality to merge that change into the main branch.

Users should also have the capability to define file attachment objects as branch agnostic. So that an attachment to a specific object is the same in all the branches that exist in the system.

#### Open issues

A known issue will occur when there is a merge conflict. For example, a branch was created after which the attachment is updated in the main branch and the newly created branch. When opening a proposed change the user will be asked to resolve the conflict. Today conflict resolution works at the attribute or relationship level, not at the object level. This means it is possible for the user to pick the checksum of the main branch and the storage_id of the other branch, invalidating the attachment. For the first implementation this is going to be a documented limitation, but we should look at object level conflict resolution (new card to be created)

### Permission system

File attachments object's need to be integrated with Infrahub's permission system, so that you can control who can view/edit/create attachments.

It's important that the permission system not only considers the permission on the `FileAttachment` object, but also on the storage object itself. A user that has no permission to view a `FileAttachment` object should also not have a capability to download the object using the storage API.

For a future iteration of this solution we are going to look into automatically inheriting the permission from the object that the FileAttachment object is attached to. This is currently out-of-scope for this iteration.

### File size limitation

We should be able to configure a maximum file size for CoreFileAttachments. When a user tries to upload an attachment that is to big, we should be able to deny the creation of this attachment.

The feature is scoped to add "small" attachments (config, word type documents, images), IE no multi GB size of files, for example device firmware.

In Infrahub's configuration file, we need add a new setting that allows us to set the maximum file size of attachments.

If this configuration setting is not provided, we should provide a default value

```toml
[storage]
driver = "local"
attachment_max_file_size=200 #in MB
```

#### Open question

- What should be the default file size limitation?

### GraphQL API

New GraphQL queries and mutations should be added to create file attachment objects

#### Querying for file attachments

Using the generic `CoreFileAttachment`

```graphql
query {
  CoreFileAttachment {
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
          file_checksum {
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
          attached_object {
            node {
              id
            }
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
  AttachmentCircuitContract {
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
	attached_object {
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
	  node {value
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
- `attached_object__ids`
- `signed_by__ids`
- `signed_by__attribute__value`

#### Mutations

The following mutations need to be implemented, although the goal is that they should probably not be used by the end-users directly.

```graphql
mutation {
  AttachmentCircuitContractCreate(
    data: {
      name: {value: ""}, 
      checksum: {value: ""},
      file_size: {value: 123},
      file_type: {value: ""},
      storage_id: {value: ""},
      attached_object: {id: ""},
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
  AttachmentCircuitContractUpdate(
    data: {
      id: "",
      hfid: [""],
      name: {value: ""}, 
      checksum: {value: ""},
      file_size: {value: 123},
      file_type: {value: ""},
      storage_id: {value: ""},
      attached_object: {id: ""},
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
  AttachmentCircuitContractUpsert(
    data: {
      id: "",
      hfid: [""],
      name: {value: ""}, 
      checksum: {value: ""},
      file_size: {value: 123},
      file_type: {value: ""},
      storage_id: {value: ""},
      attached_object: {id: ""},
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
  AttachmentCircuitContractDelete(
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

### REST API

Infrahub already has the `/api/storage` API endpoints. However these endpoints do not take Infrahub's permission system into account.

We need to add new REST API endpoints that allow you to upload and download FileAttachment objects, that also take the permission system into account.

#### Download FileAttachments

```
GET /api/CoreFileAttachment/object/{identifier}
Return headers:
- Content-Length
- Content-Type > derrived from the FileAttachmentObject
- Content-Disposition > contains the file name derrived from the FileAttachmentObject
Return: {content}
```

When receiving this HTTP request, Infrahub should look up the CoreFileAttachment object using the storage_id__value filter.

We can then validate that the user has the correct permission to view/download the CoreFileAttachment object.

#### Upload FileAttachments

```
POST /api/CoreFileAttachment/upload
Body: {"file": "String"} # binary
Return: {"identifier": {identifier}, "checksum": "String"}
```

#### Open questions

- Should the REST API endpoint to upload file content, accept the identifier of the FileAttachment object, this would allow us to validate the permission of the CoreFileAttachment object for the current user.
- What is the right order of operation? Do we first create the CoreFileAttachment object and then the object in the storage system, or the other way around?

### Python SDK

We need to add the ability to create CoreFileAttachments and attach them to an object using the Python SDK.

#### Adding a new attachment

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

attachment = client.create_attachment(
    kind=CircuitContractAttachment,
	attached_object=circuit,
	relationship="contracts",
	name="contract",
	contract_start="2026-01-01",
	contract_end="2026-12-31",
	signed_by=account,
	file=Path("/tmp/contract.pdf")
)
```

#### Downloading an attachment

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

account = client.get(kind=CoreUserAccount, id=<uuid>)

# for card many
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contracts"], prefetch_relationships=True)

attachment: CircuitContractAttachment = circuit.contracts.peers[0].peer
content = attachment.download()
with open(f"/tmp/{attachment.file_name.value}", "wb") as f:
    f.write(content)
	
	
# for card one
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contract"], prefetch_relationships=True)

attachment: CircuitContractAttachment = circuit.contract.peer
content = attachment.download()
with open(f"/tmp/{attachment.file_name.value}", "wb") as f:
    f.write(content)
```

#### Updating an attachment

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

# Creating a CoreFileAttachment

account = client.get(kind=CoreUserAccount, id=<uuid>)

# card many
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contracts"], prefetch_relationships=True)

attachment: CircuitContractAttachment = circuit.contracts.peers[0].peer
attachment.contract_start = "2026-02-01"
attachment.save(allow_upsert=True)

# card one
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contract"], prefetch_relationships=True)

attachment: CircuitContractAttachment = circuit.contract.peer
attachment.contract_start = "2026-02-01"
attachment.save(allow_upsert=True)
```

#### Uploading a new version of an attachment

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

# Creating a CoreFileAttachment

account = client.get(kind=CoreUserAccount, id=<uuid>)

# Card many
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contracts"], prefetch_relationships=True)

attachment: CircuitContractAttachment = circuit.contracts.peers[0].peer
attachment.upload(Path("/tmp/contract_new.pdf"))

# Card one
circuit = client.get(kind=InfraCircuit, id=<uuid>, include=["contract"], prefetch_relationships=True)

attachment: CircuitContractAttachment = circuit.contract.peer
attachment.upload(Path("/tmp/contract_new.pdf"))
```

## Frontend Scope

### Schema-Driven Display

- Detect attachment relationship in schema for current object type
- Read relationship cardinality (one or many) from schema
- Read relationship kind (Generic, Attribute, etc.) to determine display style
- Extract custom fields from user-defined FileAttachment type for form fields

### Inline Display (Attribute Field)

#### Empty State (No Files Uploaded)

- Display "no file uploaded yet" text in attribute row
- Show Upload button/icon inline

#### Single File Display (Cardinality: One)

- Display file as single inline element in attribute row
- Show: file name + key metadata (size, type, upload date)
- Click file → Opens file detail/edit side panel

#### Multiple Files Display (Cardinality: Many)

- Display files as tag-style chips (similar to existing tags UI)
- Each chip shows: file name + icon
- Show Upload icon/button to add more files
- Click individual chip → Opens file detail/edit side panel for that file

### Upload Side Panel (New File)

- **File selection**: Drag-and-drop or browse button
- **Form fields**: Dynamically generated from schema
  - Core fields: name/description (if editable)
  - Custom fields from user-defined FileAttachment type (e.g., contract_start, contract_end, signed_by)
- **Validation**: File size limit check (from backend config)
- **Actions**: Cancel, Upload & Attach

### File Detail/Edit Side Panel (Existing File)

- **Read-only fields**: file_name, checksum, file_size, file_type, storage_id
- **Editable fields**: Custom attributes from schema (e.g., contract_start, contract_end)
- **File preview**: For supported types (PDFs, images)
- **Actions**:
  - Replace file: Upload new version (updates storage_id, checksum, file_size, file_type)
  - Delete attachment: delete attachment object
  - Download file: Download current version
  - Save changes: Update editable metadata only

### API Integration Needs

- **Query**: Fetch attachment objects via GraphQL using relationship (e.g., circuit.contracts)
- **Update**: Mutate the file attachment object data
- **Delete**: Delete file attachment object
- **Upload**: POST to /api/CoreFileAttachment/upload → Create storage object
- **Download**: GET /api/CoreFileAttachment/object/{identifier}

### Key Frontend Considerations

- **Permission-aware**: Only show Upload/Edit/Delete if user has permission
- **Branch-aware**: Display attachments for current branch context
- **Relationship kind handling**: Respect Generic vs Attribute kind for display style
- **Error handling**: File size exceeded, upload failures, permission denied
- **Loading states**: Upload progress, file preview loading

### Open Questions [UI] 

- ‘delete’ :  do we allow ‘delete file’ and allow the ‘file object’ to be saved with custom fields but no file' OR do we only allow ‘delete’ file object in which case the user must delete the entire file object and then ‘create/upload’ a new one.  [there might be a use case where they want to replace the file but delete existing and then save/come back to upload a new one] 
- What metadata do we want to display for the file (file size, upload date, type, who uploaded it?) 
- Do we want to give the user the option to preview/replace/delete inline in the Object detail view or ONLY on the ‘edit modal’ in the right panel.  [the simpler option] 
- For cardinality ‘many’ :  will we also allow min + max ?  from paul: “so when creating an object that has attachments, we won't be able to have a min count since we don't provide file attachments in the object creation form, only afterwardswe can see later if that's an issue but having it as 2 steps for now and figure it out”. 
