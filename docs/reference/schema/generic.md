---
label: Generic
layout: default
order: 600
---
<!-- vale off -->



# Generic

## Summary

Below is the list of all available options to define a Generic in the schema

| Name | Type | Description | Mandatory | { class="compact" }
| ---- | ---- | ---- | --------- |
| [**branch**](#branch) | Attribute | Type of branch support for the model. | False |
| [**default_filter**](#default_filter) | Attribute | Default filter used to search for a node in addition to its ID. | False |
| [**description**](#description) | Attribute | Short description of the Generic. | False |
| [**display_labels**](#display_labels) | Attribute | List of attributes to use to generate the display label | False |
| [**icon**](#icon) | Attribute | Defines the icon to be used for this object type. | False |
| [**include_in_menu**](#include_in_menu) | Attribute | Defines if objects of this kind should be included in the menu. | False |
| [**label**](#label) | Attribute | Human friendly representation of the name/kind | False |
| [**menu_placement**](#menu_placement) | Attribute | Defines where in the menu this object should be placed. | False |
| [**name**](#name) | Attribute | Generic name, must be unique within a namespace and must start with an uppercase letter. | True |
| [**namespace**](#namespace) | Attribute | Generic Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions. | True |
| [**order_by**](#order_by) | Attribute | List of attributes to use to order the results by default | False |
| [**used_by**](#used_by) | Attribute | List of Nodes that are referencing this Generic | False |
| [**attributes**](#attributes) | Relationship |  | False |
| [**relationships**](#relationships) | Relationship |  | False |

## Reference Guide
### branch

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Text` |
| **Description** | Type of branch support for the model. |
| **Optional** | True |
| **Default Value** | aware |
| **Constraints** |  |
| **Accepted Values** | `aware` `agnostic` `local`  |

### default_filter

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | default_filter |
| **Kind** | `Text` |
| **Description** | Default filter used to search for a node in addition to its ID. |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  Regex: `^[a-z0-9\_]+$` |


### description

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | description |
| **Kind** | `Text` |
| **Description** | Short description of the Generic. |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 128 |


### display_labels

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | display_labels |
| **Kind** | `List` |
| **Description** | List of attributes to use to generate the display label |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  |


### icon

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | icon |
| **Kind** | `Text` |
| **Description** | Defines the icon to be used for this object type. |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  |


### include_in_menu

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | include_in_menu |
| **Kind** | `Boolean` |
| **Description** | Defines if objects of this kind should be included in the menu. |
| **Optional** | True |
| **Default Value** | True |
| **Constraints** |  |


### label

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | label |
| **Kind** | `Text` |
| **Description** | Human friendly representation of the name/kind |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 32 |


### menu_placement

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | menu_placement |
| **Kind** | `Text` |
| **Description** | Defines where in the menu this object should be placed. |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  |


### name

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | name |
| **Kind** | `Text` |
| **Description** | Generic name, must be unique within a namespace and must start with an uppercase letter. |
| **Optional** | False |
| **Default Value** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 2, max 32 |


### namespace

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | namespace |
| **Kind** | `Text` |
| **Description** | Generic Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions. |
| **Optional** | False |
| **Default Value** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 3, max 32 |


### order_by

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | order_by |
| **Kind** | `List` |
| **Description** | List of attributes to use to order the results by default |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  |


### used_by

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | used_by |
| **Kind** | `List` |
| **Description** | List of Nodes that are referencing this Generic |
| **Optional** | True |
| **Default Value** |  |
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

