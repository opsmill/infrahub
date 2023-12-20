---
label: Rendering configuration
# icon: file-directory
tags: [tutorial]
order: 550
---

# Rendering Jinja templates

Infrahub can natively render any Jinja templates dynamically. Internally it's referred to as `RFile` for `Rendered File`.
There are many systems that can render Jinja Templates. What sets Infrahub apart is the deep integration with the `Unified Version Control System` and the Jinja rendering engine. It allows users to prepare and render a change in a branch, including changes on the data AND on the template without affecting the rendering on the main branch.

!!!
The `infrahub-demo-edge` repository that we integrated in the previous step includes one RFile that can generate a full configuration for each device.
!!!

## RFile

An `RFile` is an internal concept that represents a Jinja Template coupled with a `GraphQL Query`. Combined, they can render any file in text format.

## Generate the configuration of a device

The rendered configuration is available via the REST API under `/api/rfile/<rfile_name>` followed by any additional parameters expected in the GraphQL query.

The `rfile`, `device_startup`, present in the repository expects the name of the device as a parameter `/api/rfile/<rfile_name>?device=<device_name>`. As an example, below is the URL for couple of devices:

- [Configuration for `ord1-edge1` (`/api/rfile/device_startup?device=ord1-edge1`)](http://localhost:8000/api/rfile/device_startup?device=ord1-edge1)
- [Configuration for `atl1-edge2` (`/api/rfile/device_startup?device=atl1-edge2`)](http://localhost:8000/api/rfile/device_startup?device=atl1-edge2)

In these examples `device_startup` is the name of an RFile defined in the `infrahub-demo-edge` repository. The query string `?device=atl1-edge2` includes all the arguments that are required by the GraphQL query associated with this RFile.

## Create a new branch, then change the data AND the template

Next, we'll create a new branch and make modifications both in the data and in the template to explore the integration between the Jinja Template Renderer and the storage engine.

### 1. Create a new branch `update-ethernet1`

From the frontend, create a new branch named `update-ethernet1` and be sure to uncheck the toggle `Is data only` in the UI.

![Create a new branch (not with Data Only)](../../media/tutorial/tutorial-6-git-integration.cy.ts/tutorial_6_branch_creation.png)

### 2. Update the interface Ethernet 1 for atl1-edge1

Now we'll make a change in the branch `update-ethernet1` that will be reflected in the rendered template, like updating the documentation.

1. Navigate to the device `atl1-edge1` in the frontend
2. Navigate to the list of its interfaces in the `Interfaces` Tab
3. Select the interface `Ethernet1`
4. Edit the interface `Ethernet`
5. Update its description to `New description in the branch`
6. Save your change

![Update the description for the interface Ethernet1](../../media/tutorial/tutorial-6-git-integration.cy.ts/tutorial_6_interface_update.png)

### 3. Update the Jinja2 template in GitHub

The final step is to modify the Jinja template directly from GitHub

In GitHub:

1. Navigate to your clone
2. Select the new branch in the branch menu dropdown
3. Select the file `templates` / `device_startup_config.tpl.j2`
4. Edit the file with the `pen` in the top right corner
5. Delete the lines 77 and 78 (i.e. the last two lines of `ip prefix-list BOGON-Prefixes`)
6. Commit your changes in the branch `update-ethernet1` directly from GitHub

![Update the template in GitHub](../../media/tutorial_rfile_update_jinja.gif)

!!!success Validate that everything is correct
After making these changes, you should be able to render the RFile for the branch `update-ethernet1` and see the changes made to the data AND to the schema at the same time at the address [`/rfile/device_startup?device=ord1-edge1&branch=update-ethernet1`](http://localhost:8000/api/rfile/device_startup?device=ord1-edge1&branch=update-ethernet1)
!!!

### 4. Merge the Branch `update-ethernet1`

After merging the branch `update-ethernet1`, regenerate the configuration for `atl1-edge1` in `main` and validate that the 2 changes are now available in `main`.
