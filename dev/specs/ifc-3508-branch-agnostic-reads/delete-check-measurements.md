# Delete check measurements for user story 4

These measurements compare the cost of today's node delete check with the cost of the window check on branch `agnostic-delete-check-ifc-3508`, and with two forms of a two-query check. They were run on 2026-11-12 to choose the design of the delete check for FR-014 to FR-017.

The two-query check is the design chosen: query 1 with one `CALL` subquery per cascade level for every delete, and query 2 only when the delete set holds a branch-agnostic node.

## How the measurements were run

- The measurement script was a pytest component test, copied into `backend/tests/component/core/` only while it ran and not committed.
- Each measurement ran in its own pytest process against a new Neo4j 2026.05 test container, with the process memory limited to 5 GB.
- The database held 50 branches, 100 standard groups with 100 tag members each (10,000 memberships) and 1,000 group actions, plus the nodes of the scenario.
- Database hits are the sum of `dbHits` in the `PROFILE` plan of every query sent during the measured step, from one profiled run.
- Times are the median of 5 runs that were not profiled. The S3 full deletes used 3 runs.
- "Check" is the delete check alone. "Full delete" is the check, then loading the nodes the cascade adds, then deleting each node, inside a transaction that is rolled back.
- In the measurement script, query 1 used the request branch's `get_query_filter_path` filter. The implementation uses the request branch's window filter instead.

## Approaches compared

- (a) Today's check on `stable`: a walk on the request branch that sends one query per cascade level and reads every link of the relationship identifiers it indexed.
- (b) The window check on branch `agnostic-delete-check-ifc-3508` at commit `0934010e0`.
- (c) The two-query check, with query 1 written as a quantified path pattern.
- (c, `ANY SHORTEST`) The same, with `ANY SHORTEST` added to the path pattern.
- (d) The two-query check, with query 1 written as one `CALL` subquery per cascade level.

## Scenarios

- S1: delete a `CoreStandardGroup` (branch-aware) with 10 tag members.
- S2: delete a `CoreAccountGroup` (branch-agnostic) with 10 account members.
- S5: delete a `CoreAccountGroup` that 20 `CoreGroupAction` nodes require. The delete is refused.
- S6: a branch-aware root cascades to a branch-aware mid, which cascades to a branch-agnostic leaf. On branch `spike-s6`, a holder node has a required relationship to the leaf. The expected result is a refusal that names `spike-s6`.
- S4: branch-aware kinds `D0` to `D5`, each with a cascade relationship to the next. Each level holds W nodes, each linked to every node of the next level. A delete that starts at depth 5 cascades to 5W + 1 nodes over W⁵ paths to the deepest level.
- S3: a branch-aware root cascades to 100 branch-aware mids, each of which cascades to 100 branch-agnostic leaves: 10,101 nodes, 10,000 of them branch-agnostic. The smaller form has 10 mids and 1,011 nodes.

## Results for single-node deletes (S1, S2, S5)

Delete check:

| Approach | S1 | S2 | S5 (refused) |
|---|---|---|---|
| (a) | 72,424 hits, 43.7 ms | 72,424 hits, 40.6 ms | 72,424 hits, 34.5 ms |
| (b) | 359 hits, 2.1 ms | 359 hits, 2.4 ms | 1,380 hits, 28.7 ms |
| (c) | 181 hits, 3.1 ms | 690 hits in 2 queries, 12.4 ms | 3,110 hits in 2 queries, 26.7 ms |
| (c, `ANY SHORTEST`) | 181 hits, 5.1 ms | 690 hits, 7.9 ms | 3,110 hits, 27.1 ms |
| (d) | 181 hits, 3.0 ms | 690 hits in 2 queries, 6.5 ms | 3,110 hits in 2 queries, 26.4 ms |

Full delete:

| Approach | S1 | S2 | S5 (refused) |
|---|---|---|---|
| (a) | 74,892 hits, 93.5 ms | 74,705 hits, 54.1 ms | 73,094 hits, 36.8 ms |
| (b) | 2,807 hits, 53.5 ms | 2,640 hits, 17.3 ms | 2,050 hits, 29.1 ms |
| (c) | 2,659 hits, 50.0 ms | 2,981 hits, 22.3 ms | 3,830 hits, 23.7 ms |
| (d) | 2,659 hits, 46.9 ms | 2,981 hits, 24.4 ms | 3,830 hits, 24.8 ms |

Today's check reads 72,424 hits for every one of these deletes because it reads every link of the indexed relationship identifiers, including the 10,000 memberships that the deleted group does not hold.

## Results for a cascade into a branch-agnostic node with a required peer on another branch (S6)

| Approach | Delete check | Full delete | Result |
|---|---|---|---|
| (a) | 192 hits, 4.5 ms | 3,307 hits, 150.9 ms | Deletes 3 nodes and leaves the holder's required link without a peer on `spike-s6` |
| (b) | 1,760 hits in 3 queries, 17.6 ms | 2,161 hits, 23.7 ms | Refused |
| (c) | 934 hits in 2 queries, 16.6 ms | 1,501 hits, 26.8 ms | Refused |
| (c, `ANY SHORTEST`) | 1,232 hits, 23.3 ms | not run | Refused |
| (d) | 1,181 hits in 2 queries, 17.7 ms | 1,585 hits, 15.3 ms | Refused |

## Results for layered cascades (S4)

Depths 1 and 2 are left out. At those depths, the profiled counts include hits that do not come from the measured step: (d) reported 1,535,405 hits for an 11-node check at width 10. At depths 3 to 5, the check runs and separate plan runs gave the same counts.

Delete check at width 5 (16, 21 and 26 nodes; 125, 625 and 3,125 paths to the deepest level):

| Approach | Depth 3 | Depth 4 | Depth 5 |
|---|---|---|---|
| (a) | 37,128 hits, 18.4 ms | 49,504 hits, 18.7 ms | 51,980 hits, 15.8 ms |
| (b) | 24,854 hits, 76.0 ms | 38,025 hits, 111.7 ms | 48,720 hits, 142.5 ms |
| (c) | 21,067 hits, 12.8 ms | 106,716 hits, 37.4 ms | 533,484 hits, 88.2 ms |
| (c, `ANY SHORTEST`) | 26,949 hits, 14.6 ms | 28,153 hits, 16.8 ms | 27,814 hits, 22.5 ms |
| (d) | 8,254 hits, 9.2 ms | 11,971 hits, 10.2 ms | 14,179 hits, 8.7 ms |

Delete check at width 10 (31, 41 and 51 nodes; 1,000, 10,000 and 100,000 paths to the deepest level):

| Approach | Depth 3 | Depth 4 | Depth 5 |
|---|---|---|---|
| (a) | 513,815 hits, 109.0 ms | 684,916 hits, 141.1 ms | 702,027 hits, 141.8 ms |
| (b) | 151,248 hits, 451.0 ms | 231,558 hits, 632.9 ms | 297,668 hits, 828.0 ms |
| (c) | 158,895 hits, 43.2 ms | 1,594,194 hits, 204.8 ms | 15,940,495 hits, 1,969.4 ms |
| (c, `ANY SHORTEST`) | 50,424 hits, 22.7 ms | 200,418 hits, 83.9 ms | 102,704 hits, 338.1 ms |
| (d) | 31,899 hits, 16.3 ms | 46,816 hits, 18.7 ms | 54,849 hits, 21.7 ms |

Full delete at depth 5:

| Approach | Width 5 (26 nodes) | Width 10 (51 nodes) |
|---|---|---|
| (a) | 377,195 hits, 207.2 ms | 3,494,763 hits, 918.1 ms |
| (b) | 316,438 hits, 302.0 ms | 721,648 hits, 1,152.5 ms |
| (c) | 711,800 hits, 260.1 ms | 16,151,484 hits, 2,404.9 ms |
| (d) | 259,805 hits, 179.5 ms | 157,152 hits, 274.0 ms |

The steps after the check are the same code for every approach, but the full delete for (a) at width 10 costs 2.79 million hits more than its check, against 102,303 for (d). The cause is not known.

The hits of (c) grow with the number of cascade paths, about ten times per level at width 10. The hits of (d) grow with the number of nodes.

## Results for a cascade of 10,101 nodes with 10,000 branch-agnostic nodes (S3)

Delete check. The process held 845 MB before the check started:

| Approach | Hits | Queries | Time | Peak process memory |
|---|---|---|---|---|
| (a) | 1,422,153 | 3 | 442 ms | 1,000 MB |
| (b) | 28,044,628 | 106 | 389 s | 1,953 MB |
| (c) | 1,503,178 | 2 | 469 ms | 860 MB |
| (c, `ANY SHORTEST`) | 1,981,304 | 2 | 928 ms | 859 MB |
| (d) | 1,539,318 | 2 | 565 ms | 859 MB |

Full delete of 10,101 nodes:

- (a), (c) and (d): the Python process passed the 5 GB limit and the kernel stopped it.
- (b): Neo4j refused the transaction with `MemoryPoolOutOfMemoryError`, because it passed the 716.8 MiB limit set by `dbms.memory.transaction.total.max`.

Full delete of 1,011 nodes:

| Approach | Hits | Time | Peak process memory |
|---|---|---|---|
| (a) | 1,042,653 | 3,521.8 ms | 1,596 MB |
| (b) | 1,353,929 | 9,403.3 ms | 1,526 MB |
| (c) | 1,119,658 | 4,054.2 ms | 1,588 MB |
| (d) | 1,124,022 | 4,130.2 ms | 1,589 MB |

In the 1,011-node full delete with (a), the process memory went from 758 MB to 763 MB during the check and from 742 MB to 1,596 MB while the nodes were deleted. The memory used by a full delete of 10,101 nodes comes from the steps after the check, which are the same for every approach.

## What the measurements show

- (d) reads the fewest hits of all approaches in S1 and S4. It reads fewer hits than (a) in every scenario except two:
  - S3, where it reads 8% more and its check takes 123 ms longer. There, (d) also runs query 2, which checks the 10,000 branch-agnostic leaves on the 49 other branches, and (a) does not check other branches.
  - S6, where (a) does not check the other branches and allows a delete that it should refuse.
- (d) costs less than (a) when the deleted node's relationship identifiers have many links elsewhere in the database: 181 hits against 72,424 in S1.
- (c) is not usable: its cost grows with the number of cascade paths and reached 15.9 million hits for a 51-node check.
- (b) is not usable for large cascades: its check took 389 s for 10,101 nodes, and its full delete passed Neo4j's transaction memory limit.
- (a) allows the S6 delete and leaves a required link without a peer on another branch. (b), (c) and (d) refuse it.
