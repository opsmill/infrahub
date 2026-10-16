Fixed artifacts and generators not being regenerated after a change to a field that their query reads only inside a fragment on a generic, such as `... on InfraGenericDevice { name { value } }`.
