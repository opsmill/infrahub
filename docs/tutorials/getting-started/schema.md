---
label: Extend the schema
# icon: file-directory
tags: [tutorial]
order: 850
---
# Extend the schema

Infrahub can be extended by providing your own schema (or models). The version of Infrahub we currently use for the demo is bare-bones and doesn't include many models.

## Visualize the active schema

The default schema is composed of 25+ models that are either mandatory for Infrahub to function like `Account`, `StandardGroup`, `Repository` or that are very generic like `Tag`.

You can explore the current schema by visiting the schema page, you can find it in the left menu under the Unified Storage section.

[!ref Explore the current schema](http://localhost:8000/api/schema)

![](../../media/tutorial/tutorial-3-schema.cy.ts/tutorial_3_schema.png)

[!ref Check the schema documentation for more information](../../reference/schema/readme.md)

## Extend the schema with some network related models

In order to model a network, we need to extend the current models to capture more information like: `Device`, `Interface`, `IPAddress`, `BGPSession`, `Location`, `Role`, `Status` etc.

A schema extension with these types of models and more is available in the `models/` directory

==- Infrastructure Base Schema
:::code source="../../../models/infrastructure_base.yml" :::
==-

Use the following command to load these new models into Infrahub

```sh
invoke demo.load-infra-schema
```

==- Expected Results

```sh
> invoke demo.load-infra-schema
command=IMAGE_NAME=opsmill/infrahub-py3.11 IMAGE_VER=0.9.1 PYTHON_VER=3.11 INFRAHUB_BUILD_NAME=infrahub NBR_WORKERS=1 CACHE_DOCKER_IMAGE=redis:7.2 MESSAGE_QUEUE_DOCKER_IMAGE=rabbitmq:3.12-management INFRAHUB_DB_TYPE=neo4j DATABASE_DOCKER_IMAGE=neo4j:5.14-community docker compose -f development/docker-compose-deps.yml -f development/docker-compose-database-neo4j.yml -f development/docker-compose.yml -f development/docker-compose.default.yml -p infrahub run infrahub-git infrahubctl schema load models/infrastructure_base.yml
[+] Creating 4/0
 ✔ Container infrahub-message-queue-1    Running                                                                                                 0.0s
 ✔ Container infrahub-cache-1            Running                                                                                                 0.0s
 ✔ Container infrahub-database-1         Running                                                                                                 0.0s
 ✔ Container infrahub-infrahub-server-1  Running                                                                                                 0.0s
[+] Running 3/3
 ✔ Container infrahub-database-1       Healthy                                                                                                   0.5s
 ✔ Container infrahub-message-queue-1  Healthy                                                                                                   0.5s
 ✔ Container infrahub-cache-1          Healthy                                                                                                   0.5s
 schema 'models/infrastructure_base.yml' loaded successfully in 12.352 sec!
command=IMAGE_NAME=opsmill/infrahub-py3.11 IMAGE_VER=0.9.1 PYTHON_VER=3.11 INFRAHUB_BUILD_NAME=infrahub NBR_WORKERS=1 CACHE_DOCKER_IMAGE=redis:7.2 MESSAGE_QUEUE_DOCKER_IMAGE=rabbitmq:3.12-management INFRAHUB_DB_TYPE=neo4j DATABASE_DOCKER_IMAGE=neo4j:5.14-community docker compose -f development/docker-compose-deps.yml -f development/docker-compose-database-neo4j.yml -f development/docker-compose.yml -f development/docker-compose.default.yml -p infrahub restart infrahub-server
[+] Restarting 1/1
 ✔ Container infrahub-infrahub-server-1  Started                                                                                                 1.5s
 ```

==-

!!!success Validate that everything is correct
**Reload the frontend** to see the new menu corresponding to the new models we added to the schema.
!!!

## Load some real data into the database

In order to have more meaningful data to explore, we'll use a sample topology of 6 devices as presented below that is leveraging all the new models we added to the schema.

![](../../media/demo_edge.excalidraw.svg)

Use the following command to load these new models into Infrahub

```sh
invoke demo.load-infra-data
```

==- Expected Results

```sh
> invoke demo.load-infra-data
command=IMAGE_NAME=opsmill/infrahub-py3.11 IMAGE_VER=0.9.1 PYTHON_VER=3.11 INFRAHUB_BUILD_NAME=infrahub NBR_WORKERS=1 CACHE_DOCKER_IMAGE=redis:7.2 MESSAGE_QUEUE_DOCKER_IMAGE=rabbitmq:3.12-management INFRAHUB_DB_TYPE=neo4j DATABASE_DOCKER_IMAGE=neo4j:5.14-community docker compose -f development/docker-compose-deps.yml -f development/docker-compose-database-neo4j.yml -f development/docker-compose.yml -f development/docker-compose.default.yml -p infrahub run infrahub-git infrahubctl run models/infrastructure_edge.py
[+] Creating 4/0
 ✔ Container infrahub-database-1         Running                                                                                                 0.0s
 ✔ Container infrahub-message-queue-1    Running                                                                                                 0.0s
 ✔ Container infrahub-cache-1            Running                                                                                                 0.0s
 ✔ Container infrahub-infrahub-server-1  Running                                                                                                 0.0s
[+] Running 3/3
 ✔ Container infrahub-database-1       Healthy                                                                                                   0.5s
 ✔ Container infrahub-message-queue-1  Healthy                                                                                                   0.5s
 ✔ Container infrahub-cache-1          Healthy                                                                                                   0.5s
[13:26:38] INFO     Creating User Accounts, Groups & Organizations & Platforms                                              infrastructure_edge.py:845
[13:26:39] INFO     - Created CoreAccount - pop-builder                                                                     infrastructure_edge.py:857
           INFO     - Created CoreAccount - CRM Synchronization                                                             infrastructure_edge.py:857
[13:26:40] INFO     - Created CoreAccount - Jack Bauer                                                                      infrastructure_edge.py:857
           INFO     - Created CoreAccount - Chloe O'Brian                                                                   infrastructure_edge.py:857
           INFO     - Created CoreAccount - David Palmer                                                                    infrastructure_edge.py:857
           INFO     - Created CoreAccount - Operation Team                                                                  infrastructure_edge.py:857
[13:26:41] INFO     - Created CoreAccount - Engineering Team                                                                infrastructure_edge.py:857
           INFO     - Created CoreAccount - Architecture Team                                                               infrastructure_edge.py:857
           INFO     - Created CoreStandardGroup - arista_devices                                                            infrastructure_edge.py:890
           INFO     - Created CoreStandardGroup - edge_router                                                               infrastructure_edge.py:890
           INFO     - Created CoreStandardGroup - cisco_devices                                                             infrastructure_edge.py:890
           INFO     - Created CoreStandardGroup - core_router                                                               infrastructure_edge.py:890
[13:26:42] INFO     - Created CoreOrganization - Colt                                                                       infrastructure_edge.py:890
           INFO     - Created CoreOrganization - Verizon                                                                    infrastructure_edge.py:890
           INFO     - Created CoreOrganization - Hurricane Electric                                                         infrastructure_edge.py:890
           INFO     - Created CoreOrganization - GTT                                                                        infrastructure_edge.py:890
           INFO     - Created CoreOrganization - Zayo                                                                       infrastructure_edge.py:890
           INFO     - Created CoreOrganization - Lumen                                                                      infrastructure_edge.py:890
           INFO     - Created CoreOrganization - Duff                                                                       infrastructure_edge.py:890
           INFO     - Created CoreOrganization - Equinix                                                                    infrastructure_edge.py:890
           INFO     - Created InfraPlatform - Cisco NXOS SSH                                                                infrastructure_edge.py:890
           INFO     - Created InfraPlatform - Cisco IOS                                                                     infrastructure_edge.py:890
           INFO     - Created InfraPlatform - Arista EOS                                                                    infrastructure_edge.py:890
           INFO     - Created InfraPlatform - Juniper JunOS                                                                 infrastructure_edge.py:890
[13:26:43] INFO     - Created CoreStandardGroup - transit_interfaces                                                        infrastructure_edge.py:890
           INFO     - Created CoreOrganization - Telia                                                                      infrastructure_edge.py:890
           INFO     Creating Autonommous Systems                                                                            infrastructure_edge.py:898
[13:26:44] INFO     - Created InfraAutonomousSystem - AS8220                                                                infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS701                                                                 infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS3257                                                                infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS1299                                                                infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS6939                                                                infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS3356                                                                infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS64496                                                               infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS6461                                                                infrastructure_edge.py:914
           INFO     - Created InfraAutonomousSystem - AS24115                                                               infrastructure_edge.py:914
           INFO     Creating BGP Peer Groups                                                                                infrastructure_edge.py:919
[13:26:45] INFO     - Created InfraBGPPeerGroup - POP_GLOBAL                                                                infrastructure_edge.py:940
           INFO     - Created InfraBGPPeerGroup - TRANSIT_DEFAULT                                                           infrastructure_edge.py:940
           INFO     - Created InfraBGPPeerGroup - POP_INTERNAL                                                              infrastructure_edge.py:940
           INFO     - Created InfraBGPPeerGroup - TRANSIT_TELIA                                                             infrastructure_edge.py:940
           INFO     - Created InfraBGPPeerGroup - IX_DEFAULT                                                                infrastructure_edge.py:940
           INFO     Creating Tags                                                                                           infrastructure_edge.py:947
           INFO     - Created BuiltinTag - blue                                                                             infrastructure_edge.py:954
           INFO     - Created BuiltinTag - red                                                                              infrastructure_edge.py:954
           INFO     - Created BuiltinTag - green                                                                            infrastructure_edge.py:954
           INFO     Creating Site and associated objects (Device, Circuit, BGP Sessions)                                    infrastructure_edge.py:961
           INFO     - Created BuiltinLocation - den1                                                                        infrastructure_edge.py:247
           INFO     - Created BuiltinLocation - atl1                                                                        infrastructure_edge.py:247
           INFO     - Created BuiltinLocation - jfk1                                                                        infrastructure_edge.py:247
           INFO     - Created BuiltinLocation - ord1                                                                        infrastructure_edge.py:247
[13:26:46] INFO     - Created InfraDevice - den1-edge1                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - jfk1-edge1                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - atl1-edge1                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - ord1-edge1                                                                      infrastructure_edge.py:292
[13:26:51] INFO      - Created InfraCircuit - Telia [TELIA-e87e45cc]                                                        infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Telia [TELIA-279b86e2]                                                        infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Telia [TELIA-b6c893c2]                                                        infrastructure_edge.py:419
[13:26:52] INFO      - Created InfraCircuit - Telia [TELIA-2349d510]                                                        infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Colt [COLT-d0d6253c]                                                          infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Colt [COLT-326cdea1]                                                          infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Colt [COLT-0f58d6f3]                                                          infrastructure_edge.py:419
[13:26:53] INFO      - Created InfraCircuit - Colt [COLT-114a7233]                                                          infrastructure_edge.py:419
[13:26:54] INFO      - Created InfraCircuit - Equinix [EQUINIX-675afa38]                                                    infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Equinix [EQUINIX-cac5b473]                                                    infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Equinix [EQUINIX-4029091b]                                                    infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Equinix [EQUINIX-18accc9f]                                                    infrastructure_edge.py:419
[13:26:55] INFO     - Created InfraDevice - ord1-edge2                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - atl1-edge2                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - jfk1-edge2                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - den1-edge2                                                                      infrastructure_edge.py:292
[13:26:57] INFO      - Created InfraCircuit - Telia [TELIA-40b4b08e]                                                        infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Telia [TELIA-ad9fb2e8]                                                        infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Telia [TELIA-d0a677d6]                                                        infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Telia [TELIA-b0046316]                                                        infrastructure_edge.py:419
[13:26:58] INFO      - Created InfraCircuit - Colt [COLT-4152e5fb]                                                          infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Colt [COLT-a56b37c2]                                                          infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Colt [COLT-b7cbc746]                                                          infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Colt [COLT-6a686855]                                                          infrastructure_edge.py:419
[13:26:59] INFO      - Created InfraCircuit - Equinix [EQUINIX-d3c6fabf]                                                    infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Equinix [EQUINIX-3761d171]                                                    infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Equinix [EQUINIX-9593d88a]                                                    infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Equinix [EQUINIX-3deddad8]                                                    infrastructure_edge.py:419
           INFO     - Created InfraDevice - ord1-core1                                                                      infrastructure_edge.py:292
[13:27:00] INFO     - Created InfraDevice - atl1-core1                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - jfk1-core1                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - den1-core1                                                                      infrastructure_edge.py:292
[13:27:02] INFO     - Created InfraDevice - ord1-core2                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - atl1-core2                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - jfk1-core2                                                                      infrastructure_edge.py:292
           INFO     - Created InfraDevice - den1-core2                                                                      infrastructure_edge.py:292
[13:27:04] INFO      - Connected 'ord1-edge1::Ethernet1' <> 'ord1-edge2::Ethernet1'                                         infrastructure_edge.py:493
           INFO      - Connected 'atl1-edge1::Ethernet1' <> 'atl1-edge2::Ethernet1'                                         infrastructure_edge.py:493
           INFO      - Connected 'jfk1-edge1::Ethernet1' <> 'jfk1-edge2::Ethernet1'                                         infrastructure_edge.py:493
[13:27:05] INFO      - Connected 'den1-edge1::Ethernet1' <> 'den1-edge2::Ethernet1'                                         infrastructure_edge.py:493
           INFO      - Connected 'ord1-edge1::Ethernet2' <> 'ord1-edge2::Ethernet2'                                         infrastructure_edge.py:493
           INFO      - Connected 'jfk1-edge1::Ethernet2' <> 'jfk1-edge2::Ethernet2'                                         infrastructure_edge.py:493
           INFO      - Connected 'atl1-edge1::Ethernet2' <> 'atl1-edge2::Ethernet2'                                         infrastructure_edge.py:493
           INFO      - Created BGP Session 'ord1-edge1' >> 'ord1-edge2': 'POP_INTERNAL' '10.0.0.2/32' >> '10.0.0.5/32'      infrastructure_edge.py:526
           INFO      - Created BGP Session 'jfk1-edge1' >> 'jfk1-edge2': 'POP_INTERNAL' '10.0.0.1/32' >> '10.0.0.6/32'      infrastructure_edge.py:526
           INFO      - Connected 'den1-edge1::Ethernet2' <> 'den1-edge2::Ethernet2'                                         infrastructure_edge.py:493
           INFO      - Created BGP Session 'atl1-edge1' >> 'atl1-edge2': 'POP_INTERNAL' '10.0.0.3/32' >> '10.0.0.7/32'      infrastructure_edge.py:526
           INFO      - Created BGP Session 'den1-edge1' >> 'den1-edge2': 'POP_INTERNAL' '10.0.0.4/32' >> '10.0.0.8/32'      infrastructure_edge.py:526
           INFO      - Created BGP Session 'ord1-edge2' >> 'ord1-edge1': 'POP_INTERNAL' '10.0.0.5/32' >> '10.0.0.2/32'      infrastructure_edge.py:526
           INFO      - Created BGP Session 'atl1-edge2' >> 'atl1-edge1': 'POP_INTERNAL' '10.0.0.7/32' >> '10.0.0.3/32'      infrastructure_edge.py:526
           INFO      - Created BGP Session 'jfk1-edge2' >> 'jfk1-edge1': 'POP_INTERNAL' '10.0.0.6/32' >> '10.0.0.1/32'      infrastructure_edge.py:526
[13:27:06] INFO     - Created BuiltinLocation - dfw1                                                                        infrastructure_edge.py:247
           INFO      - Created BGP Session 'den1-edge2' >> 'den1-edge1': 'POP_INTERNAL' '10.0.0.8/32' >> '10.0.0.4/32'      infrastructure_edge.py:526
           INFO     - Created InfraDevice - dfw1-edge1                                                                      infrastructure_edge.py:292
[13:27:08] INFO      - Created InfraCircuit - Telia [TELIA-d494435f]                                                        infrastructure_edge.py:419
[13:27:09] INFO      - Created InfraCircuit - Colt [COLT-b8604504]                                                          infrastructure_edge.py:419
           INFO      - Created InfraCircuit - Equinix [EQUINIX-60846286]                                                    infrastructure_edge.py:419
[13:27:10] INFO     - Created InfraDevice - dfw1-edge2                                                                      infrastructure_edge.py:292
[13:27:13] INFO      - Created InfraCircuit - Telia [TELIA-76cab67e]                                                        infrastructure_edge.py:419
[13:27:14] INFO      - Created InfraCircuit - Colt [COLT-bae5e4b3]                                                          infrastructure_edge.py:419
[13:27:15] INFO      - Created InfraCircuit - Equinix [EQUINIX-0f2db0ab]                                                    infrastructure_edge.py:419
           INFO     - Created InfraDevice - dfw1-core1                                                                      infrastructure_edge.py:292
[13:27:17] INFO     - Created InfraDevice - dfw1-core2                                                                      infrastructure_edge.py:292
[13:27:19] INFO      - Connected 'dfw1-edge1::Ethernet1' <> 'dfw1-edge2::Ethernet1'                                         infrastructure_edge.py:493
[13:27:20] INFO      - Connected 'dfw1-edge1::Ethernet2' <> 'dfw1-edge2::Ethernet2'                                         infrastructure_edge.py:493
           INFO      - Created BGP Session 'dfw1-edge1' >> 'dfw1-edge2': 'POP_INTERNAL' '10.0.0.17/32' >> '10.0.0.18/32'    infrastructure_edge.py:526
           INFO      - Created BGP Session 'dfw1-edge2' >> 'dfw1-edge1': 'POP_INTERNAL' '10.0.0.18/32' >> '10.0.0.17/32'    infrastructure_edge.py:526
           INFO     Creating Full Mesh iBGP SESSION between all the Edge devices                                            infrastructure_edge.py:973
           INFO     - Created BGP Session 'atl1-edge1' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.2/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge1' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.5/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.2/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.5/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge1' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.1/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge1' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.6/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.1/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.6/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge1' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.4/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge1' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.8/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.4/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.8/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge1' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge1' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.3/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'atl1-edge2' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.7/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.3/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.7/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.3/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.7/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.1/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.6/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.1/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.6/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.4/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.8/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.4/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.8/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge1' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.2/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'ord1-edge2' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.5/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.3/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.7/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.3/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.7/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.2/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.5/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.2/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.5/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.4/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.8/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.4/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.8/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge1' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.1/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'jfk1-edge2' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.6/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.3/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.7/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.3/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.7/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.2/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.5/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.2/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.5/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.1/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.6/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.1/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.6/32'        infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge1' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.4/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'dfw1-edge1': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.17/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'den1-edge2' >> 'dfw1-edge2': 'POP_GLOBAL' '10.0.0.8/32' >> '10.0.0.18/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.3/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.7/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'atl1-edge1': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.3/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'atl1-edge2': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.7/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.2/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.5/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'ord1-edge1': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.2/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'ord1-edge2': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.5/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.1/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.6/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'jfk1-edge1': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.1/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'jfk1-edge2': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.6/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.4/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge1' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.17/32' >> '10.0.0.8/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'den1-edge1': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.4/32'       infrastructure_edge.py:1004
           INFO     - Created BGP Session 'dfw1-edge2' >> 'den1-edge2': 'POP_GLOBAL' '10.0.0.18/32' >> '10.0.0.8/32'       infrastructure_edge.py:1004
[13:27:25] INFO     Creating Backbone Links & Circuits                                                                     infrastructure_edge.py:1014
           INFO     - Created InfraCircuit - Lumen [LUMEN-8453ca9c]                                                        infrastructure_edge.py:1052
[13:27:26] INFO      - Connected 'atl1-edge1::Ethernet6' <> 'ord1-edge1::Ethernet3'                                        infrastructure_edge.py:1102
[13:27:27] INFO     - Created InfraCircuit - Lumen [LUMEN-6cb08cf2]                                                        infrastructure_edge.py:1052
[13:27:28] INFO      - Connected 'atl1-edge1::Ethernet5' <> 'jfk1-edge1::Ethernet3'                                        infrastructure_edge.py:1102
           INFO     - Created InfraCircuit - Lumen [LUMEN-af16a2b5]                                                        infrastructure_edge.py:1052
[13:27:29] INFO      - Connected 'jfk1-edge1::Ethernet6' <> 'ord1-edge1::Ethernet6'                                        infrastructure_edge.py:1102
           INFO     - Created InfraCircuit - Zayo [ZAYO-25ea6d29]                                                          infrastructure_edge.py:1052
[13:27:31] INFO      - Connected 'atl1-edge2::Ethernet6' <> 'ord1-edge2::Ethernet3'                                        infrastructure_edge.py:1102
           INFO     - Created InfraCircuit - Zayo [ZAYO-8968962b]                                                          infrastructure_edge.py:1052
[13:27:32] INFO      - Connected 'atl1-edge2::Ethernet5' <> 'jfk1-edge2::Ethernet3'                                        infrastructure_edge.py:1102
           INFO     - Created InfraCircuit - Zayo [ZAYO-579e7a16]                                                          infrastructure_edge.py:1052
[13:27:33] INFO      - Connected 'jfk1-edge2::Ethernet6' <> 'ord1-edge2::Ethernet6'                                        infrastructure_edge.py:1102
           INFO     Create a new branch and Add a new transit link with GTT on the edge1 device of the given site           infrastructure_edge.py:537
           INFO     - Creating branch: 'ord1-add-transit'                                                                   infrastructure_edge.py:544
[13:27:38] INFO      - Adding new Transit on 'ord1-edge1::Ethernet10'                                                       infrastructure_edge.py:556
           INFO       - Created InfraCircuit - GTT [GTT-d8ee9606]                                                           infrastructure_edge.py:591
[13:27:39] INFO     Create a new Branch and Change the IP addresses between edge1 and edge2 on the selected site            infrastructure_edge.py:648
           INFO     - Creating branch: 'jfk1-update-edge-ips'                                                               infrastructure_edge.py:649
[13:27:43] INFO      - Replaced jfk1-edge1-Ethernet1 IP to 10.1.0.32/31                                                     infrastructure_edge.py:678
           INFO      - Replaced jfk1-edge2-Ethernet1 IP to 10.1.0.33/31                                                     infrastructure_edge.py:687
           INFO     Create a new Branch and Delete Colt Transit Circuit                                                     infrastructure_edge.py:694
           INFO     - Creating branch: 'atl1-delete-transit'                                                                infrastructure_edge.py:699
[13:27:47] INFO      - Deleted Colt [DUFF-cf3a6ed2d959]                                                                     infrastructure_edge.py:752
           INFO      - Deleted Colt [DUFF-4141a7be1f9a]                                                                     infrastructure_edge.py:752
           INFO     Create a new Branch and introduce some conflicts                                                        infrastructure_edge.py:759
           INFO     - Creating branch: 'den1-maintenance-conflict'                                                          infrastructure_edge.py:769
[13:27:53] INFO     Create a new Branch and introduce some conflicts on the platforms for node ADD and DELETE               infrastructure_edge.py:802
           INFO     - Creating branch: 'platform-conflict'                                                                  infrastructure_edge.py:809
```

==-

!!!success Validate that everything is correct
You should now be able to see 10 devices when you visit the list of devices at [http://localhost:8000/objects/InfraDevice](http://localhost:8000/objects/InfraDevice)
!!!
