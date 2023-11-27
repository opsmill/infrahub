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
| **Description** | Node name, must be unique within a namespace and must be all lowercase. |
| **Constraints** |  Regex: `^[a-z0-9\_]+$`<br> Length: min 2, max 2 |


## namespace

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | namespace |
| **Kind** | `Text` |
| **Description** | Node Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions. |
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
| **Description** | Short description of the model, will be visible in the frontend. |
| **Constraints** | <br> Length: min -, max - |


## branch

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Text` |
| **Description** | Type of branch support for the model. |
| **Constraints** |  |
| **Accepted Values** | `aware` `agnostic` `local`  |

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


## include_in_menu

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | include_in_menu |
| **Kind** | `Boolean` |
| **Description** | Defines if objects of this kind should be included in the menu. |
| **Constraints** |  |


## menu_placement

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | menu_placement |
| **Kind** | `Text` |
| **Description** | Defines where in the menu this object should be placed. |
| **Constraints** |  |


## icon

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | icon |
| **Kind** | `Text` |
| **Description** | Defines the icon to be used for this object type. |
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

