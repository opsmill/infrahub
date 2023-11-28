---
label: Object storage
layout: default
---
# Object storage

Infrahub provides an interface to store and retrieve files in an object storage. The object storage interface is independent of the branches.

Currently, Infrahub only supports a local backend. The goal over time is to support multiple backends, such as AWS S3, to allow users to select where they would like to store their files.

Currently the main interface to interact with the object storage is the REST API. 3 methods are supported:

- GET /api/storage/object/{identifier}
- POST /api/storage/upload/content
- POST /api/storage/upload/file

Please check the API documentation for more details.
