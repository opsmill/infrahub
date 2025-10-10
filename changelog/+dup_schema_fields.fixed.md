Fix a bug that allowed duplicate attributes and/or relationships on Node or Generic schemas to be merged into the default branch,
which would cause the application and workers to crash with an error message similar to the following:
```
ValueError: SchemaName: Names of attributes and relationships must be unique : ['field_name_1', 'field_name_2']
```
Added a new CLI command `infrahub db check-duplicate-schema-fields` to resolve this duplicated schema fields issue if it appears.