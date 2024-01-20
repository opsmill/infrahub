---
label: Messages
icon: mail
layout: default
---
# Infrahub Messages

## check.artifact.create

Runs a check to verify the creation of an artifact.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
artifact_name | string | Name of the artifact | True |
artifact_definition | string | The the ID of the artifact definition | True |
commit | string | The commit to target | True |
content_type | string | Content type of the artifact | True |
transform_type | string | The type of transform associated with this artifact | True |
transform_location | string | The transforms location within the repository | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the Repository | True |
repository_kind | string | The kind of the Repository | True |
branch_name | string | The branch where the check is run | True |
target_id | string | The ID of the target object for this artifact | True |
target_name | string | Name of the artifact target | True |
artifact_id |  | The id of the artifact if it previously existed | False |
query | string | The name of the query to use when collecting data | True |
rebase | boolean | Indicates if a rebase should be done | True |
timeout | integer | Timeout for requests used to generate this artifact | True |
variables | object | Input variables when generating the artifact | True |
validator_id | string | The ID of the validator | True |


## check.repository.check_definition

Triggers user defined checks to run based on a Check Definition.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
check_definition_id | string | The unique ID of the check definition | True |
commit | string | The commit to target | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the Repository | True |
branch_name | string | The branch where the check is run | True |
file_path | string | The path and filename of the check | True |
class_name | string | The name of the class containing the check | True |
proposed_change | string | The unique ID of the Proposed Change | True |


## check.repository.merge_conflicts

Runs a check to validate if there are merge conflicts for a proposed change between two branches.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
validator_id | string | The id of the validator associated with this check | True |
validator_execution_id | string | The id of current execution of the associated validator | True |
check_execution_id | string | The unique ID for the current execution of this check | True |
proposed_change | string | The unique ID of the Proposed Change | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the Repository | True |
source_branch | string | The source branch | True |
target_branch | string | The target branch | True |


## check.repository.user_check

Runs a check as defined within a CoreCheckDefinition within a repository.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
validator_id | string | The id of the validator associated with this check | True |
validator_execution_id | string | The id of current execution of the associated validator | True |
check_execution_id | string | The unique ID for the current execution of this check | True |
check_definition_id | string | The unique ID of the check definition | True |
commit | string | The commit to target | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the Repository | True |
branch_name | string | The branch where the check is run | True |
file_path | string | The path and filename of the check | True |
class_name | string | The name of the class containing the check | True |
proposed_change | string | The unique ID of the Proposed Change | True |
variables | object | Input variables when running the check | False |
name | string | The name of the check | True |


## event.branch.create

Sent when a new branch is created.

Priority: HIGEST (5)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The branch that was created | True |
branch_id | string | The unique ID of the branch | True |
data_only | boolean | Indicates if this is a data only branch, or repositories can be tied to it. | True |


## event.branch.delete

Sent when a branch has been deleted.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The branch that was deleted | True |
branch_id | string | The unique ID of the branch | True |
data_only | boolean | Indicates if this is a data only branch, or repositories can be tied to it. | True |


## event.branch.merge

Sent when a branch has been merged.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
source_branch | string | The source branch | True |
target_branch | string | The target branch | True |


## event.node.mutated

Sent when a node has been mutated

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The branch that was created | True |
kind | string | The type of object modified | True |
node_id | string | The ID of the mutated node | True |
action | string | The action taken on the node | True |
data | object | Data on modified object | True |


## event.schema.update

Sent when the schema on a branch has been updated.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The branch where the update occured | True |


## event.worker.new_primary_api

Sent on startup or when a new primary API worker is elected.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
worker_id | string | The worker ID that got elected | True |


## finalize.validator.execution

Update the status of a validator after all checks have been completed.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
validator_id | string | The id of the validator associated with this check | True |
validator_execution_id | string | The id of current execution of the associated validator | True |
start_time | string | Start time when the message was first created | True |
validator_type | string | The type of validator to complete | True |


## git.branch.create

Create a branch in a Git repository.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | Name of the branch to create | True |
branch_id | string | The unique ID of the branch | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the Repository | True |


## git.diff.names_only

Request a list of modified files between two commits.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
repository_kind | string | The kind of the repository | True |
first_commit | string | The first commit | True |
second_commit | string | The second commit | True |


## git.file.get

Read a file from a Git repository.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
commit | string | The commit id to use to access the file | True |
file | string | The path and filename within the repository | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
repository_kind | string | The kind of the repository | True |


## git.repository.add

Clone and sync an external repository after creation.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
location | string | The external URL of the repository | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
default_branch_name |  | Default branch for this repository | False |


## git.repository.add_read_only

Clone and sync an external repository after creation.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
location | string | The external URL of the repository | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
ref | string | Ref to track on the external repository | True |
infrahub_branch_name | string | Infrahub branch on which to sync the remote repository | True |


## git.repository.merge

Merge one branch into another.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
source_branch | string | The source branch | True |
destination_branch | string | The source branch | True |


## git.repository.pull_read_only

Update a read-only repository to the latest commit for its ref

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
location | string | The external URL of the repository | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
ref |  | Ref to track on the external repository | False |
commit |  | Specific commit to pull | False |
infrahub_branch_name | string | Infrahub branch on which to sync the remote repository | True |


## refresh.registry.branches

Sent to indicate that the registry should be refreshed and new branch data loaded.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |


## refresh.webhook.configuration

Sent to indicate that configuration in the cache for webhooks should be refreshed.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |


## request.artifact.generate

Runs to generate an artifact

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
artifact_name | string | Name of the artifact | True |
artifact_definition | string | The the ID of the artifact definition | True |
commit | string | The commit to target | True |
content_type | string | Content type of the artifact | True |
transform_type | string | The type of transform associated with this artifact | True |
transform_location | string | The transforms location within the repository | True |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the Repository | True |
repository_kind | string | The kind of the Repository | True |
branch_name | string | The branch where the check is run | True |
target_id | string | The ID of the target object for this artifact | True |
target_name | string | Name of the artifact target | True |
artifact_id |  | The id of the artifact if it previously existed | False |
query | string | The name of the query to use when collecting data | True |
rebase | boolean | Indicates if a rebase should be done | True |
timeout | integer | Timeout for requests used to generate this artifact | True |
variables | object | Input variables when generating the artifact | True |


## request.artifact_definition.check

Sent to validate the generation of artifacts in relation to a proposed change.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
artifact_definition | string | The unique ID of the Artifact Definition | True |
proposed_change | string | The unique ID of the Proposed Change | True |
source_branch | string | The source branch | True |
target_branch | string | The target branch | True |


## request.artifact_definition.generate

Sent to trigger the generation of artifacts for a given branch.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
artifact_definition | string | The unique ID of the Artifact Definition | True |
branch | string | The branch to target | True |
limit | array | List of targets to limit the scope of the generation, if populated only the included artifacts will be regenerated | False |


## request.git.create_branch

Sent to trigger the creation of a branch in git repositories.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The branch to target | True |
branch_id | string | The unique ID of the branch | True |


## request.git.sync

Request remote repositories to be synced.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |


## request.graphql_query_group.update

Sent to create or update a GraphQLQueryGroup associated with a given GraphQLQuery.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The branch to target | True |
query_name | string | The name of the GraphQLQuery that should be associated with the group | True |
query_id | string | The ID of the GraphQLQuery that should be associated with the group | True |
related_node_ids | array | List of nodes related to the GraphQLQuery | True |
subscribers | array | List of subscribers to add to the group | True |
params | object | Params sent with the query | True |


## request.proposed_change.cancel

Cancel the proposed change

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
proposed_change | string | The unique ID of the Proposed Change | True |


## request.proposed_change.data_integrity

Sent trigger data integrity checks for a proposed change

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
proposed_change | string | The unique ID of the Proposed Change | True |


## request.proposed_change.refresh_artifacts

Sent trigger the refresh of artifacts that are impacted by the proposed change.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
proposed_change | string | The unique ID of the Proposed Change | True |


## request.proposed_change.repository_checks

Sent when a proposed change is created to trigger additional checks

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
proposed_change | string | The unique ID of the Proposed Change | True |


## request.proposed_change.schema_integrity

Sent trigger schema integrity checks for a proposed change

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
proposed_change | string | The unique ID of the Proposed Change | True |


## request.repository.checks

Sent to trigger the checks for a repository to be executed.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
proposed_change | string | The unique ID of the Proposed Change | True |
repository | string | The unique ID of the Repository | True |
source_branch | string | The source branch | True |
target_branch | string | The target branch | True |


## request.repository.user_checks

Sent to trigger the user defined checks on a repository.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
proposed_change | string | The unique ID of the Proposed Change | True |
repository | string | The unique ID of the Repository | True |
source_branch | string | The source branch | True |
target_branch | string | The target branch | True |


## send.webhook.event

Sent a webhook to an external source.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
webhook_id | string | The unique ID of the webhook | True |
event_type | string | The event type | True |
event_data | object | The data tied to the event | True |


## transform.jinja.template

Sent to trigger the checks for a repository to be executed.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
repository_kind | string | The kind of the repository | True |
data | object | Input data for the template | True |
branch | string | The branch to target | True |
template_location | string | Location of the template within the repository | True |
commit | string | The commit id to use when rendering the template | True |


## transform.python.data

Sent to run a Python transform.

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
repository_id | string | The unique ID of the Repository | True |
repository_name | string | The name of the repository | True |
repository_kind | string | The kind of the repository | True |
data | object | Input data for the template | True |
branch | string | The branch to target | True |
transform_location | string | Location of the transform within the repository | True |
commit | string | The commit id to use when rendering the template | True |


## trigger.artifact_definition.generate

Sent after a branch has been merged to start the regeneration of artifacts

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The impacted branch | True |


## trigger.proposed_change.cancel

Triggers request to cancel any open or closed proposed changes for a given branch

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
branch | string | The impacted branch | True |


## trigger.webhook.actions

Triggers webhooks to be sent for the given action

Priority: NORMAL (3)

| Property | Type | Description | Mandatory | { class="compact" }
| -------- | ---- | ----------- | --------- |
event_type | string | The event type | True |
event_data | object | The webhook payload | True |

