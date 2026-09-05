Bounded the memory used when validating composite uniqueness constraints, so a branch merge or rebase no longer risks exhausting Neo4j transaction memory when many nodes share a relationship peer.
