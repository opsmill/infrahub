from neo4j.exceptions import Neo4jError

from infrahub.exceptions import DatabaseError, QueryError, QueryTimeoutError

RECORD_WRITE_ERRORS = (DatabaseError, QueryError, QueryTimeoutError, Neo4jError)
"""The errors that a write of a schema change record raises, which the caller logs without failing the schema update."""
