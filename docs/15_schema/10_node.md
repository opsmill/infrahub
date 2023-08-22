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
| **Description** | Node name, must be unique and must be all lowercase. |
| **Constraints** | <br> Length: min 2, max 2 |


## namespace

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | namespace |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 3, max 3 |


## label

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | label |
| **Kind** | `Text` |
| **Description** | Human friendly representation of the name/kind |
| **Constraints** | <br> Length: min -, max - |


## description

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | description |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Length: min -, max - |


## branch

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  |
| **Accepted Values** | `aware` `agnostic`  |

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


## order_by

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | order_by |
| **Kind** | `List` |
| **Description** | List of attributes to use to order the results by default |
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

