Updating a node no longer reads its stored relationship peers while working out which locks to take, removing one query per relationship in the payload from every update and upsert.
