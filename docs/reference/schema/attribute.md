---
label: Attribute
layout: default
order: 800
---


# Attribute

In a schema file, an attribute can be defined inside a `node`, a `generic` or a `node extension`.

## Summary

Below is the list of all available options to define an Attribute in the schema

| Name | Type | Optional | { class="compact" }
| ---- | ---- | --------- |
| [**name**](#name) | Attribute name, must be unique within a model and must be all lowercase. | False |
| [**kind**](#kind) | Defines the type of the attribute. | False |
| [**enum**](#enum) | Define a list of valid values for the attribute. | True |
| [**choices**](#choices) | Define a list of valid choices for a dropdown attribute. | True |
| [**regex**](#regex) | Regex uses to limit limit the characters allowed in for the attributes. | True |
| [**max_length**](#max_length) | Set a maximum number of characters allowed for a given attribute. | True |
| [**min_length**](#min_length) | Set a minimum number of characters allowed for a given attribute. | True |
| [**label**](#label) | Human friendly representation of the name | True |
| [**description**](#description) | Short description of the aattribute. | True |
| [**read_only**](#read_only) | Set the attribute as Read-Only, users won't be able to change its value. | True |
| [**unique**](#unique) | Indicate if the value of this attribute but be unique in the database for a given model. | True |
| [**optional**](#optional) | Indicate this attribute is mandatory or it is optional. | True |
| [**branch**](#branch) | Type of branch support for the attribute, if not defined it will be inherited from the node. | True |
| [**order_weight**](#order_weight) | Number used to order the attribute in the frontend (table and view). | True |
| [**default_value**](#default_value) | Default value of the attribute. | True |

## Example

```yaml
nodes:
  - name: Rack
    attributes:
      - name: name
        kind: Text
        unique: True
        description: Unique identifier for the rack
extensions:
  nodes:
    - kind: CoreProposedChange
      attribute:
        - name: ticket_id
            kind: Text
            unique: True
            optional: False
            description: Internal Ticket ID from Service Now
```

## Reference Guide

### name

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | name |
| **Kind** | `Text` |
| **Description** | Attribute name, must be unique within a model and must be all lowercase. |
| **Optional**  | False |
| **Default Value** |  |
| **Constraints** |  Regex: `^[a-z0-9\_]+$`<br> Length: min 3, max 32 |


### kind

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | kind |
| **Kind** | `Text` |
| **Description** | Defines the type of the attribute. |
| **Optional**  | False |
| **Default Value** |  |
| **Constraints** |  Length: min 3, max 32 |
| **Accepted Values** | `ID` `Dropdown` `Text` `TextArea` `DateTime` `Email` `Password` `HashedPassword` `URL` `File` `MacAddress` `Color` `Number` `Bandwidth` `IPHost` `IPNetwork` `Checkbox` `List` `JSON` `Any` `String` `Integer` `Boolean`  |

### enum

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | enum |
| **Kind** | `List` |
| **Description** | Define a list of valid values for the attribute. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### choices

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | choices |
| **Kind** | `List` |
| **Description** | Define a list of valid choices for a dropdown attribute. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### regex

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | regex |
| **Kind** | `Text` |
| **Description** | Regex uses to limit limit the characters allowed in for the attributes. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### max_length

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | max_length |
| **Kind** | `Number` |
| **Description** | Set a maximum number of characters allowed for a given attribute. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### min_length

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | min_length |
| **Kind** | `Number` |
| **Description** | Set a minimum number of characters allowed for a given attribute. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### label

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | label |
| **Kind** | `Text` |
| **Description** | Human friendly representation of the name |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 32 |


### description

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | description |
| **Kind** | `Text` |
| **Description** | Short description of the aattribute. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 128 |


### read_only

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | read_only |
| **Kind** | `Boolean` |
| **Description** | Set the attribute as Read-Only, users won't be able to change its value. |
| **Optional**  | True |
| **Default Value** | False |
| **Constraints** |  |


### unique

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | unique |
| **Kind** | `Boolean` |
| **Description** | Indicate if the value of this attribute but be unique in the database for a given model. |
| **Optional**  | True |
| **Default Value** | False |
| **Constraints** |  |


### optional

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | optional |
| **Kind** | `Boolean` |
| **Description** | Indicate this attribute is mandatory or it is optional. |
| **Optional**  | True |
| **Default Value** | True |
| **Constraints** |  |


### branch

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Text` |
| **Description** | Type of branch support for the attribute, if not defined it will be inherited from the node. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |
| **Accepted Values** | `aware` `agnostic` `local`  |

### order_weight

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | order_weight |
| **Kind** | `Number` |
| **Description** | Number used to order the attribute in the frontend (table and view). |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |


### default_value

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | default_value |
| **Kind** | `Any` |
| **Description** | Default value of the attribute. |
| **Optional**  | True |
| **Default Value** |  |
| **Constraints** |  |




