# Product terminology

Use the same terms a reader sees in the product, the CLI, and the API. Consistent terminology connects the page to the feature they already know, and makes it findable by search.

Adapted from the release-notes skill's rule of the same name, which is the authoritative copy — check there when adding a term.

## Capitalise named Infrahub concepts

- Proposed Change / Proposed Changes
- Generator / Generators
- Transformation / Transformations
- Python Transformation
- Jinja2 Transformation
- Object Template / Object Templates
- Profile / Profiles
- Resource Manager

## Keep descriptive terms lowercase

- linked repository
- computed attribute
- artifact
- webhook delivery
- default branch
- source branch
- object file

## Preserve standard capitalisation

Infrahub, Git, GraphQL, IPAM, API, SDK, UI, Python, Jinja2, Neo4j, OpenAPI.

## Terms where a synonym changes the meaning

A few are worth getting exactly right, because the generic word means something broader:

- **linked repository** is the Infrahub concept, not any Git repository.
- **Transformation** names the Infrahub feature and its definition, not transformation in general.
- **Proposed Change** names the Infrahub workflow and the object in the UI, not a proposed change in the ordinary sense.

Code identifiers, YAML keys, file paths, environment variables, error codes, and commands keep their literal spelling — do not adjust their case to match prose style.

## Prefer the product's own verb

If the tool is called Sync, the verb is "sync". Do not reach for a synonym to avoid repeating the name: "keep Infrahub in sync" is clear, "keep Infrahub aligned" is not. Repeating the product's vocabulary teaches it to the reader.

## Check terminology at the end

Terminology drifts during rewriting, particularly when a sentence is reworded for rhythm. Include a terminology pass in the pre-PR audit, and confirm the spelling of identifiers against the source rather than from memory.
