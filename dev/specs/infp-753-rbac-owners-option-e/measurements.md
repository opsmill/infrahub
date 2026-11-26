# Measurements: owner and source metadata, storage option E

## Source of the numbers and the test files in pull request 1

- All numbers in this file come from the branch `rbac-owners-option-e-impl-infp-753`. "This branch" in this file means that branch. Pull request 1 does not measure them again.
- Pull request 1 holds `conftest.py` and `test_no_owner_overhead.py` of `backend/tests/query_benchmark/ownership/`, and they pass.
- The spike test `test_plain_cypher.py` stays on the branch `rbac-owners-option-e-impl-infp-753`. It is not in pull request 1. The numbers of the spike stay in this file.
- A later pull request adds `test_owner_queries.py`, `option_specific.py` and `test_change_check_overhead.py`. `test_owner_queries.py` writes owners through the GraphQL owner API, and `test_change_check_overhead.py` needs the change check.

## "Today" numbers of SC-001 and SC-002, before any change

SC-001 and SC-002 of [spec.md](spec.md) allow at most 5% more time than "today". This section records "today" (task T008).
A later measure runs the same test on the same data set and compares its numbers with the table below.

### Source of the numbers: the common data set, measured in the worktree of option B

- Options B and E use one common data set and one common test, so that their numbers compare.
- The numbers were measured in the worktree of option B, on `develop` code: commit `475d8b1422` of the branch `rbac-owners-option-b-impl-infp-753`, with the benchmark files only. The code has no owner change at this commit.
- The numbers are valid for option E, because the code and the data set are the same.
- This branch holds the same two files, byte for byte: the fixture `reference_data_set` in [conftest.py](../../../backend/tests/query_benchmark/ownership/conftest.py) and the test [test_no_owner_overhead.py](../../../backend/tests/query_benchmark/ownership/test_no_owner_overhead.py).
- This branch did not run the test at full size for the "today" numbers. One run with 50 devices and 2,400 interfaces on 2026-11-12 proved that the test passes on this branch. That run gives no "today" number.
- The run at full size on the code of this branch is in the section "Numbers of SC-001 and SC-002 on the code of this branch".
- An earlier version of this file held "today" numbers of the first data set of option E. The common data set replaced that data set, so those numbers are removed.

### Run and data set

- Run: 2026-11-12, from 15:21 to 15:57 UTC. Result of the test runner: `4 passed, 1 warning in 2109.84s (0:35:09)`.
- Real size of the data set: the full reference data set of the spec.
  - 10,000 devices
  - 480,000 interfaces (48 for each device)
  - 363 locations in a hierarchy 5 levels deep (3 children for each parent: 3, 9, 27, 81 and 243 locations)
  - 50 account groups
  - No node has an owner.
- The schema of the data set: `BenchDevice` has a Parent relationship to a rack, and `BenchInterface` has a Parent relationship to its device. An interface has 6 parents above it. This is the depth that SC-009 names.
- Each number is the median time of one operation. The test measures the time of the call of the SDK client, which goes through the API.
- A list query runs one time before the measure, so the caches of the database are warm.
- The load of the data set took 19 minutes 36 seconds. This time includes the start of the containers and of the application.

### Results

| Operation | Criterion | Data set | Runs | Median |
|---|---|---|---|---|
| List query: first page of 50 devices, with the count | SC-001 | 10,000 devices, 480,000 interfaces | 20 | 73.9 ms |
| List query: first page of 50 interfaces, with the count | SC-001 | 10,000 devices, 480,000 interfaces | 20 | 1,325.7 ms |
| List query: the interfaces of one device (filter `device__ids`) | SC-001 | 10,000 devices, 480,000 interfaces | 20 | 4,584.1 ms |
| List query: one device by name (filter `name__value`) | SC-001 | 10,000 devices, 480,000 interfaces | 20 | 117.1 ms |
| Create one interface | SC-002 | 10,000 devices, 480,000 interfaces | 20 | 38.5 ms |
| Update the description of one interface | SC-002 | 10,000 devices, 480,000 interfaces | 20 | 23.5 ms |
| Delete one interface | SC-002 | 10,000 devices, 480,000 interfaces | 20 | 22.9 ms |
| Delete one device with 4 interfaces | SC-002 | 10,000 devices, 480,000 interfaces | 5 | 146,400.1 ms |
| Object file load: 10 devices with 4 interfaces each | SC-002 | 10,000 devices, 480,000 interfaces | 5 | 1,316.7 ms |
| Generator run: 1 target, 1 node written | SC-002 | 10,000 devices, 480,000 interfaces | 5 | 584.1 ms |

### How to run the measure again

```bash
uv run pytest backend/tests/query_benchmark/ownership/test_no_owner_overhead.py -s -p no:cacheprovider --no-cov -q --session-timeout=10800
```

- `INFRAHUB_OWNERSHIP_BENCHMARK_DEVICES` sets a smaller number of devices. The test prints the real size above each table.

### Environment of the run

- Machine: a shared VM with 16 CPUs (AMD EPYC 9R45) and 61 GiB of memory.
- A second benchmark run used the machine at the same time. The load average was between 2.6 and 6.8 at the times of the checks.
- Database: Neo4j `2026.10.1-enterprise` in a container, with a heap of 4 GiB and a page cache of 4 GiB.
- Python 3.12.13. The application, the SDK client and the test run in one process.

### Limits of these numbers

- The generator is the `cartags` generator of the test repository `car-dealership`. It reads one person and writes one tag. It does not read devices or interfaces. The database holds the reference data set during the run.
- The delete of one device takes more than 2 minutes on this data set. During a delete, the list of running database transactions showed one query that ran for more than 25 seconds. The query starts from all `Relationship` vertices whose name is in a list of identifiers. The cause was not examined further.
- The numbers change between two runs on this machine. An earlier run on the same day had the same data set size and gave these medians:
  - List queries: 79.9 ms, 1,402.4 ms, 4,837.0 ms and 122.0 ms (4% to 8% more than in the table)
  - Create, update and delete of one interface: 37.5 ms, 26.5 ms and 26.5 ms (3% less to 16% more)
  - The earlier run did not refresh the planner statistics of Neo4j after the load. It was stopped before the object file load and the generator run gave a number.
- The limit of SC-001 and SC-002 is 5%. A difference of 5% is smaller than the change between two runs on this machine. It is not known how many runs, or which machine, give a stable comparison.
- With 20 devices and 960 interfaces, the generator run gave 498.7 ms in one run and 1,239.1 ms in another run.

## Numbers of SC-001 and SC-002 on the code of this branch (task T061)

- Nine of the ten operations show no added time: each difference to "today" is smaller than the change between two "today" runs.
- A delete of a node now runs one more database query. The query alone takes 3.9 ms, which is 17% of the "today" time of the delete of one interface. So SC-002 is not met for the delete of one node.
- The table shows 20.5% more time for the delete of one interface. The table alone does not prove the difference, because the earlier "today" run gave 16% more than the "today" table.
- The run cannot prove the limit of 5% for any operation, because two "today" runs on this machine differed by 3% to 16%.

### Run and data set

- Run: 2026-11-12, from 22:21 to 22:57 UTC. Result of the test runner: `4 passed, 1 warning in 2143.82s (0:35:43)`.
- Code: commit `9f5ede9de1` of the branch `rbac-owners-option-e-impl-infp-753`, with the changes of tasks T065 to T067. The commit that adds this section holds these changes.
- The test, the data set and the command are the ones of the "today" run. The two benchmark files have no change.
- Real size of the data set: the full reference data set of the spec.
  - 10,000 devices
  - 480,000 interfaces (48 for each device)
  - 363 locations in a hierarchy 5 levels deep
  - 50 account groups
  - No node has an owner.
- A first run with 20 devices and 960 interfaces at 22:18 UTC proved that the test passes on this code: `4 passed, 1 warning in 115.73s (0:01:55)`. No number of that run is compared.

### Results

| Operation | Criterion | Runs | "Today" median | Median on this branch | Difference |
|---|---|---|---|---|---|
| List query: first page of 50 devices, with the count | SC-001 | 20 | 73.9 ms | 75.7 ms | 2.4% more |
| List query: first page of 50 interfaces, with the count | SC-001 | 20 | 1,325.7 ms | 1,327.2 ms | 0.1% more |
| List query: the interfaces of one device (filter `device__ids`) | SC-001 | 20 | 4,584.1 ms | 4,624.6 ms | 0.9% more |
| List query: one device by name (filter `name__value`) | SC-001 | 20 | 117.1 ms | 118.4 ms | 1.1% more |
| Create one interface | SC-002 | 20 | 38.5 ms | 37.2 ms | 3.4% less |
| Update the description of one interface | SC-002 | 20 | 23.5 ms | 23.8 ms | 1.3% more |
| Delete one interface | SC-002 | 20 | 22.9 ms | 27.6 ms | 20.5% more |
| Delete one device with 4 interfaces | SC-002 | 5 | 146,400.1 ms | 150,477.3 ms | 2.8% more |
| Object file load: 10 devices with 4 interfaces each | SC-002 | 5 | 1,316.7 ms | 1,118.1 ms | 15.1% less |
| Generator run: 1 target, 1 node written | SC-002 | 5 | 584.1 ms | 578.1 ms | 1.0% less |

### Comparison with SC-001 and SC-002

- SC-001, the four list queries: the differences are 0.1% to 2.4%. The earlier "today" run gave 4% to 8% more than the "today" table on the same code. So the run shows no added time, and it does not prove the limit of 5%.
- SC-002, create and update of one interface, the delete of one device, the object file load and the generator run: the differences are between 15.1% less and 2.8% more.
  - This branch has no change that makes an object file load faster. The 15.1% shows the change between two runs.
  - The run shows no added time for these operations, and it does not prove the limit of 5%.
- SC-002, delete of one interface: not met, because of one more query.
  - The median is 4.7 ms more than in the "today" table (20.5%), and 1.1 ms more than in the earlier "today" run (26.5 ms, 4.2%).
  - Since task T042, the delete of a node runs one more database query, `ownership_node_owner_edges_close`. The query closes the owner edges of the node. It runs also when the node has no owner.
  - This query alone takes 3.9 ms for a node without owners: the median of 50 calls on 2026-11-12, on a test database with one node, after 10 calls that are not counted. This is 17% of the "today" median of the delete.
  - The delete of one device with 4 interfaces deletes 5 nodes. Five more queries add about 20 ms to 150 seconds, so the table cannot show them.
- Decided: the delete of a node keeps the query that closes its owner edges, and the lock of the node (decision of the maintainer, finding 5 of the first review in [opsmill-implement-report.md](opsmill-implement-report.md)).
  - An `EXISTS` check after the lock skips the reads of the holders for a node with no owner.
  - After this change, a cascade delete of 550 nodes took about 6% more time than the base, and a plain delete was within the noise between runs ([opsmill-implement-report.md](opsmill-implement-report.md)). So SC-002 is not met for a cascade delete.

### Environment of the run

- Machine: the shared VM of the "today" run.
- Another implementation run used the machine at the same time. It ran tests with 2 worker processes.
- The load average of the last minute was between 1.5 and 8.4 at 18 checks, one every 2 minutes. It was above 6.8 from 22:23 to 22:35 UTC, during the load of the data set. During the "today" run, it was between 2.6 and 6.8.
- Database: Neo4j `2026.10.1-enterprise` in a container. Python 3.12.13.

### Limits of these numbers

- One run at full size gives the numbers. It is not known how many runs, or which machine, give a stable comparison with a limit of 5%.
- The 3.9 ms of the added query come from a small database. The query starts from the node by its ID, so the size of the data set is not expected to change this time. This was not measured on the reference data set.
- The test measures a customer who uses no owner. It does not measure a write of an owner on an attribute or a link, which now runs one more read query to check the kind of the owner.

## Update and upsert with the lock of the node (2026-11-20)

`Node._update` locks the node vertex at its start, so each update runs one more query. This section compares one update and one upsert that changes nothing with `develop`.

### Run

- Code: the head of the pull request, and `develop` at `ee2d2dc402`.
- Test: a component test that is not committed. It creates one `TestPerson` on the default branch, then runs each GraphQL mutation 210 times and does not count the first 10.
  - Update: `TestPersonUpdate` with a new `name` each time.
  - Upsert that changes nothing: `TestPersonUpsert` with the same `id`, `name` and `height`. The upsert of an existing node saves it, so it takes the lock. The table uses the second series of upserts, which runs after the updates; the first series still includes the start of the database.
- The time is the time of the GraphQL call only.
- 3 runs on each code, in turn: head, `develop`, `develop`, head, `develop`, head.
- Machine: the shared VM, 16 CPUs. Another agent ran tests at the same time. The load average of the last minute was 3.6 after the runs.
- Database: Neo4j in a test container.

### Results

| Mutation | Runs of 200 | `develop` medians | Head medians |
|---|---|---|---|
| Update of one attribute | 3 | 22.65, 23.69, 21.72 ms | 22.29, 22.42, 18.11 ms |
| Upsert that changes nothing | 3 | 11.54, 11.48, 11.20 ms | 11.80, 12.18, 10.53 ms |

- In each round, the median of the head minus the median of `develop` is between 3.61 ms less and 0.70 ms more. The medians of one code differ by up to 4.31 ms between runs (the update on the head). So the run shows no added time, and it cannot show a difference smaller than this noise.
- No query count was measured.

## Pull request 2: cost for a customer with no owners (2026-11-26)

This section compares the code of pull request 2 with the code of pull request 1 alone, for a customer who has no owners (FR-009, SC-001 and SC-002, task T044).

- The runs show no added time that is larger than the change between two runs on this machine. Eight of the ten operations differ by 5.0% or less.
- The object file load takes 10.3% more time on the head, and the delete of one interface takes 8.9% less. The code check below finds no owner query in these two operations when the input gives no owners.
- The code check finds that a query that does not ask for an owner field or a source field, and uses no owner filter or source filter, reads no owners and no sources.
- Each value is the median of one run. So a difference of a few percent is not significant.

### Runs and data set

- Head: the backend code of commit `3bf19c4c1b`. The commits after it up to `14eab625d7` change no code in
  `backend/infrahub`. The later commits `3d0b3395a9`, `1e2ce01f82`, `7525979eae`, `5f37e5265e` and `b310d33b82` to
  `9a5a17b1f5` change the backend code, and this benchmark did not run on them.
  - Run: 2026-11-26, from 12:36:27 to 13:20:40 UTC. Result of the test runner: `4 passed, 1 warning in 2653.39s (0:44:13)`.
- Base: commit `0c44f461d3`, the start of pull request 2. It holds the code of pull request 1 only. Two runs on this commit give the ten rows:
  - Object file load, delete of one device and generator run: 2026-11-26, from 14:06:38 to 14:50:32 UTC. Result of the test runner: `2 passed, 1 warning in 2623.79s (0:43:43)`.
  - List queries and create, update and delete of one interface: 2026-11-26, from 14:58:30 to 15:29:36 UTC. Result of the test runner: `2 passed, 1 warning in 1859.79s (0:30:59)`.
- Test: [test_no_owner_overhead.py](../../../backend/tests/query_benchmark/ownership/test_no_owner_overhead.py), the same file on the two commits. Each run loads the data set again.
- Real size of the data set: 10,000 devices, 480,000 interfaces, 363 locations in a hierarchy 5 levels deep and 50 account groups. No node has an owner.
- Each value is the median of 20 calls (list queries, create, update and delete of one interface) or of 5 calls (the other rows), in one run.
- Each number comes from a run with no other test stack on the machine.
  - The base runs: a check every 2 minutes found no other test stack. In the second base run, the same check found no other pytest process.
  - The first base run loaded its data set while an E2E test stack ran, from 14:08:30 to 14:10:49 UTC. Its measured calls of the object file load and of the delete of one device (5 loads, and 5 deletes of about 155 seconds) ended at 14:49:47 UTC, so they started at about 14:36 UTC. The generator run printed its row at 14:50:22 UTC.
  - The load average of the last minute was between 1.0 and 2.4 from 14:37 to 14:49 UTC in the first base run, and between 2.3 and 3.2 in the second base run.
  - The head run: the logs of this work show no other test stack during the run.
- Machine: the shared VM, 16 CPUs (AMD EPYC 9R45) and 61 GiB of memory. Database: Neo4j `2026.10.1-enterprise` in a test container. Python 3.12.13.

### Results

| Operation | Criterion | Runs | Median on the base | Median on the head | Difference |
|---|---|---|---|---|---|
| List query: first page of 50 devices, with the count | SC-001 | 20 | 1,104.1 ms | 1,130.4 ms | 2.4% more |
| List query: first page of 50 interfaces, with the count | SC-001 | 20 | 2,136.8 ms | 2,095.6 ms | 1.9% less |
| List query: the interfaces of one device (filter `device__ids`) | SC-001 | 20 | 23.9 ms | 25.0 ms | 4.6% more |
| List query: one device by name (filter `name__value`) | SC-001 | 20 | 10.6 ms | 10.4 ms | 1.9% less |
| Create one interface | SC-002 | 20 | 39.5 ms | 38.0 ms | 3.8% less |
| Update the description of one interface | SC-002 | 20 | 26.7 ms | 26.6 ms | 0.4% less |
| Delete one interface | SC-002 | 20 | 31.5 ms | 28.7 ms | 8.9% less |
| Delete one device with 4 interfaces | SC-002 | 5 | 155,384.6 ms | 147,674.2 ms | 5.0% less |
| Object file load: 10 devices with 4 interfaces each | SC-002 | 5 | 1,226.2 ms | 1,352.7 ms | 10.3% more |
| Generator run: 1 target, 1 node written | SC-002 | 5 | 503.7 ms | 502.2 ms | 0.3% less |

- The delete of one device takes more than 2 minutes on the two commits. It was slow before pull request 2. See "Limits of these numbers" of the "today" run.
- The list queries take other times than in the tables of 2026-11-12. For example, the first page of devices took 73.9 ms then. The cause was not examined. This section compares only the runs of this section.

### Code check: a query without owner fields and owner filters reads no owners (FR-009)

All references are to the code of pull request 2.

- graphql-core runs the resolver of a field only when the request selects that field. Each owner field and source field has its own resolver:
  - `ownership`, `target_ownership`, `target_field_ownership` and `sources` of `node_metadata`: `backend/infrahub/graphql/manager.py:801-828`
  - `ownership` of an attribute or a relationship: `backend/infrahub/graphql/manager.py:142-148`
  - `kind`, `display_label`, `hfid` and `is_deleted` of an owner or a source: `backend/infrahub/graphql/types/ownership.py:16-19`. These fields exist only under the owner fields and the source fields above.
- The node, the attribute and the relationship put only a reference into the response, with no database read:
  - `backend/infrahub/core/node/__init__.py:1648` loops over the requested fields of `node_metadata` only. Lines 1667 to 1674 add the reference when the request asks for an owner field or a source field.
  - `backend/infrahub/core/attribute.py:679` adds the reference only when the request asks for `ownership`.
  - `backend/infrahub/graphql/resolvers/single_relationship.py:129` adds the reference only when the request asks for `ownership`.
  - `backend/infrahub/graphql/resolvers/many_relationship.py:135-140` always adds the reference to the response. This is a dictionary. It reads nothing.
- The resolvers return without a database read when the reference is missing: `backend/infrahub/graphql/resolvers/ownership.py:171-173`, `183-185`, `192-194` and `209-211`. The data loaders of that file read the database only for the keys that these resolvers give: lines 42-46, 61-65, 77-80 and 92-111.
- The only other caller of these loaders is the event query. It reads the labels of owners only when an event holds a change of owners: `backend/infrahub/graphql/queries/event.py:57-81`.
- The list query adds the owner filter and the source filter only when the request gives one:
  - `backend/infrahub/core/query/node.py:2155` calls `has_owner_filter`, which is true only when `node_metadata__owners__ids` or `node_metadata__owners__isnull` has a value: `backend/infrahub/core/ownership/filter.py:16` and `20-21`.
  - `backend/infrahub/core/query/node.py:2167` adds the source filter only when `node_metadata__sources__ids` has a value.
  - `backend/infrahub/core/query/node.py:1994` and `backend/infrahub/core/query/node_get_list_filters.py:214` skip these filter names in the filters on fields. They add no Cypher.
- Result: a query that does not ask for `ownership`, `target_ownership`, `target_field_ownership` or `sources`, and uses no owner filter or source filter, reaches no owner read and no source read.
- Mutations, which the table also measures: a create, an update or an upsert whose input gives no owners and no sources reads and writes no owners.
  - `backend/infrahub/core/ownership/input.py:139-179` reads the database only for an owner key or a source key of the input.
  - `backend/infrahub/core/ownership/writer.py:155` returns before any query when the input gives no owner state.
  - Pull request 2 does not change the delete mutation. The query that closes the owner edges of a deleted node comes from pull request 1, so the base and the head both run it.

### How to run the measure again

On each commit:

```bash
uv run pytest backend/tests/query_benchmark/ownership/test_no_owner_overhead.py -s -p no:cacheprovider --no-cov -q --session-timeout=10800
```

### Limits of these numbers

- One run on each commit gives each value. It is not known how many runs give a stable comparison with a limit of 5%.
- The base and the head ran at different times of the day, on a shared VM.

## Spike on the storage of option E (tasks T022 and T023)

The spike measures SC-003 to SC-006, SC-009 and SC-010 of [spec.md](spec.md) with plain Cypher queries on the storage of this branch. It also measures the index on the branch of `HAS_NO_OWNER` and the lookup of an `OwnerSet` vertex.

### Data set of every spike number: the first data set of option E

Every number of this section was measured on the first data set of option E (interface → device → location). The common data set replaced it after the spike.

- Do not compare a number of this section with a number of option B. The two options measured on data sets with different layouts.
- Do not compare a number of this section with the "today" numbers above. They come from the common data set, and they go through the SDK client and the API.
- The polish phase measures again on the common data set: task T144 for SC-003 to SC-006, and task T145 for SC-009 and SC-010.

The first data set of option E had this content:

- 10,000 devices
- 480,000 interfaces, 48 for each device
- 1,364 locations of one kind in a hierarchy 5 levels deep, with 4 children for each parent
- 50 account groups

The first data set of option E had these links:

- An interface has a Parent relationship to its device.
- A device has a Parent relationship to a location of level 5. Each location of level 5 holds 9 or 10 devices.
- A location of levels 2 to 5 has a hierarchy parent.
- So an interface has 6 parents above it: its device, then 5 locations.

| Criterion | First data set of option E | Common data set |
|---|---|---|
| Number of locations | 1,364 | 363 |
| Children for each parent location | 4 | 3 |
| Kinds of location | 1 | 5, one for each level |
| Devices for each location of level 5 | 9 or 10 | 41 or 42 |

The fixture of the first data set is in commit `5deaf7a9f9` of this branch. The load took 1,636 seconds.

### Run of the spike

- Date of the run: 2026-11-12, from 15:50 to 16:23 UTC.
- Code: commit `3b7b68eee7`, with the test file of the spike.
- Test: `backend/tests/query_benchmark/ownership/test_plain_cypher.py` on the branch `rbac-owners-option-e-impl-infp-753`. It is not product code, and it is not in pull request 1. The tasks T144 and T145 can reuse its owner data and its helpers from that branch.
- Command: `uv run pytest backend/tests/query_benchmark/ownership/test_plain_cypher.py -s -p no:cacheprovider --no-cov -q --durations=10 --session-timeout=14400`
- Result of the run: 9 tests passed in 1,955 seconds. The setup took 1,384 seconds: the load of the data set, then the write of the owner edges.
- Machine: AMD EPYC 9R45, 16 CPUs, 61 GiB of memory.
- Database: Neo4j `2026.10.1-enterprise` in a test container, with 4 GiB of heap and 4 GiB of page cache.
- Python 3.12.13.

The numbers hold noise. The VM is shared, and another implementation run used the same machine during this run. Each number comes from one run of the test.

### State of the test file after the spike

- The test file of the spike run is in commit `20978f3957` of this branch.
- After the spike, the test file was changed to use the common data set: its kinds, its layout and the variable `INFRAHUB_OWNERSHIP_BENCHMARK_DEVICES`. It measures the same operations as before.
- So the command above now runs on the common data set. A new run does not give the numbers of this section again.
- The changed test passed one time on 2026-11-12, with 50 devices and 2,400 interfaces: 9 tests passed in 88 seconds. That run gives no number for this file.
- The changed test was not run at full size.

### Results against each limit

Measured on the first data set of option E (interface → device → location).

| Criterion | Limit | Measured on the first data set of option E (10,000 devices, 480,000 interfaces) | Limit met |
|---|---|---|---|
| SC-003 | Owner filter on interfaces: first page of 50 with the count, under 2 seconds | 181 ms for 3,024 interfaces that match. 274 ms for 5,610. 2,551 ms for 59,900. 3,542 ms for 83,330. 8,717 ms for 210,860 (all 50 groups). | Met for the two small filters. Not met for 59,900 interfaces and more. |
| SC-004 | "No owner" filter on devices: first page with the count, under 2 seconds | 1,027 ms from the owners down. 3,537 ms with a walk up from each device. 5,606 devices match. | Met from the owners down. Not met with the walk up. |
| SC-005 | After a change of owners on a device or a profile, the next read of every node that inherits shows the new owners | The 48 interfaces of one device show the new owner at the next read. A profile is not measured. | Met for a device. Not known for a profile. |
| SC-006 | A page of 50 nodes with owners takes at most 100 ms longer | The read of the owners that apply to 50 nodes takes 11.4 to 14.7 ms in the database. | Met for the database read. The GraphQL layer is not in the number. |
| SC-009 | The owner check adds at most 10% to a mutation on one interface at depth 6 | The read of the owners adds 12.9%: 10.6 ms for the update alone, 11.9 ms with the read. | Not met. |
| SC-010 | A generator run over 10,000 owned nodes takes at most 10% longer | The read of the owners adds 10.5% to the total time of 10,000 upserts, and 8.2% to the median time of one upsert. | Not met on the total time. The difference to the limit is smaller than the noise. |

### Owner data of the run

Measured on the first data set of option E (interface → device → location).

The fixture of the data set gives no owner. The test writes these owner edges with Cypher on the default branch: 3,958 `HAS_OWNER` edges and 300 `HAS_NO_OWNER` edges.

- 2,500 devices (1 device in 4) have own owners. Each one has one of 40 groups, so each group has 62 or 63 devices. 1,250 of these devices have a second owner, which is the same group for all.
- 100 devices have "no owner".
- 1 location of level 1 has one group as owner. 1 location of level 3 below it has another group. 6 locations of level 5 have one group each.
- 200 interfaces have one group as own owner, and 200 interfaces have "no owner".
- All 50 account groups own nodes.
- 210,860 of the 480,000 interfaces have an owner, own or inherited. 5,606 of the 10,000 devices have no owner.
- The data set has no profile, no object template and no owner on an attribute.

The test computes the expected owners of each node in Python from the same rules. Each filter query returns the expected count.

### Method

- Each query is plain Cypher. No resolver, no product read query and no GraphQL layer is in the numbers, except for the mutations of SC-009 and SC-010.
- Each read has the branch filter and the time filter of the default branch. A read on another branch is not measured.
- Each read checks that the owner is active, so a deleted owner does not count.
- The walk to the parents follows the Parent relationship first, then the hierarchy parent. It stops at the first node with own owners or "no owner". The depth limit is 16 parents (PD-3).
- "From the owner down" starts at the owner vertex, takes the nodes that hold a `HAS_OWNER` edge to it, then goes down to the nodes that inherit. A step down follows only the relationships and the kinds on the way to the kind of the list.
- Each filter has two queries, as a list query has: one for the count and one for the page of 50, ordered by node ID. Each query has 1 run to warm up, then 7 measured runs.
- The db hits come from one `PROFILE` run of the query. They do not change with the load of the machine.

### SC-003: owner filter on interfaces, from the owner down

Measured on the first data set of option E (interface → device → location).

| Filter | Interfaces that match | Count: median (ms) | Page of 50: median (ms) | Count and page: median (ms) | Minimum (ms) | Maximum (ms) | db hits of the count |
|---|---|---|---|---|---|---|---|
| One group, own owner of interfaces | 200 | 15.8 | 14.9 | 30.9 | 29.9 | 31.5 | 80,604 |
| One group, own owner of devices | 3,024 | 91.0 | 89.6 | 180.6 | 173.3 | 235.8 | 188,321 |
| One group, owner of a location of level 3 | 5,610 | 135.0 | 139.1 | 274.1 | 269.5 | 287.2 | 288,120 |
| One group, second owner of 1 device in 8 | 59,900 | 1,269.0 | 1,288.1 | 2,551.1 | 2,543.4 | 2,787.7 | 2,318,178 |
| One group, owner of a location of level 1 | 83,330 | 1,742.2 | 1,804.9 | 3,541.7 | 3,525.7 | 3,570.6 | 3,236,327 |
| All 50 groups | 210,860 | 4,334.5 | 4,380.7 | 8,716.5 | 8,676.0 | 8,826.9 | 7,962,384 |

- The time grows with the number of interfaces that match: about 21 microseconds for each interface, for each of the two queries.
- With this cost, the count and the page together reach 2 seconds at about 47,000 interfaces. This number is computed from the rows above. It is not measured.
- A walk up from each interface, for the group that owns the location of level 1, takes 81.9 seconds for the count (one run). From the owner down, the same count takes 1.7 seconds.

### SC-004: "no owner" filter on devices

Measured on the first data set of option E (interface → device → location).

| Query | Devices that match | Count: median (ms) | Page of 50: median (ms) | Count and page: median (ms) | Minimum (ms) | Maximum (ms) |
|---|---|---|---|---|---|---|
| From the owners down, then the devices that the walk did not reach | 5,606 | 510.7 | 516.0 | 1,026.6 | 983.1 | 1,046.4 |
| Walk up from each device | 5,606 | 1,761.2 | 1,775.6 | 3,536.6 | 3,514.5 | 3,578.4 |

### SC-005: change of owners, then read

Measured on the first data set of option E (interface → device → location).

- The device `device-00000` has two groups as own owners. Its 48 interfaces inherit them.
- The test sets another group as the only owner of the device, with the write query of this branch (`OwnershipRepository.write`).
- The next read returns the new group for the 48 interfaces, with the device as the node that holds the owners.
- The storage holds no copy of the owners that apply. Each read walks to the parents.

| Step | Duration (ms) |
|---|---|
| Write of the owners of the device, one run | 342.5 |
| First read of the 48 interfaces after the write, one run | 406.2 |
| 30 more reads of the 48 interfaces, median | 3.1 (minimum 2.6, maximum 58.7) |

- The write is the first run of the write query in the test. The read is the first read after the write. The cause of their time is not known.
- Not measured: a change of owners on a profile. The data set has no profile, and the write query of this branch supports the node vertex only.

### SC-006: read of the owners that apply to a page of 50 nodes

Measured on the first data set of option E (interface → device → location).

Each row has 3 runs to warm up, then 30 measured runs.

| Page | Median (ms) | Minimum (ms) | Maximum (ms) | db hits |
|---|---|---|---|---|
| 50 devices, the first of the data set | 11.4 | 10.6 | 73.1 | 13,488 |
| 50 interfaces, owners from a location 6 parents above | 14.7 | 14.2 | 15.1 | 21,064 |
| 50 interfaces, no owner on the 6 parents | 13.6 | 13.3 | 13.9 | 20,464 |

- The number is one database query. It returns the ID of each owner and of the node that holds the owners.
- Not in the number: the read of the kind, the display label and the HFID of each owner, and the work of the GraphQL layer.

### SC-009: owner read before a mutation on one interface at depth 6

Measured on the first data set of option E (interface → device → location).

- The interface inherits its owners from a location 6 parents above it.
- The temporary check is one read of the owners that apply to the interface, before the update mutation. The mutation is the GraphQL update of the description of the interface.
- The test process runs the GraphQL request. No HTTP layer is in the number. The "today" numbers above go through the SDK client and the API, so "Update alone" does not compare with the "today" row of the update.
- 3 runs to warm up, then 200 measured runs. In each run, the update alone and the update with the read both run. Their order changes at each run.

| Operation | Median (ms) | Minimum (ms) | Maximum (ms) |
|---|---|---|---|
| Update alone | 10.6 | 9.2 | 248.6 |
| Read of the owners that apply | 1.2 | 1.0 | 50.7 |
| Read, then update | 11.9 | 10.1 | 382.9 |

- The read adds 12.9% on the medians. The limit is 10%.
- Not in the number: the read of the groups of the user, and the decision of the check.

### SC-010: owner read before each upsert of a generator run

Measured on the first data set of option E (interface → device → location).

- A generator writes each node with one upsert mutation ([generator.py, line 101](../../../python_sdk/infrahub_sdk/generator.py)). The test runs the upsert of 10,000 interfaces whose device has own owners.
- For each interface, the upsert alone and the upsert with the read both run. Their order changes at each interface.

| Operation | Total (s) | Median (ms) | Minimum (ms) | Maximum (ms) |
|---|---|---|---|---|
| Upsert alone | 137.2 | 13.4 | 12.3 | 448.8 |
| Read of the owners that apply | 7.9 | 0.8 | 0.7 | 4.4 |
| Read, then upsert | 151.6 | 14.5 | 13.1 | 825.3 |

- The read adds 10.5% on the totals and 8.2% on the medians. The limit is 10%.
- The totals hold slow runs of up to 825 ms, so they hold more noise than the medians.
- Not measured: a whole generator run with the read of the owners. The "today" table above has a whole generator run that writes one node, with no read of the owners. The share that the read adds to a whole run is not known.

### Index on the branch of `HAS_NO_OWNER` and the diff query

Measured on the first data set of option E (interface → device → location).

- The test writes 1,000 owner changes with a branch name that is not the default branch: 500 devices get an owner and 500 devices get "no owner".
- The diff query lists the nodes whose owner edges changed on the branch. It has one pattern for each holder (node, attribute, `OwnerSet`) and each edge type, with an index hint where the index exists.
- The test measures the query with the index and after a drop of the index. Then it adds 80,000 `HAS_NO_OWNER` edges on the default branch and measures both again.
- Each row has 3 runs to warm up, then 30 measured runs.

| Index on `HAS_NO_OWNER(branch)` | `HAS_NO_OWNER` edges in the database | Changes on the branch | Median (ms) | Minimum (ms) | Maximum (ms) | db hits |
|---|---|---|---|---|---|---|
| Yes | 800 | 1,000 | 13.4 | 12.8 | 39.1 | 19,042 |
| No | 800 | 1,000 | 14.5 | 13.8 | 40.3 | 20,561 |
| Yes | 80,800 | 1,000 | 13.1 | 12.7 | 365.3 | 19,042 |
| No | 80,800 | 1,000 | 109.7 | 101.2 | 173.7 | 413,525 |

- With the index, the cost depends on the changes of the branch only.
- Without the index, the cost grows with the number of `HAS_NO_OWNER` edges in the database: 20,561 db hits with 800 edges, and 413,525 db hits with 80,800 edges.

### Lookup of an `OwnerSet` vertex by its key

Measured on the first data set of option E (interface → device → location).

- The test creates 1,019 `OwnerSet` vertices: one on each of 1,000 devices, for the same relationship, and 19 more on one of these devices.
- The lookup matches the node by its ID, then reads the `HAS_OWNER_SET` edges of the node. No index exists on `OwnerSet`.
- Each row has 3 runs to warm up, then 30 measured runs.

| Node | Median (ms) | Minimum (ms) | Maximum (ms) | db hits |
|---|---|---|---|---|
| Node with 20 `OwnerSet` vertices | 0.4 | 0.4 | 7.5 | 69 |
| Node with 1 `OwnerSet` vertex | 0.4 | 0.3 | 1.8 | 12 |

### Decisions of the spike

Measured on the first data set of option E (interface → device → location).

1. Owner filter (research R-6). PD-8 of [provisional-decisions.md](provisional-decisions.md) fixes this decision.
   - The filter by owner starts from the owner and goes down to the nodes that inherit.
   - The "no owner" filter starts from all owners, goes down, and returns the nodes that the walk did not reach.
   - No index of the owners that apply is built, because it needs approval.
   - SC-003 is met when the filter matches up to 5,610 interfaces. It is not met when the filter matches 59,900 interfaces or more.
   - What meets SC-003 for a larger filter is not decided.
   - Decision of 2026-11-16 (PD-8): the filter stays as built, with no index. The limit of the full-size run is accepted for this phase ("Success criteria").
2. Index on `HAS_NO_OWNER(branch)`: the index stays. Task T011 added it.
   - With the index, the diff query costs 13.1 to 13.4 ms for 1,000 changes, and the cost does not grow with the other `HAS_NO_OWNER` edges.
   - The cost of option B on this data set is not known. This run cannot measure option B. The benchmark of 2026-11-09 gave 14.3 ms for option B on other data and another machine.
   - Decision of 2026-11-27: "no owner" is a `HAS_OWNER` edge to `NoOwner`, so the diff query reads it through `owner_branch`, and the index on `HAS_NO_OWNER(branch)` is removed. Nobody measured the diff query after this change.
3. Lookup of an `OwnerSet` by its key: no index. The lookup costs 0.4 ms and 69 db hits for a node with 20 `OwnerSet` vertices.
4. Task T023: the spike chose no index of the owners that apply. So no new database structure needs approval, and no task is added to [tasks.md](tasks.md).

### Limits of these numbers

- The numbers come from one run on a shared VM. Another implementation run used the machine at the same time.
- For SC-009 and SC-010, the difference between the result and the limit of 10% is smaller than the spread of the runs. The minimum of "update alone" is 13% below its median.
- The numbers are for the default branch. A read on another branch must take the latest edge of each pair of vertices, and its cost is not measured.
- The owners that a profile or an object template gives are not in the data set. The walk does not read profiles. Their cost in the filter and in the read is not measured.
- The owners of attributes and of relationship fields are not in the filter numbers.
- The numbers are for the first data set of option E. The tasks T144 and T145 measure the product queries and the change check again, on the common data set.

## Change check of Infrahub Community: SC-008 and FR-043 (task T085)

- The change check adds 8.8 to 13.7 microseconds to a mutation of one interface. This is 0.05% to 0.08% of the time of the mutation. SC-008 allows 5%.
- A mutation runs the same database queries with the change check and without it (FR-043).
- The times of a whole mutation with and without the change check differ by 2.1% less to 1.5% more. These differences have both signs and are larger than the time of the change check alone. So they show the change between two runs, not the change check.

### Method

- The test is `backend/tests/query_benchmark/ownership/test_change_check_overhead.py` (a later pull request adds this file). It uses the common data set of [conftest.py](../../../backend/tests/query_benchmark/ownership/conftest.py).
- The mutations run in the test process, through the GraphQL schema and without the HTTP layer. A mutation through the API takes longer, so the share of the change check through the API is smaller than in the table below.
- "Without a session" is a request without an account session. Such a request builds no change set and calls no change check.
- "With a session" is a request with the session of the administrator account. It builds the change set and calls the change check of Infrahub Community.
- The two requests differ by the account session, not by the change check alone. The test that counts the queries shows that both run the same database queries.
- A run with a session and a run without a session alternate. The path that runs first changes at each run. The first call of each path is not measured.
- "Change check alone" is the time of the function that a mutation calls for the change check, without the mutation. It covers the build of the change set, the lookup of the change check of the process, and the check. The change set comes from the changelog of a real create and of a real update of an interface, and from one node for the delete.

### Run and data set

- Run: 2026-11-13, from 07:52 to 08:11 UTC. Result of the test runner: `2 passed, 1 warning in 1152.36s (0:19:12)`.
- Code: the commit that adds this section. Its parent is `a4d1923fa7` on the branch `rbac-owners-option-e-impl-infp-753`.
- Real size of the data set: the full reference data set of the spec.
  - 10,000 devices
  - 480,000 interfaces (48 for each device)
  - 363 locations in a hierarchy 5 levels deep
  - 50 account groups
  - No node has an owner.
- A first run with 20 devices and 960 interfaces on 2026-11-13 at 00:47 UTC proved that the test passes: `2 passed, 1 warning in 39.60s`. No number of that run is compared.
- A first attempt at full size, from 07:33 to 07:51 UTC, failed during the load of the data set. The database returned `BlockStorageEngine: Failed to apply transaction`. Another benchmark run loaded its data set on the same machine at that time. The cause of the error is not known.

### Results

| Mutation of one interface | Runs | Median without a session | Median with a session | Difference | Change check alone, median of 1,000 calls | Share of the mutation without a session |
|---|---|---|---|---|---|---|
| Create | 20 | 16.68 ms | 16.93 ms | 1.5% more | 13.7 microseconds | 0.08% |
| Update the description | 20 | 17.07 ms | 16.97 ms | 0.6% less | 10.0 microseconds | 0.06% |
| Delete | 20 | 17.72 ms | 17.34 ms | 2.1% less | 8.8 microseconds | 0.05% |

- Database queries: for each of the three mutations, the test compares the number of queries of each query name with a session and without a session. The numbers are equal.
- The test also counts the calls of the change check: 3 calls for the 3 mutations with a session, and no call without a session.

### Comparison with SC-008 and FR-043

- SC-008, at most 5% more time because of the change check: met for the three mutations of this test. The change check alone takes 0.05% to 0.08% of the mutation.
- The "today" table gives 22.9 to 38.5 ms for the same mutations through the API. Against these times, the change check alone is about 0.04%.
- FR-043, no database read in the Community check: the query numbers are equal. A unit test also calls the Community check with a database handle that fails on any use.

### How to run the measure again

```bash
uv run pytest backend/tests/query_benchmark/ownership/test_change_check_overhead.py -s -p no:cacheprovider --no-cov -q --session-timeout=10800
```

- `INFRAHUB_OWNERSHIP_BENCHMARK_DEVICES` sets a smaller number of devices. The test prints the real size above the table.

### Environment of the run

- Machine: the shared VM of the "today" run.
- The load average of the last minute was between 3.1 and 7.4 at 10 checks, one every 2 minutes. It is not known if another run used the machine during this run.
- Database: Neo4j `2026.10.1-enterprise` in a container, with a heap of 4 GiB and a page cache of 4 GiB. Python 3.12.13.

### Limits of these numbers

- One run at full size gives the numbers.
- Each mutation changes one interface. The create sends two fields, and the update sends one field. A mutation that changes many fields or many links builds a larger change set. Its time is not measured.
- The numbers are for the change check of Infrahub Community. They do not measure a check that reads owners (SC-009 and SC-010).
- The numbers are for the default branch.

## Source filter and the list query (task T136)

Date: 2026-11-13. The test is a temporary component test. It is not in the repository.

- Data set: 3,000 `TestTenant` nodes of the test schema `tests/helpers/schema/ownership.py`. 30 nodes have one source, the same account group. This is not the reference data set.
- Query: `NodeGetListQuery` with the filter `node_metadata__sources__ids` and a page of 5 nodes, run one time with `PROFILE`.

| Branch | Filter | Rows of the page | db hits |
|---|---|---|---|
| default branch | one source | 5 | 512 |
| default branch | none | 5 | 36,010 |
| another branch | one source | 5 | 662 |
| another branch | none | 5 | 6,091 |

- With the filter, the plan starts with `NodeIndexSeek` on `source:Node(uuid)`, then expands the `HAS_SOURCE` edges to the 30 nodes. It has no scan of the nodes of the kind.
- The filter needs the hint `USING INDEX SEEK source:Node(uuid)`. With `USING INDEX` on 400 nodes, the planner chose a scan of the whole index of node IDs.
- Not measured: the time, the reference data set, a filter on several sources, and the source filter together with an owner filter. With an owner filter, the source filter starts from the nodes that the owner filter gives.

## Full-size run of the common benchmark (tasks T144 and T145)

- SC-003 is not met for an owner filter that matches 101,462 interfaces or more. It is met for a filter that matches up to 59,900 interfaces.
- SC-009 is not met. The read of the owners adds 20.4% to the update of one interface. The limit is 10%.
- SC-004, SC-005 and SC-008 are met.
- SC-006 is below its limit on the medians, but the runs cannot prove it. See "Success criteria".
- SC-010 is below its limit on the medians and above it on the totals. The totals of the first run were below the limit. See "Success criteria".
- A page of 50 interfaces of some devices takes 4.0 seconds without owners. The owners and the sources add 18.5 to 34.1 ms to it.
- All 10 tests passed. The test of the query plans passed for the first time at this size. See "Query plans".
- The numbers of this section come from the second full-size run. See "First run and second run".

### Run and data set

- Run: 2026-11-14, from 11:50:50 to 13:02:11 UTC. Result of the test runner: `10 passed, 1 warning in 4272.90s (1:11:12)`.
- Code: commit `0f54daade5` of the branch `rbac-owners-option-e-impl-infp-753`.
  - The work tree was at commit `fc07690f315da522a00901da438781aa12ed38d2`. This commit adds one Markdown file to `0f54daade5` and changes no code.
- Test: `backend/tests/query_benchmark/ownership/test_owner_queries.py` (a later pull request adds this file). The file is the same in each branch that implements owners. The parts that depend on the storage are in `option_specific.py` of the same folder, which the same later pull request adds.
- Real size of the data set: the full reference data set of the spec, from [conftest.py](../../../backend/tests/query_benchmark/ownership/conftest.py).
  - 10,000 devices
  - 480,000 interfaces (48 for each device)
  - 363 locations in a hierarchy 5 levels deep
  - 50 account groups
- The test writes the owners and the sources through GraphQL, then measures. After the write:
  - 242,528 interfaces have an owner, own or inherited. 237,472 interfaces have no owner.
  - 4,946 devices have no owner.
  - 400 interfaces have a source.
  - 100 devices use one profile that gives owners.
- The run was alone on the VM. No other test run of this project was active.
  - Before the run, `pgrep` found no pytest process.
  - At 12:01 and at 12:27 UTC, `pgrep` found only the pytest process of this run. No other check ran.
  - Three idle containers of another session stayed up during the run: a database, a cache and a message queue.
- Load average of the last 1, 5 and 15 minutes:
  - Before the run, at 11:50:50 UTC: 0.31, 0.76, 1.58
  - During the data load, at 12:00:40 UTC, before the first test ended: 3.62, 3.07, 2.42
  - After the run, at 13:02:11 UTC: 1.36, 1.44, 1.48
- Disk: `df -h /` gave 18G available of 96G before the run and after the run.
- Machine: 16 CPUs (AMD EPYC 9R45) and 61 GiB of memory.
- Database: Neo4j `2026.10.1-enterprise` in a test container, with a heap of 4 GiB and a page cache of 4 GiB.
- Python 3.12.13. The application, the SDK client and the test run in one process.

### Method

- Each sample is the time of one GraphQL request of the SDK client, which goes through the API.
- Each measure has one run to warm up. That run is not in the numbers.
- Each test checks the counts and the owners that the API returns. So no number comes from a request that returned a wrong result.
- SC-009 and SC-010 use a test implementation of the change check that reads owners. It refuses nothing.
  - The check reads the owners that apply to each node that the change set names. The read runs in the transaction of the mutation.
  - The check does not read the groups of the user, and it takes no decision.
  - For each sample, the mutation runs one time without the read and one time with the read. The order changes at each sample.
- "Change check alone" of SC-008 is the time of the change check of Infrahub Community without the mutation. Each sample is the median of many direct calls.

### Results

All times are in milliseconds.

| Measure | Criterion | Limit | Operation | Samples | Median | Minimum | Maximum |
|---|---|---|---|---|---|---|---|
| `sc003_owner_filter_interface_group` | SC-003 | under 2,000 ms | one group, own owner of interfaces, 200 nodes match, first page of 50 with the count | 10 | 30.3 | 26.4 | 410.6 |
| `sc003_owner_filter_device_group` | SC-003 | under 2,000 ms | one group, own owner of devices, 3,024 nodes match, first page of 50 with the count | 10 | 118.5 | 107.5 | 557.7 |
| `sc003_owner_filter_profile_group` | SC-003 | under 2,000 ms | one group, given by a profile of devices, 4,800 nodes match, first page of 50 with the count | 10 | 169.2 | 166.4 | 174.6 |
| `sc003_owner_filter_second_device_group` | SC-003 | under 2,000 ms | one group, second own owner of 1 device in 8, 59,900 nodes match, first page of 50 with the count | 10 | 1,795.4 | 1,778.1 | 1,805.9 |
| `sc003_owner_filter_region_group` | SC-003 | under 2,000 ms | one group, owner of the region 6 parents above, 101,462 nodes match, first page of 50 with the count | 10 | 3,149.7 | 3,140.8 | 3,156.3 |
| `sc003_owner_filter_all_groups` | SC-003 | under 2,000 ms | all 50 groups, 242,528 nodes match, first page of 50 with the count | 10 | 7,358.5 | 7,330.8 | 7,922.7 |
| `sc003_no_owner_filter_interfaces` | SC-003 | under 2,000 ms | "no owner" filter, 237,472 nodes match, first page of 50 with the count | 10 | 7,727.9 | 7,698.1 | 8,457.0 |
| `sc003_source_filter_interfaces` | SC-003 | under 2,000 ms | one source, 400 nodes match, first page of 50 with the count | 10 | 21.9 | 19.1 | 44.0 |
| `sc004_no_owner_filter_devices` | SC-004 | under 2,000 ms | "no owner" filter, 4,946 nodes match, first page of 50 with the count | 10 | 1,045.7 | 1,020.4 | 1,521.5 |
| `sc005_device_owner_write` | SC-005 |  | one device with 48 interfaces: write of the owners of the device | 11 | 20.9 | 18.7 | 627.8 |
| `sc005_device_next_read` | SC-005 | the read shows the new owners | one device with 48 interfaces: read of the owners of the interfaces after the write | 11 | 4,021.8 | 3,938.4 | 4,437.5 |
| `sc005_profile_owner_write` | SC-005 |  | one profile that 100 devices use: write of the owners that the profile gives | 11 | 17.7 | 17.1 | 117.0 |
| `sc005_profile_next_read` | SC-005 | the read shows the new owners | one profile that 100 devices use: read of the owners of the devices and of the interfaces of one device after the write | 11 | 4,103.4 | 4,031.0 | 5,247.4 |
| `sc006_interface_page_baseline` | SC-006 |  | 50 interfaces that inherit from the region 6 parents above, without owners and sources | 50 | 3,999.7 | 3,917.8 | 4,430.3 |
| `sc006_interface_page_node_owners` | SC-006 | baseline + 100 ms | 50 interfaces that inherit from the region 6 parents above, with the owners of the node | 50 | 4,020.0 | 3,963.4 | 4,481.3 |
| `sc006_interface_page_attribute_owners` | SC-006 | baseline + 100 ms | 50 interfaces that inherit from the region 6 parents above, with the owners of an attribute | 50 | 4,023.6 | 3,947.3 | 4,450.1 |
| `sc006_interface_page_relationship_owners` | SC-006 | baseline + 100 ms | 50 interfaces that inherit from the region 6 parents above, with the owners of a relationship | 50 | 4,021.0 | 3,955.3 | 4,419.1 |
| `sc006_interface_page_sources` | SC-006 | baseline + 100 ms | 50 interfaces that inherit from the region 6 parents above, with the sources of the node | 50 | 4,018.2 | 3,940.8 | 4,483.4 |
| `sc006_interface_page_all` | SC-006 | baseline + 100 ms | 50 interfaces that inherit from the region 6 parents above, with the owners of the node and of two fields, and the sources | 50 | 4,033.8 | 3,963.9 | 4,462.2 |
| `sc006_device_page_baseline` | SC-006 |  | the first 50 devices, without owners and sources | 50 | 55.4 | 48.3 | 478.8 |
| `sc006_device_page_all` | SC-006 | baseline + 100 ms | the first 50 devices, with the owners of the node and of two fields, and the sources | 50 | 116.2 | 109.0 | 540.9 |
| `sc008_create_interface` | SC-008 | today + 5% | create of one interface of a device with no owner | 50 | 30.2 | 25.3 | 172.0 |
| `sc008_update_interface` | SC-008 | today + 5% | update of one interface of a device with no owner | 50 | 18.9 | 15.7 | 137.2 |
| `sc008_delete_interface` | SC-008 | today + 5% | delete of one interface of a device with no owner | 50 | 20.5 | 18.8 | 188.1 |
| `sc008_change_check_alone_create` | SC-008 |  | change check of one create, without the mutation, a sample is the median of many calls | 10 | 0.014 | 0.014 | 0.015 |
| `sc008_change_check_alone_update` | SC-008 |  | change check of one update, without the mutation, a sample is the median of many calls | 10 | 0.011 | 0.011 | 0.011 |
| `sc008_change_check_alone_delete` | SC-008 |  | change check of one delete, without the mutation, a sample is the median of many calls | 10 | 0.009 | 0.009 | 0.009 |
| `create_interface_with_owners` |  |  | create of one interface of a device with no owner, with own owners, one field owner and one source | 50 | 27.6 | 25.5 | 568.8 |
| `delete_interface_with_owners` |  |  | delete of one interface of a device with no owner, with own owners, one field owner and one source | 50 | 19.4 | 17.8 | 21.5 |
| `sc009_update_baseline` | SC-009 |  | update of one interface that inherits from the region 6 parents above, no read of owners | 200 | 15.3 | 13.9 | 29.8 |
| `sc009_update_with_owner_read` | SC-009 | baseline + 10% | update of one interface that inherits from the region 6 parents above, the change check reads the owners that apply | 200 | 18.4 | 16.6 | 138.4 |
| `sc009_owner_read_alone` | SC-009 |  | the change check alone | 200 | 3.0 | 2.5 | 121.7 |
| `sc010_upsert_baseline` | SC-010 |  | upsert of 10,000 interfaces whose device has own owners, one upsert for each node, no read of owners | 10,000 | 19.1 | 17.6 | 551.2 |
| `sc010_upsert_with_owner_read` | SC-010 | baseline + 10% on the totals | upsert of 10,000 interfaces whose device has own owners, one upsert for each node, the change check reads the owners that apply | 10,000 | 20.8 | 18.9 | 590.9 |
| `sc010_owner_read_alone` | SC-010 |  | the change check alone | 10,000 | 1.6 | 1.1 | 5.4 |
| `create_service_baseline` |  |  | create of one node without an object template | 50 | 10.0 | 8.9 | 82.6 |
| `create_service_from_template` |  |  | create of one node from an object template that gives one owner | 50 | 17.1 | 16.0 | 405.7 |
| `branch_owner_write` |  |  | write of the owners of one device on a branch | 1,000 | 14.4 | 12.3 | 347.2 |
| `branch_owner_read` |  |  | a branch with owner changes on 100 devices: read of the owners of these devices | 10 | 59.1 | 55.1 | 134.0 |
| `branch_diff` |  |  | a branch with owner changes on 100 devices: update of the diff | 10 | 7,618.8 | 7,314.9 | 8,416.4 |
| `branch_merge` |  |  | a branch with owner changes on 100 devices: merge, after the update of the diff | 10 | 24,361.8 | 23,742.9 | 25,801.5 |

### Query plans

The test plans each owner query with `EXPLAIN`, then runs it one time with `PROFILE` in a transaction that it rolls back.

| Query | Scans of a whole label, relationship type or index | Database hits |
|---|---|---|
| read of the stored owner states of a page of nodes | none | 3,520 |
| read of the stored owner states of some nodes, of their parents and of their profiles | none | 3,105 |
| read of the stored owner states of one node and of its attributes | none | 637 |
| read of the labels of the owners of an input | none | 10 |
| write of the owners of a node | `NodeByLabelScan:NoOwner` | 26 |
| write of the owners of an attribute | `NodeByLabelScan:NoOwner` | 79 |
| write of the owners of a relationship | `NodeByLabelScan:NoOwner` | 57 |
| write of the sources of a node | `NodeByLabelScan:NoOwner` | 26 |
| close of the owner edges of a deleted node | `NodeByLabelScan:NoOwner` | 83 |
| owner filter on interfaces, page | none | 12,335 |
| owner filter on interfaces, count | none | 11,935 |
| "no owner" filter on devices, page | `DirectedRelationshipTypeScan:HAS_TARGET_OWNER_SET`, `NodeByLabelScan:BenchDevice` | 2,028,566 |
| "no owner" filter on devices, count | `DirectedRelationshipTypeScan:HAS_TARGET_OWNER_SET`, `NodeByLabelScan:BenchDevice` | 2,023,805 |
| source filter on interfaces, page | none | 7,006 |
| source filter on interfaces, count | none | 6,206 |
| diff of the owner changes of a branch | `NodeByLabelScan:OwnerSet` | 455 |
| diff of the owner changes of one node | none | 90 |
| merge of the owner edges of a branch | `DirectedRelationshipTypeScan:HAS_OWNER_SOURCE`, `DirectedRelationshipTypeScan:HAS_TARGET_OWNER_SET`, `NodeByLabelScan:OwnerSet` | 1,201 |

- No plan has a scan of all nodes (`AllNodesScan`).
- The test passed. No plan has a scan outside the accepted list of `option_specific.py`.
- In the first run, the test failed because the plan of "diff of the owner changes of a branch" has the scan `NodeByLabelScan:OwnerSet`. The accepted list did not have it for this query.
- Commit `3232ec2960` added the scan to the accepted list for this query. The reasons:
  - The whole query costs 455 database hits, so the label has fewer than 455 vertices in this data set.
  - An `OwnerSet` vertex exists only for a relationship with own owners, and for each set of owners that a profile or an object template gives. A node or an attribute with own owners needs no `OwnerSet` vertex.
  - The accepted list already had the same scan for the merge query.
- The scans of each query are the same in the two runs. The database hits are the same, except for the "no owner" filter on devices: 2,031,164 and 2,026,403 in the first run.
- Not examined: the operators of the plan around the scan. The benchmark does not save the plan, and the database of the run does not exist after the run.
- Not measured: the diff query with many `OwnerSet` vertices. The cost of the scan grows with their number.
- The "no owner" filter on devices costs 2.0 million database hits. Its plan scans all nodes of the kind, which the accepted list had before the first run.

### Success criteria

The limits come from [spec.md](spec.md). Each relative value uses the baseline measure of the same run.

| Criterion | Limit of spec.md | Measured value | Result |
|---|---|---|---|
| SC-003 | The owner filter on interfaces returns the first page of 50, with the correct count, in under 2 seconds | Median 30.3 ms for 200 interfaces that match. 118.5 ms for 3,024. 169.2 ms for 4,800. 1,795.4 ms for 59,900 (maximum 1,805.9 ms). 3,149.7 ms for 101,462. 7,358.5 ms for 242,528 (all 50 groups). | Not met for 101,462 interfaces or more. Met up to 59,900. The decision of 2026-11-16 accepts this limit for this phase (PD-8). |
| SC-004 | The "no owner" filter on devices returns the first page, with the correct count, in under 2 seconds | Median 1,045.7 ms, minimum 1,020.4 ms, maximum 1,521.5 ms. 4,946 devices match. | Met |
| SC-005 | After a change of owners on a device or a profile, the next read of every node that inherits from it shows the new owners | Device: 11 writes, each with a read of its 48 interfaces. Profile that 100 devices use: 11 writes, each with a read of the 100 devices and of the 48 interfaces of one device. Each read returned the new owners. | Met |
| SC-006 | A page of 50 nodes with their owners takes at most 100 ms longer than the same page without owners | Page of 50 interfaces, baseline 3,999.7 ms: 18.5 to 34.1 ms more on the medians, and 9.5 to 70.5 ms more on the means. Page of 50 devices, baseline 55.4 ms: 60.8 ms more on the medians, and 116.5 ms more on the means. | Inside the noise |
| SC-008 | On Infrahub Community, a mutation takes at most 5% longer than today because of the change check | The change check alone takes 0.014 ms for a create, 0.011 ms for an update and 0.009 ms for a delete. This is 0.04% to 0.06% of the median of the mutation in the same run (30.2, 18.9 and 20.5 ms). | Met |
| SC-009 | The owner check adds at most 10% to a mutation on one interface at depth 6 | The read of the owners adds 20.4% on the medians (15.3 ms to 18.4 ms), 20.1% on the minimums and 24.6% on the totals. | Not met |
| SC-010 | A generator run over 10,000 owned nodes takes at most 10% longer than today | The read of the owners adds 13.0% on the totals of 10,000 upserts (195.9 s to 221.3 s), 8.8% on the medians (19.1 ms to 20.8 ms) and 7.4% on the minimums. | Inside the noise. The totals are above the limit in this run, and below it in the first run. |

- SC-003: the benchmark also files two other filters on interfaces under SC-003. The "no owner" filter takes 7,727.9 ms for 237,472 interfaces that match. The source filter takes 21.9 ms for 400 interfaces that match.
- SC-003, 59,900 interfaces that match: the two runs are below the limit, with 1,724.0 ms in the first run and 1,795.4 ms in this run.
- SC-006, page of interfaces: the medians, the minimums and the means are all below the limit. But the minimum and the maximum of each measure are about 500 ms apart, which is 5 times the limit. The baseline page uses the filter `device__ids` and takes 4.0 seconds without owners. The "today" table above has 4,584.1 ms for the same filter.
- SC-006, page of devices: the medians and the minimums are below the limit, and the means are above it. The measure with owners has samples of up to 540.9 ms.
- SC-006: the first run gave the same result. Its medians were 6.9 to 29.3 ms above the baseline for the page of interfaces, and 58.4 ms for the page of devices.
- SC-009: the result does not depend on the noise. The fastest read of the owners alone takes 2.5 ms, which is 16.6% of the median of the update without the read. The first run gave 20.7% on the medians.
- SC-010: the medians and the minimums are below the limit, by 1.2 and 2.6 points. The totals are above the limit, by 3.0 points.
  - The two runs do not agree on the totals. The first run gave 5.5% on the totals, 8.2% on the medians and 7.7% on the minimums.
  - So the totals moved by 7.5 points between the two runs, and the medians moved by 0.6 points.
  - The read of the owners alone has a total of 16.4 s, which is 8.4% of the baseline total. The difference of the two totals gives 13.0%. So the totals of this run hold a noise of 4.6 points or more.
  - The samples go from 17.6 ms to 590.9 ms.
  - The measure is 10,000 upsert mutations, one for each interface. It is not a whole generator run.
- Two runs give the numbers of SC-006 and SC-010. It is not known how many runs give a stable result.

### First run and second run

The first run used the code of commit `10cc705b6c` and had one failed plan test.

- First run: 2026-11-14, from 04:01:19 to 05:11:40 UTC. Result of the test runner: `1 failed, 9 passed, 1 warning in 4213.03s (1:10:13)`.
  - The load average was 0.48, 1.34, 1.51 before the run and 1.78, 1.45, 1.42 after the run.
  - The 9 tests that measure passed. `test_plans_of_the_owner_queries` failed. See "Query plans".
- Second run: the run of this section, on the code of commit `0f54daade5`.
- Four fix commits are between the two runs: `69838da53a`, `82d98b6c49`, `9eacb2e35f` and `0f54daade5`.
- The two runs use the same test file, the same data set and the same machine.
- Each value is a median, in milliseconds. The difference uses the values before they are rounded.

| Measure | First run | Second run | Difference |
|---|---|---|---|
| `sc003_owner_filter_interface_group` | 31.0 | 30.3 | -2.2% |
| `sc003_owner_filter_device_group` | 113.5 | 118.5 | +4.4% |
| `sc003_owner_filter_profile_group` | 161.7 | 169.2 | +4.6% |
| `sc003_owner_filter_second_device_group` | 1,724.0 | 1,795.4 | +4.1% |
| `sc003_owner_filter_region_group` | 3,020.5 | 3,149.7 | +4.3% |
| `sc003_owner_filter_all_groups` | 6,979.6 | 7,358.5 | +5.4% |
| `sc003_no_owner_filter_interfaces` | 7,439.0 | 7,727.9 | +3.9% |
| `sc003_source_filter_interfaces` | 19.0 | 21.9 | +15.3% |
| `sc004_no_owner_filter_devices` | 1,019.0 | 1,045.7 | +2.6% |
| `sc005_device_owner_write` | 22.8 | 20.9 | -8.3% |
| `sc005_device_next_read` | 3,917.8 | 4,021.8 | +2.7% |
| `sc005_profile_owner_write` | 17.8 | 17.7 | -0.1% |
| `sc005_profile_next_read` | 4,013.8 | 4,103.4 | +2.2% |
| `sc006_interface_page_baseline` | 3,942.0 | 3,999.7 | +1.5% |
| `sc006_interface_page_node_owners` | 3,951.6 | 4,020.0 | +1.7% |
| `sc006_interface_page_attribute_owners` | 3,960.1 | 4,023.6 | +1.6% |
| `sc006_interface_page_relationship_owners` | 3,954.4 | 4,021.0 | +1.7% |
| `sc006_interface_page_sources` | 3,948.9 | 4,018.2 | +1.8% |
| `sc006_interface_page_all` | 3,971.4 | 4,033.8 | +1.6% |
| `sc006_device_page_baseline` | 55.8 | 55.4 | -0.7% |
| `sc006_device_page_all` | 114.2 | 116.2 | +1.8% |
| `sc008_create_interface` | 30.2 | 30.2 | +0.1% |
| `sc008_update_interface` | 18.3 | 18.9 | +3.3% |
| `sc008_delete_interface` | 20.2 | 20.5 | +1.4% |
| `sc008_change_check_alone_create` | 0.015 | 0.014 | -6.7% |
| `sc008_change_check_alone_update` | 0.011 | 0.011 | +0.0% |
| `sc008_change_check_alone_delete` | 0.009 | 0.009 | +0.0% |
| `create_interface_with_owners` | 27.6 | 27.6 | -0.1% |
| `delete_interface_with_owners` | 19.2 | 19.4 | +1.0% |
| `sc009_update_baseline` | 15.0 | 15.3 | +2.2% |
| `sc009_update_with_owner_read` | 18.1 | 18.4 | +2.0% |
| `sc009_owner_read_alone` | 2.9 | 3.0 | +4.1% |
| `sc010_upsert_baseline` | 19.4 | 19.1 | -1.3% |
| `sc010_upsert_with_owner_read` | 21.0 | 20.8 | -0.7% |
| `sc010_owner_read_alone` | 1.7 | 1.6 | -2.8% |
| `create_service_baseline` | 10.2 | 10.0 | -2.1% |
| `create_service_from_template` | 15.3 | 17.1 | +11.8% |
| `branch_owner_write` | 13.9 | 14.4 | +4.0% |
| `branch_owner_read` | 56.5 | 59.1 | +4.4% |
| `branch_diff` | 7,355.8 | 7,618.8 | +3.6% |
| `branch_merge` | 23,816.4 | 24,361.8 | +2.3% |

- 36 of the 41 medians differ by less than 5%. 29 medians are higher in the second run, 10 are lower and 2 are equal.
- Two medians differ by more than 10%: `sc003_source_filter_interfaces` (19.0 ms to 21.9 ms) and `create_service_from_template` (15.3 ms to 17.1 ms).
- The measures that take more than one second are 1.5% to 5.4% slower in the second run. The cause was not examined: it can be the four fix commits or the state of the machine.

### SC-009 and SC-010: comparison with the spike

The spike used the first data set of option E. This run uses the common data set. So the comparison is indicative.

| Criterion | Value | Spike, 2026-11-12, first data set of option E | This run, 2026-11-14, common data set |
|---|---|---|---|
| SC-009 | Update without the read, median | 10.6 ms | 15.3 ms |
| SC-009 | Read of the owners alone, median | 1.2 ms | 3.0 ms |
| SC-009 | Update with the read, median | 11.9 ms | 18.4 ms |
| SC-009 | Added on the medians | 12.9% | 20.4% |
| SC-010 | 10,000 upserts without the read, total | 137.2 s | 195.9 s |
| SC-010 | 10,000 upserts with the read, total | 151.6 s | 221.3 s |
| SC-010 | Added on the totals | 10.5% | 13.0% |
| SC-010 | Read of the owners alone, median | 0.8 ms | 1.6 ms |
| SC-010 | Added on the medians | 8.2% | 8.8% |

The two measures differ by more than the data set:

- In the spike, the read was one plain Cypher query that ran before the mutation. In this run, the change check of the mutation does the read, in the transaction of the mutation, with the product code that applies the inheritance from profiles, object templates and parents.
- In the spike, the test process ran the GraphQL request without the HTTP layer. In this run, the request goes through the SDK client and the API.
- The cause of the longer read (3.0 ms against 1.2 ms for SC-009) was not examined.

- SC-009: both measures give the same result, not met.
- SC-010: the medians give 8.2% in the spike and 8.8% in this run. The totals give 10.5% in the spike and 13.0% in this run, so the two measures are above the limit on the totals.

### How to run the measure again

```bash
uv run pytest backend/tests/query_benchmark/ownership/test_owner_queries.py --session-timeout=14400 -s -p no:cacheprovider --no-cov -q
```

- `INFRAHUB_OWNERSHIP_BENCHMARK_DEVICES` sets a smaller number of devices. The test prints the real size above the table.
- `INFRAHUB_OWNERSHIP_BENCHMARK_RESULTS` names a JSON file that receives the measures and the plans.
- The test compares the scans with the accepted list only with 10,000 devices or more. A smaller graph gets other plans.
