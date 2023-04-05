---
label: Node
layout: default
order: 900
---

# Node

Below is the list of all available options to define a node in the schema
## name

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | name |
| **Kind** | `Text` |
| **Description** | Node name, must be unique and must be a all lowercase. |
| **Constraints** |  Regex: `^[a-z0-9\_]+$`<br> Lenght: min 3, max 3 |


## kind

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | kind |
| **Kind** | `Text` |
| **Description** | Node kind, must be unique and must be in CamelCase |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Lenght: min 3, max 3 |


## label

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | label |
| **Kind** | `Text` |
| **Description** | Human friendly representation of the name/kind |
| **Constraints** | <br> Lenght: min -, max - |


## description

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | description |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Lenght: min -, max - |


## branch

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Boolean` |
| **Description** |  |
| **Constraints** |  |


## default_filter

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | default_filter |
| **Kind** | `Text` |
| **Description** | Default filter used to search for a node in addition to its ID. |
| **Constraints** |  |


## display_labels

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | display_labels |
| **Kind** | `List` |
| **Description** | List of attributes to use to generate the display label |
| **Constraints** |  |


## inherit_from

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | inherit_from |
| **Kind** | `List` |
| **Description** | List of Generic Kind that this node is inheriting from |
| **Constraints** |  |


## groups

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | groups |
| **Kind** | `List` |
| **Description** | List of Group that this node is part of |
| **Constraints** |  |



## attributes

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | attributes |
| **Kind** | `List` |
| **Description** |  |

## relationships

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | relationships |
| **Kind** | `List` |
| **Description** |  |

