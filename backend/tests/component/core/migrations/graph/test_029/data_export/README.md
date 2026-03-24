# Test Data Export

Various bad data states that can have occurred after merging a branch that included an update to a schema's name, namespace, or inheritance

- duplicated nodes: multiple Node vertices with the same UUID and database labels
- duplicated edges: edges with the exact same data linking the same two vertices
- duplicated Relationships: duplicated Relationship vertices with duplicated IS_RELATED edges linking the same two peer vertices
