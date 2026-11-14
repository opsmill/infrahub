Creating or upserting a node now reads each peer named by its id once instead of once per constraint check, label computation and write, which cuts the database round trips of such a mutation in half
