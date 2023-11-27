---
label: Node
layout: default
order: 900
---


# Node

## Summary

Below is the list of all available options to define a Node in the schema

| Name | Type | Optional | { class="compact" }
| ---- | ---- | --------- |
| [**name**](#name) | Node name, must be unique within a namespace and must be all lowercase. | False |
| [**namespace**](#namespace) | Node Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions. | False |
| [**label**](#label) | Human friendly representation of the name/kind | True |
| [**description**](#description) | Short description of the model, will be visible in the frontend. | True |
| [**branch**](#branch) | Type of branch support for the model. | True |
| [**default_filter**](#default_filter) | Default filter used to search for a node in addition to its ID. | True |
| [**display_labels**](#display_labels) | List of attributes to use to generate the display label | True |
| [**include_in_menu**](#include_in_menu) | Defines if objects of this kind should be included in the menu. | True |
| [**menu_placement**](#menu_placement) | Defines where in the menu this object should be placed. | True |
| [**icon**](#icon) | Defines the icon to be used for this object type. | True |
| [**order_by**](#order_by) | List of attributes to use to order the results by default | True |
| [**inherit_from**](#inherit_from) | List of Generic Kind that this node is inheriting from | True |
| [**groups**](#groups) | List of Group that this node is part of | True |

## Reference Guide
### name

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | name |
| **Kind** | `Text` |
| **Description** | Node name, must be unique within a namespace and must be all lowercase. |
| **Optional**  | False |
| **Default Value** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 2, max 32 |


### namespace

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | namespace |
| **Kind** | `Text` |
| **Description** | Node Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions. |
| **Optional**  | False |
| **Default Value** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 3, max 32 |


### label

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | label |
| **Kind** | `Text` |
| **Description** | Human friendly representation of the name/kind |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 32 |


### description

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | description |
| **Kind** | `Text` |
| **Description** | Short description of the model, will be visible in the frontend. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 128 |


### branch

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Text` |
| **Description** | Type of branch support for the model. |
| **Optional**  | True |
| **Default Value** | aware |
| **Constraints** |  |
| **Accepted Values** | `aware` `agnostic` `local`  |

### default_filter

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | default_filter |
| **Kind** | `Text` |
| **Description** | Default filter used to search for a node in addition to its ID. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  Regex: `^[a-z0-9\_]+$` |


### display_labels

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | display_labels |
| **Kind** | `List` |
| **Description** | List of attributes to use to generate the display label |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### include_in_menu

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | include_in_menu |
| **Kind** | `Boolean` |
| **Description** | Defines if objects of this kind should be included in the menu. |
| **Optional**  | True |
| **Default Value** | True |
| **Constraints** |  |


### menu_placement

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | menu_placement |
| **Kind** | `Text` |
| **Description** | Defines where in the menu this object should be placed. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### icon

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | icon |
| **Kind** | `Text` |
| **Description** | Defines the icon to be used for this object type. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### order_by

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | order_by |
| **Kind** | `List` |
| **Description** | List of attributes to use to order the results by default |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### inherit_from

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | inherit_from |
| **Kind** | `List` |
| **Description** | List of Generic Kind that this node is inheriting from |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### groups

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | groups |
| **Kind** | `List` |
| **Description** | List of Group that this node is part of |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |



## attributes

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | attributes |
| **Kind** | `List` |
| **Description** |  |

## relationships

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | relationships |
| **Kind** | `List` |
| **Description** |  |

