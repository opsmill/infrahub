Update uniqueness checks/constraints logic to consider NULL values instead of ignoring.
This might cause data integrity issues if you have nodes with NULL values for attributes that are part of their
schema's uniqueness constraints. This change includes a database migration that validates data integrity using
the new uniqueness check/constraint logic and will fail if any uniqueness issues exist.