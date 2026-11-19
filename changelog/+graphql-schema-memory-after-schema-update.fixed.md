Fixed Infrahub processes that run GraphQL queries keeping earlier versions of the GraphQL schema in memory after schema changes, which increased their memory use with each schema update.
