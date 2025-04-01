Fix an issue where optional unique attributes having a NULL value could be duplicated.
Upgrading infrahub to a version containing this fix will perform a check identifying such duplicates.
If some duplicates are found, data or schema should be fixed in order to complete the upgrade: 
- Either the uniqueness constraint on corresponding attributes should be removed within schema.
- Or duplicated unique attributes values should be modified.
