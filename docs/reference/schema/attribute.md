---
label: Attribute
layout: default
order: 800
---

# Attribute

In a schema file, an attribute can be defined inside a `node` or inside a `node extension`.

Below is the list of all available options to define an Attribute in the schema
## name

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | name |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Length: min 3, max 3 |


## namespace

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | namespace |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Length: min 3, max 3 |


## kind

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | kind |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** | <br> Length: min 3, max 3 |
| **Accepted Values** | `ID` `Text` `TextArea` `DateTime` `Email` `Password` `HashedPassword` `URL` `File` `MacAddress` `Color` `Number` `Bandwidth` `IPHost` `IPNetwork` `Checkbox` `List` `JSON` `Any` `String` `Integer` `Boolean`  |

## enum

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | enum |
| **Kind** | `List` |
| **Description** |  |
| **Constraints** |  |


## regex

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | regex |
| **Kind** | `Text` |
| **Description** |  |
| **Constraints** |  |


## max_length

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | max_length |
| **Kind** | `Number` |
| **Description** |  |
| **Constraints** |  |


## min_length

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | min_length |
| **Kind** | `Number` |
| **Description** |  |
| **Constraints** |  |


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


## unique

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | unique |
| **Kind** | `Boolean` |
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

## order_weight

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | order_weight |
| **Kind** | `Number` |
| **Description** |  |
| **Constraints** |  |


## default_value

| -- | -- | { class="compact" }
| ---- | --------------- |
| **Name** | default_value |
| **Kind** | `Any` |
| **Description** |  |
| **Constraints** |  |


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

