# Schema

## Node, Attributes and Relationships

| Name | Description | Kind | Constraints |
| -- | -- | -- | -- | -- |
| name | Node name, must be unique and must be a all lowercase. The name is used to generate the name of the queries and the mutation in GraphQL | String |  Regex: `^[a-z0-9\_]+$`<br> Lenght: min 3, max 3 |
| kind | Node kind, must be unique and must be in CamelCase | String |  Regex: `^[A-Z][a-zA-Z0-9]+$`<br> Lenght: min 3, max 3 |
| label | Human friendly representation of the name/kind | String | <br> Lenght: min -, max - |
| description |  | String | <br> Lenght: min -, max - |
| branch |  | Boolean |  |
| default_filter | Default filter used to search for a node in addition to its ID. | String |  |
| display_label | List of attributes to use to generate the display label | List |  |
| inherit_from | List of Generic Kind that this node is inheriting from | List |  |
| groups | List of Group that this node is part of | List |  |


### Attribute Kind


### Relationship Kind

## Generics & Groups
