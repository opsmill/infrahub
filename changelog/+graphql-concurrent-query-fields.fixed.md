Fixed GraphQL queries that request two or more custom root fields in one request, such as two `InfrahubResourcePoolUtilization` fields, failing with a database read error or hanging.
