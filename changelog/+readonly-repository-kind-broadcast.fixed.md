Fixed the read-only git repository add flow broadcasting the wrong repository kind, which caused peer workers to materialize the new repository as read-write instead of read-only.
