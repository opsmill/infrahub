---
label: Relationship
layout: default
order: 700
---


# Relationship

In a schema file, a relationship can be defined inside a `node` or inside a `node extension`.

Below is the list of all available options to define a Relationship in the schema

## Reference Guide
### name

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | name |
| **Kind** | `Text` |
| **Description** |  |
| **Optional** | False |
| **Default Value** |  |
| **Constraints** |  Regex: `^[a-z0-9\_]+$`<br> Length: min 3, max 32 |


### peer

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | peer |
| **Kind** | `Text` |
| **Description** |  |
| **Optional** | False |
| **Default Value** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 3, max 32 |


### kind

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | kind |
| **Kind** | `Text` |
| **Description** |  |
| **Optional** | False |
| **Default Value** | Generic |
| **Constraints** |  |
| **Accepted Values** | `Generic` `Attribute` `Component` `Parent` `Group`  |

### label

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | label |
| **Kind** | `Text` |
| **Description** |  |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 32 |


### description

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | description |
| **Kind** | `Text` |
| **Description** | Short description of the attribute. |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  Length: min -, max 128 |


### identifier

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | identifier |
| **Kind** | `Text` |
| **Description** |  |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  Regex: `^[a-z0-9\_]+$`<br> Length: min -, max 128 |


### cardinality

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | cardinality |
| **Kind** | `Text` |
| **Description** |  |
| **Optional** | False |
| **Default Value** |  |
| **Constraints** |  |
| **Accepted Values** | `one` `many`  |

### order_weight

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | order_weight |
| **Kind** | `Number` |
| **Description** |  |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  |


### optional

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | optional |
| **Kind** | `Boolean` |
| **Description** |  |
| **Optional** | True |
| **Default Value** | False |
| **Constraints** |  |


### branch

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Text` |
| **Description** |  |
| **Optional** | True |
| **Default Value** |  |
| **Constraints** |  |
| **Accepted Values** | `aware` `agnostic` `local`  |

### inherited

| Key | Value | { class="compact" }
| ---- | --------------- |
| **Name** | inherited |
| **Kind** | `Boolean` |
| **Description** |  |
| **Optional** | True |
| **Default Value** | False |
| **Constraints** |  |



## node

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | node |
| **Kind** | `Object` |
| **Description** |  |

