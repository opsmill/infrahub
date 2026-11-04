# Decisions

One line each, with the reason. Knobs: none; the prototype carried no knob.

- The allocation weight is read from the resource prefix node, through one query with an inline fragment per prefix kind that has an `allocation_weight` attribute, because the utilization query's `weight` field is the prefix size. When no prefix kind has the attribute, the page sends no extra request and shows no weight.
- The list is ordered by weight, highest first, a missing weight counting as 0, then by prefix with numeric collation, because the backend returns resources in no fixed order and allocates from the heaviest first.
- The bar's second segment is the usage the viewing branch adds to the default branch, and its tooltip says "This branch only", because that is what the utilization query returns. On the default branch the segment is empty.
- "Member type has no default" replaces the prototype's "defaults to Prefix" for a prefix pool without a member type, because the backend has no fallback at allocation time; a request must set it.
- The allocated table has no Branch column, because the backend returns the viewing branch for every row.
- The table lists every prefix or address inside the resource prefix that is visible on the branch, including ones created by hand, because that is what the allocations query returns; an entry the pool did not reserve shows "None" as identifier.
- The count in the table header comes from the first page of allocations, not from a second query, because every page carries the count.
- The selected resource prefix is a path segment, `/resources/<id>`, not a query parameter, because the number pool does the same with `/ranges/<id>` and the breadcrumb already reads that segment.
- Without a resource prefix in the link, the first one in list order is selected without redirecting, so the link stays short; the breadcrumb's resource selector appears once a resource prefix is in the link.
- The pool node is fetched with its own typed query rather than the generic object query, because the header needs the namespace's default flag to leave the `namespace` parameter out of the IPAM link.
- The Actions menu is the number pool menu with the pool kind as a parameter, so Edit opens the existing IP pool forms.
