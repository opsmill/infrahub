Several built-in `Core` generic schemas that have special handling in Infrahub now restrict inheritance to the `Core` namespace via the `restricted_namespaces` field. This prevents user-defined schemas from inheriting from generics whose code paths assume a specific internal structure.

**Breaking change.** Any user-defined node schema that inherits from one of the generics listed below must be removed (and its data deleted) before upgrading. Infrahub will refuse to load a schema that violates these restrictions and the upgrade will not complete.

The newly restricted generics are:

- `CoreCredential`
- `CoreGenericAccount`
- `CoreResourcePool`
- `CoreIPPool`
- `CoreTransformation`
- `CoreBasePermission`
- `CoreMenu`
- `CoreComment`
- `CoreThread`
- `CoreValidator`
- `CoreKeyValue`
- `CoreTriggerRule`
- `CoreAction`
- `CoreNodeTriggerMatch`
