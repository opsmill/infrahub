Allow objects to be converted to another type by mapping fields or defining custom values.

* For attributes, values from the source object will appear in the target form when the attribute type matches between the source and target schemas.
* For dropdowns and enums, if the set of options is identical in both schemas, the selected source value will appear in the target form; otherwise, no value will be shown.
* For relationships, linked objects from the source will appear in the target form when the related object type matches between the source and target schemas.