# Infrahub glossary

This file is the glossary for Infrahub. Each entry gives the name to use for one domain concept, a
definition, and the other names to avoid, with a reason where the reason is not obvious. Use these
names in code, GraphQL schema, specs, ADRs, commit messages, pull request descriptions, and
conversation.

The `grilling-ideas` and `creating-prd` skills use this file to choose domain terms. The
`creating-issues`, `pr`, and `speckit-opsmill-implement` skills read it as project context. None of
these skills names `dev/knowledge/` as a place to look for `CONTEXT.md`, so the root `AGENTS.md`
points to this file.

When a change adds a domain concept, renames one, or changes what one means, update this file in the
same pull request. An entry that includes "Not decided" records a question that the sources answer
in different ways; do not treat either answer as the rule until the entry is updated.

For the principles that every change follows, see [`dev/constitution.md`](../constitution.md). For
how the system works, see [`dev/knowledge/`](.). For past decisions, see [`dev/adr/`](../adr/).

## Schema

**Schema**:
The data model of an Infrahub instance: which kinds of objects can exist, their attributes and
relationships, and their validation rules. Infrahub stores the schema in its database, so each
branch can have a different schema. YAML schema files are not the schema itself; loading a file
creates or updates the schema that Infrahub stores. Source: [About
schema](../../docs/docs/schema/overview.mdx).
_Avoid_: "data model" as a separate term (the docs use it to explain the schema, not as another
concept), "schema file" for the loaded schema (the file is only the input).

**Kind**:
The identifier of a node or generic in the schema, made by joining its `namespace` and its `name`,
for example `InfraDevice`. Attributes and relationships also have a `kind`, which comes from
Infrahub (for example `Text` or `Component`) and controls how the element appears in GraphQL and the
web interface. Source: [Nodes & attributes](../../docs/docs/schema/nodes-and-attributes.mdx).
_Avoid_: "type" and "model" for a node's kind (both are used in prose, but the schema, GraphQL, and
SDK use `kind`), "class".

**Node**:
A schema definition of a kind that objects can be created from, such as `InfraDevice`. A node has
attributes and relationships and can inherit from generics. It is the counterpart of a **generic**.
Source: [Nodes & attributes](../../docs/docs/schema/nodes-and-attributes.mdx).
Not decided: whether "node" also names a stored record. The [documentation agent
instructions](../../docs/AGENTS.md) say to call a stored record an "object" in user-facing text and
to keep "node" for the schema kind. The OpsMill organization-wide writing instructions for product
documents say to use "node", not "object". The product itself uses both words for a stored record:
the Python SDK class is `InfrahubNode`, GraphQL results return each record in a `node` field, the
[Generators page](../../docs/docs/generators/overview.mdx) says a Generator "creates new nodes", and
the web interface has both "Related Nodes" (event details) and "Source Object" (path traversal).
_Avoid_: "schema node" and "node kind" only where the context already shows that a schema definition
is meant; "model".

**Generic**:
A schema definition that shares attributes and relationships across several nodes. A node lists the
generics it inherits from in `inherit_from` and receives their attributes and relationships. No
object can be created from a generic alone. A relationship whose peer is a generic can connect to
objects of every node that inherits from it. Source: [Generics &
inheritance](../../docs/docs/schema/generics-and-inheritance.mdx).
_Avoid_: "abstract node", "base class", "interface" (the docs compare a generic to these, but they
are not Infrahub terms).

**Attribute**:
A value stored directly on an object, such as a name, an IP address, or a flag. Each attribute has a
kind, such as `Text`, `IPHost`, or `Boolean`. Source: [Nodes &
attributes](../../docs/docs/schema/nodes-and-attributes.mdx).
_Avoid_: "field" (GraphQL uses "field" for both attributes and relationships), "property" (an
attribute has properties of its own, such as `value`, `source`, and `owner`).

**Relationship**:
A typed link between two nodes in the schema, and between their objects in the data. A relationship
has a cardinality (`one` or `many`) and a kind. Schema authors use the kinds `Generic`, `Attribute`,
`Component`, and `Parent`; Infrahub also defines `Group`, `Hierarchy`, `Profile`, and `Template`.
The kind controls how the relationship appears in the web interface. What happens on deletion
follows the relationship's `on_delete` value; when `on_delete` is not set, a `Component`
relationship cascades and every other kind does nothing. Sources:
[Relationships](../../docs/docs/schema/relationships.mdx),
[`constants/__init__.py`](../../backend/infrahub/core/constants/__init__.py) (`RelationshipKind`).
_Avoid_: "link", "reference", "foreign key", "edge" (an edge is an element of the graph database,
not of the schema).

**Peer**:
The other side of a relationship. In the schema, the `peer` property of a relationship names the
kind on the other side. In the data, the peer is the object on the other side, as in the `peer_id`
and `peer_kind` fields of relationship events. Sources:
[Relationships](../../docs/docs/schema/relationships.mdx),
[`node_action.py`](../../backend/infrahub/events/node_action.py).
_Avoid_: "related object" and "related node" (the OpsMill organization-wide writing instructions
name "peer" as the term to use; the web interface still uses "Related Nodes").

**Display label**:
A readable representation of one object, used in lists, selectors, breadcrumbs, and diffs. The
schema defines it on a node as a Jinja2 template in `display_label`. It is not an attribute: a
GraphQL query can return it as the `display_label` field, but cannot filter on it. Sources: [Display
labels](../../docs/docs/schema/display_label.mdx), [Computed
attributes](../../docs/docs/computed-attributes/overview.mdx).
_Avoid_: "label" alone (the schema `label` property names a kind, an attribute, or a relationship,
not an object), "name", `display_labels` (the list format that the schema still accepts but has
deprecated).

**Human-friendly identifier (HFID)**:
A set of attribute values that identifies one object uniquely, defined on a node in
`human_friendly_id`, for example the device name and interface name of an interface. It is used to
refer to an object across systems, including before the object exists in Infrahub. Each part is an
attribute of the node or a unique attribute of a mandatory relationship of cardinality one. The HFID
of an object is a list of strings, such as `["atl1-edge01", "Ethernet1"]`; it is a different value
from the object's `id`, which is a UUID string. Sources: [Nodes &
attributes](../../docs/docs/schema/nodes-and-attributes.mdx), [`node.py` in the Python
SDK](https://github.com/opsmill/infrahub-sdk-python/blob/stable/infrahub_sdk/node/node.py).
Not decided: the full name. The docs say "human-friendly identifier", and the [backend knowledge
page](backend/display-labels-and-hfid.md) says "human-friendly ID".
_Avoid_: "ID" alone (it names the UUID `id`, not the HFID), "display label" (not unique and not
meant to identify an object), "name".

**Computed attribute**:
A read-only `Text` or `URL` attribute whose value Infrahub calculates from other attributes and
relationships, using a Jinja2 template or a Python Transformation, and recalculates when that data
changes. Unlike a display label, it can be used as a query filter. Sources: [Computed
attributes](../../docs/docs/computed-attributes/overview.mdx), [backend knowledge
page](backend/computed-attributes.md).
_Avoid_: "derived attribute", "calculated field", "display label" (a different feature with a
different use).

## Data

**Object**:
One stored record of a node, holding values for the node's attributes and links to other objects
through its relationships, for example the device `core-router-01`. Source:
[Objects](../../docs/docs/objects/overview.mdx).
Not decided: whether to use "object" or "node" for this concept. See the entry for **node** for the
two positions and where the product uses each word.
_Avoid_: "instance" alone (also means an Infrahub installation), "entry", "item".

**Profile**:
An object that holds attribute and relationship values for many objects of one kind, or of every
node that inherits from one generic. An object that has a Profile assigned takes the Profile's
values unless the object sets its own value. When several Profiles apply, `profile_priority` decides
which value wins. Infrahub creates a Profile kind named `Profile<Namespace><Name>` for each node and
each generic that has `generate_profile` set, which is the default, except for kinds in the
namespaces that Infrahub reserves for itself, such as `Core` (the `Builtin` namespace does get
Profile kinds). Write "Profile" with a capital P. Sources:
[Profiles](../../docs/docs/profiles/overview.mdx), [style
guide](../../docs/docs/development/style-guide.mdx),
[`schema_branch.py`](../../backend/infrahub/core/schema/schema_branch.py).
_Avoid_: "profile" in lowercase for the feature, "default values" (the schema `default_value` is a
different feature), "object template" (a template sets structure for new objects; a Profile keeps
values in sync on existing objects).

**Object template**:
An object that defines the structure of new objects of one kind: attribute values, relationships,
and components such as the interfaces of a device model. A user selects a template when creating an
object, and Infrahub creates the object and its components from it. Changing a template later does
not change the objects created from it. Infrahub creates template kinds for nodes that have
`generate_template` set, which is off by default. Sources: [Object
Templates](../../docs/docs/object-templates/overview.mdx), [Key
concepts](../../docs/docs/overview/concepts.mdx).
Not decided: the capitalization. The docs use "Object Template", "object template", and "template";
the style guide does not list the term; the web interface menu says "Templates".
_Avoid_: "template" alone where it can mean a Jinja2 template (used by Transformations, display
labels, and computed attributes), "Profile".

**Group**:
An object that collects other objects, of any kinds, as its members. A group also has subscribers,
which are objects that react to changes in the group. Groups select the targets of Generators,
checks, and artifact definitions, and event rules can react to changes in group membership. Every
group kind inherits from `CoreGroup`. Sources: [Groups](../../docs/docs/groups/overview.mdx), [Key
concepts](../../docs/docs/overview/concepts.mdx).
_Avoid_: "collection", "tag" (`BuiltinTag` is a separate kind), "list".

**Resource Manager**:
The feature that allocates resources from pools when objects are created or updated. A **resource
pool** is the object that allocates them; the kinds are `CoreIPAddressPool`, `CoreIPPrefixPool`, and
`CoreNumberPool`. Sources: [Resource Manager](../../docs/docs/resource-manager/overview.mdx), [style
guide](../../docs/docs/development/style-guide.mdx).
Not decided: the plural. The style guide says to write "Resource Manager" in the singular only. The
Vale rules accept "Resource Managers", and the web interface menu says "Resource Managers".
_Avoid_: "IPAM" for the feature (IPAM is the IP address model that two of the pool kinds read from),
"allocator".

## Branches and change review

**Branch**:
A separate version of the data, the schema, and the artifacts, in which changes stay isolated until
they are merged. Every branch is created from the default branch and merges back into it. A branch
that has `sync_with_git` set is synchronized with the corresponding Git branches; a branch without
it changes only Infrahub data. Sources: [Branches](../../docs/docs/branches/overview.mdx), [Key
concepts](../../docs/docs/overview/concepts.mdx).
_Avoid_: "Git branch" for an Infrahub branch (the two are linked only when the branch syncs with
Git), "environment", "workspace".

**Default branch**:
The branch that every other branch is created from and merged into. Its name is `main` unless the
setting `INFRAHUB_INITIAL_DEFAULT_BRANCH` sets another name when Infrahub is first initialized.
Sources: [Branches](../../docs/docs/branches/overview.mdx),
[`config.py`](../../backend/infrahub/config.py).
_Avoid_: "main branch" and "main" (the name can be different), "production", "trunk".

**Branch-aware, branch-agnostic, and branch-local**:
How a node, attribute, or relationship behaves across branches. A branch-aware value changes only on
the branch where it is edited until a merge. A branch-agnostic value is stored once and is the same
on every branch. A branch-local value stays on its branch and is never merged. Sources:
[Branches](../../docs/docs/branches/overview.mdx), [Branch-agnostic
data](../../docs/docs/branches/branch-agnostic-data.mdx).
_Avoid_: "global" and "shared data" as separate terms for branch-agnostic, "local" alone.

**Diff**:
The differences between a branch and the default branch, which Infrahub calculates, stores, and
refreshes before a merge or a rebase. A proposed change shows four kinds of difference: data,
schema, files in repositories, and artifacts. Sources: [Proposed
changes](../../docs/docs/proposed-changes/overview.mdx),
[Rebase](../../docs/docs/branches/rebase.mdx).
_Avoid_: "changeset", "delta", "comparison".

**Conflict**:
A value that both the branch and the default branch changed after the branch was created or last
rebased. A user resolves a conflict by selecting which branch's value to keep. A
delete-versus-modify conflict, where one side deleted an object that the other changed, cannot be
resolved by a selection and blocks the merge until the data is updated. Sources: [Proposed
changes](../../docs/docs/proposed-changes/overview.mdx), [backend knowledge
page](backend/diff-conflicts.md).
_Avoid_: "merge conflict" as a Git term (an Infrahub conflict is on data, not on lines of a file).

**Rebase**:
The operation that updates a branch with the current state of the default branch: it moves the
branch's `branched_from` time forward, keeps the branch's own changes, and drops their history from
before the new `branched_from`. Infrahub refuses a rebase that would break a constraint. A conflict
on a property of an attribute (its value, owner, source, or another property) blocks the rebase
until it is resolved in favor of the branch or the data is updated so that both branches agree,
unless the default branch removed the attribute. Every other conflict (a removed attribute, a
relationship, a delete-versus-modify conflict) blocks the rebase until the data is updated so that
both branches agree. Sources: [Rebase](../../docs/docs/branches/rebase.mdx), [backend knowledge
page](backend/diff-conflicts.md), [`tasks.py`](../../backend/infrahub/core/branch/tasks.py).
_Avoid_: "sync" (Git synchronization is a different operation), "refresh" (refreshing a diff is one
step of a rebase), "pull".

**Merge**:
The operation that applies the changes of a branch to the default branch, through a proposed change
or directly from the branch. A merge either completes or is rolled back; an interrupted merge leaves
the branch in `MERGE_FAILED` until an administrator recovers it. For a branch that syncs with Git,
the merge also merges the linked Git branch. Source: [Merge](../../docs/docs/branches/merge.mdx).
_Avoid_: "promote" (used in the docs for moving Git changes between environments), "commit",
"apply".

**Proposed change**:
The review of a branch before it is merged into the default branch: reviewers view the diff, discuss
it, view the results of the checks, and approve it. The kind is `CoreProposedChange`. Its `state` is
`open`, `merging`, `merged`, `closed`, or `canceled`, and a separate `is_draft` flag marks a draft.
The lifecycle page describes the stages draft, open, approved, merged, and closed. Sources: [Key
concepts](../../docs/docs/overview/concepts.mdx), [Proposed
changes](../../docs/docs/proposed-changes/overview.mdx),
[Lifecycle](../../docs/docs/proposed-changes/lifecycle.mdx),
[`constants.py`](../../backend/infrahub/proposed_change/constants.py).
Not decided: the capitalization. Some docs pages write "Proposed Change" and others "proposed
change"; the style guide does not list the term; the kind label is "Proposed Change".
_Avoid_: "pull request", "PR", "merge request" (the docs compare a proposed change to a pull
request, but a pull request is a Git hosting feature), "change request".

## Git integration and automation

**Repository**:
A Git repository connected to Infrahub, from which Infrahub imports schemas, GraphQL queries,
Transformations, Generators, checks, and artifact definitions declared in its `.infrahub.yml` file.
There are two connection types. A **Repository** (`CoreRepository`) has read-write access: Infrahub
imports from the Git branch that matches each branch that syncs with Git, and a merge updates the
linked Git branch. A **Read-only Repository** (`CoreReadOnlyRepository`) follows one branch, tag, or
commit and imports only when a user requests it. Sources: [Git
integration](../../docs/docs/git-integration/overview.mdx), [Key
concepts](../../docs/docs/overview/concepts.mdx).
Not decided: the name and capitalization of the type. The docs write "Repository" and "Read-only
Repository"; the kind labels are "Repository", "Read-Only Repository", and "Git Repository"; the web
interface menu says "Git Repositories".
_Avoid_: "repo" (the Vale rules replace it with "repository"), "Git integration" for one repository
(Git integration is the feature).

**GraphQL query**:
A named GraphQL query stored in Infrahub (`CoreGraphQLQuery`), usually imported from a repository.
Transformations, Generators, checks, and artifact definitions use one to select their input data.
Sources: [Transformations](../../docs/docs/transformations/overview.mdx),
[Checks](../../docs/docs/checks/overview.mdx).
_Avoid_: "query" alone where it can mean any GraphQL request, "stored query".

**Transformation**:
User code, in Python or as a Jinja2 template, that converts the result of a GraphQL query into
another format, such as a device configuration in plain text or a JSON payload. The kinds are
`CoreTransformPython` and `CoreTransformJinja2`. Write "Transformation" with a capital T. Sources:
[Transformations](../../docs/docs/transformations/overview.mdx), [style
guide](../../docs/docs/development/style-guide.mdx).
Not decided: the noun "transform". The style guide says to never use "transform" as a noun, but the
kind labels are "Transform Python" and "Transform Jinja2", and the [Tasks
page](../../docs/docs/deploy-manage/run-observe/tasks.mdx) says "Transform functions".
_Avoid_: "transforms" as a noun, "template" alone (a Jinja2 Transformation is one kind of
Transformation), "Generator" (a Generator changes objects; a Transformation produces content).

**Artifact**:
The stored output of a Transformation for one target object, such as the configuration of one
device. An **artifact definition** (`CoreArtifactDefinition`) names the Transformation and the group
of target objects. On a proposed change, artifacts are generated on the source branch and are not
merged; after the merge, Infrahub generates them again on the default branch. Write "artifact" in
lowercase. Sources: [Artifacts](../../docs/docs/artifacts/overview.mdx), [Proposed
changes](../../docs/docs/proposed-changes/overview.mdx), [style
guide](../../docs/docs/development/style-guide.mdx).
_Avoid_: "rendered config", "output file", "Artifact" with a capital A mid-sentence.

**Generator**:
User Python code that reads data through a GraphQL query and creates, updates, and deletes objects
and relationships in Infrahub, for example the devices and networks of a site design. A **Generator
definition** (`CoreGeneratorDefinition`) names the code, the query, and the group of target objects.
A **Generator instance** (`CoreGeneratorInstance`) tracks one Generator definition for one target
object; each run for that target creates or updates it. Each run deletes the objects that an earlier
run saved and the current run did not save again. Write "Generator" with a capital G. Sources:
[Generators](../../docs/docs/generators/overview.mdx), [Key
concepts](../../docs/docs/overview/concepts.mdx), [style
guide](../../docs/docs/development/style-guide.mdx).
_Avoid_: "generator" in lowercase for the feature, "Transformation" (a Transformation produces
content and does not change objects), "script".

**Check**:
A validation that runs on a proposed change; a failed check blocks the merge. The merge ignores the
result of the Data Integrity check, but stops while a conflict has no branch selected or while a
delete-versus-modify conflict remains. Infrahub runs built-in checks, such as Data Integrity and
Schema Integrity, and user-defined checks: Python code from a repository, declared by a **check
definition** (`CoreCheckDefinition`), that validates the result of a GraphQL query. A targeted check
runs only against the members of a group. Sources: [Checks](../../docs/docs/checks/overview.mdx),
[Proposed changes](../../docs/docs/proposed-changes/overview.mdx).
_Avoid_: "validator" for a check (a validator is an object of a kind that inherits from the generic
`CoreValidator`, such as `CoreDataValidator` or `CoreUserValidator`, and holds the results of a set
of checks for one proposed change), "test", "CI job".

## Events and integrations

**Event**:
A structured record that Infrahub emits for an operation, such as `infrahub.node.created` or
`infrahub.group.member_added`. Events are used by the activity log, event rules, webhooks, and log
forwarding. Sources: [Events](../../docs/docs/events/overview.mdx), [backend knowledge
page](backend/events.md).
_Avoid_: "message" (the message bus carries internal messages, a different mechanism),
"notification", "activity" (the activity log is one consumer of events).

**Event rule and event action**:
An **event rule** (`CoreNodeTriggerRule` or `CoreGroupTriggerRule`) is an object that matches events
by conditions, such as a change to one attribute of one kind. An **event action** (`CoreGroupAction`
or `CoreGeneratorAction`) is an object that defines what happens when a rule that points to it
matches: add or remove group members, or run a Generator definition. The web interface menu calls
them "Rules" and "Actions". Sources: [Event rules](../../docs/docs/events/event-rules.mdx), [Event
actions](../../docs/docs/events/event-actions.mdx).
_Avoid_: "trigger" alone (the kinds are named `TriggerRule`, but the docs say "event rule"),
"automation" as the name of one rule.

**Webhook**:
An object that sends an HTTP request to an external endpoint when a matching event occurs. A
**standard webhook** (`CoreStandardWebhook`) sends the event information. A **custom webhook**
(`CoreCustomWebhook`) sends a payload that a Python Transformation creates from the event; Infrahub
reads the link to that Transformation from the default branch, and without one the webhook sends the
standard event payload. Sources: [Webhooks](../../docs/docs/webhooks/overview.mdx), [Webhook with
custom Transformation](../../docs/docs/webhooks/custom-transformation.mdx), [backend knowledge
page](backend/webhooks.md).
_Avoid_: "event action" (webhooks are configured separately from event rules and event actions),
"callback", "integration".

## Running work

**Task**:
One run of a background operation, such as rendering a Jinja2 template, running a check, or a Git
pull, that users view in the task list of the web interface. Each task is a Prefect flow run.
Sources: [Tasks](../../docs/docs/deploy-manage/run-observe/tasks.mdx), [backend knowledge
page](backend/async-tasks.md).
_Avoid_: "job", "workflow" (the code calls the definition of a flow a workflow), and, in backend
code, confusing a task with a Prefect `@task`, which is one step inside a flow.

**Task worker**:
The Python process that executes tasks. It takes flow runs from the task manager (Prefect) and runs
them. An installation can run several task workers to process more tasks at the same time. Sources:
[Architecture](../../docs/docs/overview/architecture.mdx), [backend knowledge
page](backend/task-workers.md).
_Avoid_: "Prefect worker" outside code about Prefect, "worker" alone where the API server workers
could be meant.

## Flagged ambiguities

- **"Node"** and **"object"**: the product uses both words for a stored record. See the entries for
  **node** and **object**.
- **"Template"**: can mean an object template, a Jinja2 Transformation, the Jinja2 template of a
  display label or computed attribute, or a template in a repository. Say which one.
- **"Check"**: can mean a built-in check of a proposed change or a user-defined check. In the code,
  a validator (a kind that inherits from `CoreValidator`) holds the results of a set of checks for
  one proposed change.
- **"Task"**: in the web interface and the GraphQL API, a task is a Prefect flow run; in backend
  code, `@task` marks a step inside a flow.
- **"Label"**: the schema `label` property names a kind, an attribute, or a relationship; the
  display label names one object.
- **"Sync"**: Git synchronization of a branch or a repository. Do not use it for a rebase.
- **"Instance"**: can mean an Infrahub installation, an object of a node, or a Generator instance.
  Say which one.
