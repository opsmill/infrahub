---
label: Render config with Jinja2 templates
# icon: file-directory
tags: [tutorial]
order: 400
---

### Generate configuration and transform within the branch

Render a jinja template or a transform on any branch by specifying the name of the branch in the URL `branch=<BRANCH_NAME>`.

- [Render the configuration for `ord1-edge1` on the branch `cr1234`](http://localhost:8000/rfile/device_startup?device=ord1-edge1&branch=cr1234)
- [Generate the Openconfig interface data for `ord1-edge1` on the branch `cr1234`](http://localhost:8000/transform/openconfig/interfaces?device=ord1-edge1&branch=cr1234)


## Modify a file in the Git Repository within the branch as well

From the Github interface, edit the file 