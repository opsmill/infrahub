Fixed a schema load failing with `Unable to find the attribute` when it renamed an attribute and, in the same load, changed the kind of that attribute or made it unique.
Fixed a schema load that renamed an attribute and, in the same load, added it to or removed it from a uniqueness constraint: the load could leave duplicate edges for the attribute on the node's profiles and templates.
