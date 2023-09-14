---
label: Object Storage
layout: default
order: 500
---

Infrahub provides an interface to easily store and retrieve files in an object storage. The object storage interface is independent of the branches.

Currently only a local backend is supported but the goal over time is to support multiple backend like AWS S3 to allow users to select where they would like their files to be stored.

Currently the main interface to interact with the object storage is the REST API, 3 methods are supported

- GET /api/storage/object/{identifier}
- POST /api/storage/upload/content
- POST /api/storage/upload/file

Please check the API documentation for more details
