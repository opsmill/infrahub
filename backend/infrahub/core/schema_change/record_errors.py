from neo4j.exceptions import Neo4jError

from infrahub.exceptions import DatabaseError, QueryError, QueryTimeoutError

RECORD_WRITE_ERRORS = (DatabaseError, QueryError, QueryTimeoutError, Neo4jError)
"""The errors that a schema change record write raises after its retries, which a best-effort write logs."""
