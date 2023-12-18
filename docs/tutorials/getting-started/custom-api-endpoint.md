---
label: Custom API endpoint
# icon: file-directory
tags: [tutorial]
order: 500
---

# Create a custom API endpoint

As powerful as Jinja templates are, sometimes it’s both cleaner and simpler to work directly in code. The Infrahub transform endpoint lets you do exactly that. Where an `RFile` combines a GraphQL query together with a Jinja template, the Transform operation combines a GraphQL query with code. You might use a Transform instead of an `RFile` when you need to return structured data as opposed to a classic text-based configuration file.

In the example repository `infrahub-demo-edge` we use a Transform to render a configuration in the OpenConfig format. In this example, we want to generate OpenConfig interface data. The URL to target looks like this:

```txt
http://localhost:8000/api/transform/openconfig/interfaces?device=ord1-edge1&branch=cr1234
```

Breaking it down into components gives us:

- `http://localhost:8000/api/transform`: The base URL of Infrahub together with the transform endpoint.
- `openconfig/interfaces`: The name of the transform together with the path within that transform. A transform can have multiple internal endpoints, the demo repository allows for `interfaces` and `network-instances/network-instance/protocols/protocol/bgp/neighbors` under the base `openconfig` endpoint.
- `?device=ord1-edge1&branch=cr1234`: The query string that provides a list of arguments for the GraphQL query. In this case only the name of the device. Together with `branch` to show that we want to run the transform against a specific branch within Infrahub.

Render the data by going to this URL (linked from the above example URL): [Generate the OpenConfig interface data for `ord1-edge1` on the branch `cr1234`](http://localhost:8000/api/transform/openconfig/interfaces?device=ord1-edge1&branch=cr1234)
