A live change to a node that feeds a Python transform computed attribute no longer starts duplicated recompute tasks. A change to a node the transform query reads now recomputes only the attributes that query feeds, on the nodes that read the changed node through it, instead of every Python computed attribute of every kind subscribed to any query group that holds the changed node. A transform feeding several attributes builds one set of query automations instead of one set per attribute. The stored values are the same.

A branch whose schema differs from the default branch now keeps its own automations, so a schema update on that branch also refreshes the computed attributes it shares with the default branch. Before, those attributes kept their previous value on the branch until something else recomputed them.

The automations that carry this are rebuilt on the next reconcile, which `infrahub upgrade` performs, so the previous behavior continues until then.
