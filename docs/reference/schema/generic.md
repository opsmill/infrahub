<!-- vale off -->
---
label: Generic
layout: default
order: 600
---

# Generic

Below is the list of all available options to define a Generic in the schema

## name

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | name |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Length: min 3, max 3 |


## peer

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | peer |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 3, max 3 |


## kind

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | kind |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  |
| **Accepted Values** | `Generic` `Attribute` `Component` `Parent` `Group`  |

## label

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | label |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Length: min -, max - |


## description

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | description |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Length: min -, max - |


## identifier

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | identifier |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Length: min -, max - |


## cardinality

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | cardinality |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  |
| **Accepted Values** | `one` `many`  |

## order_weight

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | order_weight |
| **Kind** | `Number` |
| **Description** |  |
| **Constraints** |  |


## optional

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | optional |
| **Kind** | `Boolean` |
| **Description** |  |
| **Constraints** |  |


## branch

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | branch |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  |
| **Accepted Values** | `aware` `agnostic` `local`  |

## inherited

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | inherited |
| **Kind** | `Boolean` |
| **Description** |  |
| **Constraints** |  |



## node

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | node |
| **Kind** | `Object` |
| **Description** |  |

