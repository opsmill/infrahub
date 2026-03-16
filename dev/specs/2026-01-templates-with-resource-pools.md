---
Title: Ability to reference resource pools in object templates
Author:
  - Patrick Ogenstad
Status: draft
JPD: INFP-358
---
# Ability to reference resource pools in object templates

## Summary

Infrahub supports has two features that doesn't currently interact in an expected way.

* Templates: The ability to create objects in the database based on a template that populates predefined attributes and relationships. This could be a device template that could create a custom InfraDevice object along with multiple InfraInterface relationships.
* Resource pools: The ability to select the next available resource from a previously created pool and assign this allocation to an object.

At present when you combine templates and resource pools, any resources that can get allocated by a pool would be allocated to the template object itself. While this works at the practical level it doesn't provide much value and he expectation would be that objects created from the template would be the ones that get the resource allocation.

For example if there is a template for a device object which gets an ip address from an ip address resource pool, the expectation would be that an ip address from the pool would be allocated to the device that's created from the template.

This feature would be complete when the above expectations are met.

## Problem statement

Resources from resource pools are allocated directly to the template object instead of the final objects created by the template, this is true for the following currently supported resource pools:

* Number pool: The number pools are defined at the attribute level of a given object
* IP Address pool: The IP Address pools are defined at the relationship level of a given object. I.e. a device could have a relationship to an IP address.
* IP Prefix pool: The IP Prefix pools are defined at the relationship level of a given object.

## Backend

### Implementation caveats regarding source

When you create an object from a template we currently populate the "source" for attributes and relationships on the target object. The source ID will refer to the ID of the template. The same source field is used when assigning a resource from a pool. As this source can only have one value a conflict will arise when we want to combine templates with resource pools.

In this case the source reference back to the template has a lower priority than that of the resource pool. As such it should be the source of the resource pool that is preserved.

### Backend problem statement

For attribute level resource pools, i.e. the number pool, we should be able to keep the current API as is. Assigning a number pool to a template would look exactly the same from the frontends point of view and "from_pool" would be used to indicate that an attribute created as part of a template operation should source numbers from a pool. The backend should then avoid assigning a number from the pool to the template and instead only keep a reference to the pool. The attribute of the template should have a `NULL` value.

For relationship level resource pools, i.e. ip addresses and ip prefix pools, there's a current limitation in the backend as the "source" isn't defined at the relationship field level of an object but instead on the relationship itself. We have no way of defining the values of a field for a relationship that is not there, also on the GraphQL level we don't have a way to return an entry on a `NULL` value. As such a compromise has been made which will be in place until such an operation is possible.

### Solution

In order to have a data point that can be saved to the database as well as having a way to present it to the end users we will generate an additional attribute for template objects with relationships pointing to IP Address or IP Prefix types and use these attributes as containers to store information around which pool should be used when creating objects from the pool.

```yaml
nodes:
  - name: IPAddress
    namespace: Ipam
    include_in_menu: false
    uniqueness_constraints:
      - ["address__value"]
    inherit_from:
      - "BuiltinIPAddress"
  - name: Device
    namespace: Infra
    generate_template: true
    attributes:
      - name: name
        kind: Text
        unique: true
    relationships:
      - name: primary_address
        peer: IpamIPAddress
        label: Primary IP Address
```

Loading the above schema we can determine that template should be generated for the device object and we have a relationship to a kind that inherits from BuiltinIPAddress. As such when generating the schema we should ensure to also generate a new relationship where the pool information could be stored. It would look something like this:

```yaml
nodes:
  - name: IPAddress
    namespace: Ipam
    include_in_menu: false
    uniqueness_constraints:
      - ["address__value"]
    inherit_from:
      - "BuiltinIPAddress"
  - name: Device
    namespace: Infra
    generate_template: true
    attributes:
      - name: name
        kind: Text
        unique: true
    relationships:
      - name: primary_address
        peer: IpamIPAddress
        label: Primary IP Address
    relationships:
      - name: primary_address_from_resource_pool
        peer: CoreIPAddressPool
        cardinality: one

```

When creating or modifying a template based on the above schema logic should be in place from preventing users from populating both `primary_address` and `primary_address_from_resource_pool` at the same time.

Then creating objects from the template the backend code should consult both the `primary_address_from_resource_pool` and `primary_address` relationships to determine which one is set. If the relationship has been created the backend should treat it as any other relationship. If the `primary_address_from_resource_pool` relationship has been defined the backend should assign a resource from the pool when creating the object.

### Requirements

* Assigning number pools to a template should keep a reference to the pool within the template, resources created by the template should be assigned numbers from that pool.
* Assigning ip address or ip prefix pools to a template should store the reference to the pool within the template, resource created by the template should be assigned numbers from that pool.
* If the relationship to "primary_address" is removed generated attribute should also be removed. (note that the relationship name is only in reference to the above schema it should work for any schema)

### Limitations

* Because a relationship is used for the `primary_address_from_resource_pool` example from above the implementation will be easier but it won't work to assign multiple resources on a cardinality=many relationship.

## Frontend

### Solution

The frontend will need to keep track of template relationships to IP address and IP prefix pools as well as the relationships with the generated "_from_resource_pool" suffix. The fact that we have two relationships that contains the same type of information should be agnostic from a users point of view.

### Requirements

* Create and update forms for templates will need to be updated to ensure that we save the correct data when combining the data for two fields into one that's seen in the UI
* The detailed view of a template will need to be updated to ensure that the relationship and attribute is combined into a logical view
* This should work within the existing forms as well as within any inline editing form

## Open questions

It was suggested that a new "kind" could be introduced so that it would be easier to identify these type of attributes from the frontend point of view. As we now use a relationship instead of an attribute an indicator could be to look a the "_from_resource_pool" suffix in combination of the peer type of a pool.
