# PR lifecycle dashboard

Last successful refresh: never

Observation preview: 2026-09-28T13:08:21.967171+00:00 (UTC)

Open PRs: 117; human: 112; excluded bots: 5.

Days inactive means elapsed whole days since observed non-lifecycle activity, not time waiting for review.

## Ready to merge (5)

| PR / author | Next actor / action | Days inactive | Blockers / closure exemptions | Next notice / deadline (UTC) |
| --- | --- | --- | --- | --- |
|[#9967](https://github.com/opsmill/infrahub/pull/9967) chore: add neo4j cypher, python driver, and query tuning skills / dgarros|dgarros: Merge|33|— / approval|Reminder due|
|[#10348](https://github.com/opsmill/infrahub/pull/10348) fix: initialize git submodules and freeze the lockfile in the web session setup hook / dgarros|dgarros: Merge|31|— / approval|Reminder due|
|[#10636](https://github.com/opsmill/infrahub/pull/10636) fix: concurrent diff save batches and chunked node-level calculation / fatih-acar|fatih-acar: Merge|8|— / approval|Reminder due|
|[#10662](https://github.com/opsmill/infrahub/pull/10662) docs: rename the Get started sidebar section and its subsections / yjouffrault|yjouffrault: Merge|11|— / approval|Reminder due|
|[#10674](https://github.com/opsmill/infrahub/pull/10674) fix: silence httpcore debug records in the API server logs / DharmaBytesX|DharmaBytesX: Merge|3|— / approval|Reminder: 2026-10-02T07:36:33+00:00|

## Waiting for review (13)

| PR / author | Next actor / action | Days inactive | Blockers / closure exemptions | Next notice / deadline (UTC) |
| --- | --- | --- | --- | --- |
|[#10573](https://github.com/opsmill/infrahub/pull/10573) refactor&#40;changelog&#41;: move relationship changelog components out of models / polmichel|qduk, opsmill/backend, opsmill/frontend, opsmill/cloud, opsmill/product: Review|0|— / —|Reminder: 2026-10-05T10:02:57+00:00|
|[#10600](https://github.com/opsmill/infrahub/pull/10600) refactor&#40;backend&#41;: clear the mypy suppression on infrahub.lock / saltas888|ogenstad, polmichel: Review|0|— / —|Reminder: 2026-10-05T09:23:10+00:00|
|[#10642](https://github.com/opsmill/infrahub/pull/10642) feat&#40;git&#41;: verify write access when connecting a read-write repository / ogenstad|qduk, opsmill/backend, opsmill/frontend, opsmill/product: Review|0|— / —|Reminder: 2026-10-05T12:45:31+00:00|
|[#10654](https://github.com/opsmill/infrahub/pull/10654) fix: read union of all GraphQL selections in field extractor / ogenstad|opsmill/backend: Review|12|— / —|Reminder due|
|[#10667](https://github.com/opsmill/infrahub/pull/10667) feat: answer repository branch drift with a row per branch &#91;IFC-3147&#93; / ogenstad|opsmill/backend: Review|0|— / —|Reminder: 2026-10-05T12:43:22+00:00|
|[#10668](https://github.com/opsmill/infrahub/pull/10668) feat&#40;backend&#41;: bound every worker RPC by a configurable timeout &#91;IFC-3148&#93; / ogenstad|opsmill/backend, opsmill/frontend, opsmill/cloud: Review|0|— / —|Reminder: 2026-10-05T12:38:35+00:00|
|[#10669](https://github.com/opsmill/infrahub/pull/10669) feat: detect upstream movement on read-only repository refs &#91;IFC-3152&#93; / ogenstad|opsmill/backend, opsmill/frontend, opsmill/cloud: Review|0|— / —|Reminder: 2026-10-05T11:53:26+00:00|
|[#10672](https://github.com/opsmill/infrahub/pull/10672) refactor&#40;backend&#41;: anchor number pool reservations on the attribute / ajtmccarty|opsmill/backend: Review|9|— / —|Reminder due|
|[#10682](https://github.com/opsmill/infrahub/pull/10682) feat&#40;number-pool&#41;: publish the GraphQL contract for weighted ranges / polmichel|opsmill/backend: Review|0|— / —|Reminder: 2026-10-05T07:30:46+00:00|
|[#10696](https://github.com/opsmill/infrahub/pull/10696) feat: reject a default branch absent from the remote when connecting a repository &#91;IFC-3139&#93; / ogenstad|BeArchiTek, opsmill/backend, opsmill/frontend: Review|0|— / —|Reminder: 2026-10-05T08:09:37+00:00|
|[#10726](https://github.com/opsmill/infrahub/pull/10726) fix&#40;frontend&#41;: show why an artifact or file could not be loaded / DharmaBytesX|opsmill/frontend: Review|1|— / —|Reminder: 2026-10-04T10:08:36+00:00|
|[#10735](https://github.com/opsmill/infrahub/pull/10735) refactor&#40;backend&#41;: clear the type-checker suppressions on the core.query base module / saltas888|opsmill/backend: Review|0|— / —|Reminder: 2026-10-05T12:16:45+00:00|
|[#10741](https://github.com/opsmill/infrahub/pull/10741) chore&#40;backend&#41;: enable the pydantic mypy plugin and fix surfaced errors / ogenstad|opsmill/backend: Review|0|— / —|Reminder: 2026-10-05T11:51:03+00:00|

## Waiting for author / Needs reviewer (2)

| PR / author | Next actor / action | Days inactive | Blockers / closure exemptions | Next notice / deadline (UTC) |
| --- | --- | --- | --- | --- |
|[#7720](https://github.com/opsmill/infrahub/pull/7720) fix: deserialize List attribute values before regex validation / wvandeun|wvandeun: Request person/team review|222|— / —|Initial warning due; deadline unset|
|[#7749](https://github.com/opsmill/infrahub/pull/7749) add common parent constraint for hierarchical nodes / wvandeun|wvandeun: Request person/team review|25|— / —|Reminder due|

## Blocked (36)

| PR / author | Next actor / action | Days inactive | Blockers / closure exemptions | Next notice / deadline (UTC) |
| --- | --- | --- | --- | --- |
|[#7933](https://github.com/opsmill/infrahub/pull/7933) add inline editing to object details view / bilalabbad|bilalabbad: Resolve listed blockers|163|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#8161](https://github.com/opsmill/infrahub/pull/8161) Enhance NodeKindUpdateMigration to update pool node references / minitriga|minitriga: Resolve listed blockers|146|merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#8245](https://github.com/opsmill/infrahub/pull/8245) fix&#40;frontend&#41;: use variables for graphql pagination / fatih-acar|opsmill/frontend: Review|9|merge requirements pending or unknown / —|Reminder due|
|[#8448](https://github.com/opsmill/infrahub/pull/8448) WIP: Improve search anywhere by adding a new page / BeArchiTek|BeArchiTek: Resolve listed blockers|27|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#8506](https://github.com/opsmill/infrahub/pull/8506) Show related nodes and templates in the profile details view / bilalabbad|bilalabbad: Resolve listed blockers|85|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#8742](https://github.com/opsmill/infrahub/pull/8742) feat: add health check endpoint at /api/health for load balancer and K8s probes / BeArchiTek|BeArchiTek: Resolve listed blockers|81|merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#8852](https://github.com/opsmill/infrahub/pull/8852) Forbid to null an attribute with a default&#95;value in the schema / ogenstad|ogenstad: Resolve merge requirements|113|merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#9023](https://github.com/opsmill/infrahub/pull/9023) test: add regression coverage for login/logout activity events &#91;INFP-… / PhillSimonds|PhillSimonds: Address feedback; request review|115|requested changes, merge requirements pending or unknown / approval|Reminder due|
|[#9074](https://github.com/opsmill/infrahub/pull/9074) Add DateTime attribute range filtering &#40;&#95;&#95;after / &#95;&#95;before / between&#41; / FragmentedPacket|FragmentedPacket: Resolve listed blockers|48|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9266](https://github.com/opsmill/infrahub/pull/9266) fix: add labels to NodeNotFoundError for clearer messaging / DharmaBytesX|DharmaBytesX: Resolve listed blockers|116|merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#9370](https://github.com/opsmill/infrahub/pull/9370) Replace f-string log calls to structured kwargs logs / Dhanus3133|Dhanus3133: Resolve listed blockers|58|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9398](https://github.com/opsmill/infrahub/pull/9398) feat: Ability to update the branch description / Dhanus3133|Dhanus3133: Resolve listed blockers|32|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9432](https://github.com/opsmill/infrahub/pull/9432) feat: Allow API callers to inject a request-id header / Dhanus3133|opsmill/backend: Review|58|merge requirements pending or unknown / —|Reminder due|
|[#9549](https://github.com/opsmill/infrahub/pull/9549) feat: support DateTime kind for computed attributes / Dhanus3133|Dhanus3133: Resolve listed blockers|58|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9596](https://github.com/opsmill/infrahub/pull/9596) fix: search anywhere crashes on SchemaNode UUID lookup / BeArchiTek|BeArchiTek: Resolve listed blockers|59|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9873](https://github.com/opsmill/infrahub/pull/9873) feat&#40;skills&#41;: add shipping-features orchestrator + capturing-knowledge / pa-lem|pa-lem: Resolve listed blockers|39|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9957](https://github.com/opsmill/infrahub/pull/9957) docs&#40;release-notes&#41;: group releases by minor line with descriptions and badges / yjouffrault|yjouffrault: Resolve listed blockers|39|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9963](https://github.com/opsmill/infrahub/pull/9963) fix: allow clearing unique optional attributes in bulk edit / lancamat1|lancamat1: Resolve listed blockers|39|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9965](https://github.com/opsmill/infrahub/pull/9965) fix: enforce NonNegativeInt on GraphQL pagination arguments / iddocohen|iddocohen: Resolve listed blockers|17|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10121](https://github.com/opsmill/infrahub/pull/10121) fix&#40;graphql&#41;: retry transient database errors on object create / BeArchiTek|BeArchiTek: Address feedback; request review|24|requested changes, merge requirements pending or unknown / approval|Reminder due|
|[#10266](https://github.com/opsmill/infrahub/pull/10266) chore: run the release-notes vale check in /pre-ci / ogenstad|ogenstad: Resolve listed blockers|38|merge conflicts, merge requirements pending or unknown / approval|Reminder due|
|[#10311](https://github.com/opsmill/infrahub/pull/10311) docs: cover branch rebase in the upgrade docs / lancamat1|opsmill/frontend: Review|38|merge requirements pending or unknown / —|Reminder due|
|[#10316](https://github.com/opsmill/infrahub/pull/10316) fix: emit group.member&#95;added only for the group named in the mutation &#40;closes &#35;10314&#41; / iddocohen|iddocohen: Resolve listed blockers|38|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10408](https://github.com/opsmill/infrahub/pull/10408) docs&#40;dev&#41;: add a skill for testing against real data &#40;AI/DC solution&#41; / saltas888|fatih-acar, opsmill/frontend: Review|0|merge requirements pending or unknown / —|Reminder: 2026-10-05T12:40:56+00:00|
|[#10437](https://github.com/opsmill/infrahub/pull/10437) docs: state what starts an artifact and Generator run / lancamat1|BeArchiTek, opsmill/backend, opsmill/frontend, opsmill/sa: Review|14|merge requirements pending or unknown / —|Reminder due|
|[#10451](https://github.com/opsmill/infrahub/pull/10451) feat&#40;frontend&#41;: reveal row metadata icon on hover / qduk|qduk: Resolve listed blockers|13|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10453](https://github.com/opsmill/infrahub/pull/10453) chore: migrate pre-commit configuration to prek / ryanmerolle|ryanmerolle: Resolve listed blockers|3|merge conflicts, merge requirements pending or unknown / approval|Reminder: 2026-10-02T07:36:33+00:00|
|[#10617](https://github.com/opsmill/infrahub/pull/10617) fix: normalize IP attribute values on update &#40;closes &#35;10616&#41; / lancamat1|ajtmccarty: Review|0|merge requirements pending or unknown / —|Reminder: 2026-10-05T10:01:28+00:00|
|[#10632](https://github.com/opsmill/infrahub/pull/10632) fix&#40;workflows&#41;: stop Prefect walking and persisting large payloads / fatih-acar|fatih-acar: Resolve listed blockers|0|merge conflicts, merge requirements pending or unknown / —|Reminder: 2026-10-05T08:48:26+00:00|
|[#10649](https://github.com/opsmill/infrahub/pull/10649) feat&#40;frontend&#41;: add a Git status indicator to the app header / pa-lem|pa-lem: Resolve listed blockers|0|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-05T12:37:40+00:00|
|[#10658](https://github.com/opsmill/infrahub/pull/10658) feat&#40;repository&#41;: branches card and branch-scoped details &#40;IFC-3130&#41; / pa-lem|pa-lem: Resolve listed blockers|0|merge conflicts, merge requirements pending or unknown / —|Reminder: 2026-10-05T12:27:21+00:00|
|[#10681](https://github.com/opsmill/infrahub/pull/10681) fix&#40;git&#41;: clone a repository under the repository lock / fatih-acar|opsmill/backend: Review|4|merge requirements pending or unknown / —|Reminder: 2026-09-30T21:51:02+00:00|
|[#10683](https://github.com/opsmill/infrahub/pull/10683) fix&#40;api&#41;: stop shedding the page load that carries the web UI / fatih-acar|opsmill/backend: Review|4|merge requirements pending or unknown / —|Reminder: 2026-09-30T21:51:02+00:00|
|[#10727](https://github.com/opsmill/infrahub/pull/10727) fix&#40;git&#41;: regenerate artifacts whose stored file is missing &#91;&#35;7260&#93; / DharmaBytesX|qduk, opsmill/backend, opsmill/frontend, opsmill/cloud, opsmill/product: Review|0|merge requirements pending or unknown / —|Reminder: 2026-10-05T09:43:57+00:00|
|[#10731](https://github.com/opsmill/infrahub/pull/10731) docs: review lessons from the last 2 weeks&#40;09-11 -&gt; 09-25&#41; + extra / saltas888|pthmas, opsmill/backend, opsmill/product: Review|0|merge requirements pending or unknown / —|Reminder: 2026-10-05T12:16:45+00:00|
|[#10740](https://github.com/opsmill/infrahub/pull/10740) fix&#40;branch&#41;: delete the post-rebase changelog diff / minitriga|minitriga: Resolve listed blockers|0|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-05T12:48:59+00:00|

## Drafts (56)

| PR / author | Next actor / action | Days inactive | Blockers / closure exemptions | Next notice / deadline (UTC) |
| --- | --- | --- | --- | --- |
|[#7858](https://github.com/opsmill/infrahub/pull/7858) Add deprecation icon and description for attributes and relationships / pa-lem|pa-lem: Finish draft; ready; request review|173|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#8765](https://github.com/opsmill/infrahub/pull/8765) WIP: Add Float support / BeArchiTek|BeArchiTek: Finish draft; ready; request review|37|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#8874](https://github.com/opsmill/infrahub/pull/8874) Fix race condition: ensure generators complete before artifact refresh in proposed changes / minitriga|minitriga: Finish draft; ready; request review|113|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#8878](https://github.com/opsmill/infrahub/pull/8878) Make Generic attribute &&#35;x27;optional&&#35;x27; field changeable / PhillSimonds|PhillSimonds: Finish draft; ready; request review|24|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9070](https://github.com/opsmill/infrahub/pull/9070) Fix task pages firing one GraphQL query per related node &#40;&#35;9067&#41; / fatih-acar|fatih-acar: Finish draft; ready; request review|136|merge conflicts, merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#9226](https://github.com/opsmill/infrahub/pull/9226) chore&#40;skills&#41;: improve cypher query for planner / fatih-acar|fatih-acar: Finish draft; ready; request review|8|merge requirements pending or unknown / —|Reminder due|
|[#9323](https://github.com/opsmill/infrahub/pull/9323) Initial tests for git module refactoring / ogenstad|ogenstad: Finish draft; ready; request review|109|— / —|Initial warning due; deadline unset|
|[#9353](https://github.com/opsmill/infrahub/pull/9353) Allow for dynamic concurrency limit for generate artifacts in Prefect / ogenstad|ogenstad: Finish draft; ready; request review|43|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9451](https://github.com/opsmill/infrahub/pull/9451) feat: support Redis Sentinel for HA cache and lock connections &#91;&#35;9449&#93; / fatih-acar|fatih-acar: Finish draft; ready; request review|10|merge requirements pending or unknown / —|Reminder due|
|[#9735](https://github.com/opsmill/infrahub/pull/9735) chore: add fastapi library-skill and CI check to keep skills current / dgarros|dgarros: Finish draft; ready; request review|46|checks pending or failing, merge requirements pending or unknown / —|Reminder due|
|[#9736](https://github.com/opsmill/infrahub/pull/9736) test&#40;e2e&#41;: slim demo dataset to 2 sites + rebalance shards / fatih-acar|fatih-acar: Finish draft; ready; request review|20|checks pending or failing, merge requirements pending or unknown / —|Reminder due|
|[#9798](https://github.com/opsmill/infrahub/pull/9798) test&#40;git&#41;: multi-environment single-repo validation &#40;Approach A&#41; / lancamat1|lancamat1: Finish draft; ready; request review|65|merge requirements pending or unknown / —|Initial warning due; deadline unset|
|[#9843](https://github.com/opsmill/infrahub/pull/9843) feat&#40;frontend&#41;: rebrand color palette to OpsMill Blue / fatih-acar|fatih-acar: Finish draft; ready; request review|21|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#9988](https://github.com/opsmill/infrahub/pull/9988) experiment/wip: feat&#40;testing&#41;: seed test stacks from a db snapshot, faster boots / fatih-acar|fatih-acar: Finish draft; ready; request review|39|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10003](https://github.com/opsmill/infrahub/pull/10003) feat&#40;telemetry&#41;: licensing resource-allocation telemetry &#91;INFP-631&#93; / saltas888|saltas888: Finish draft; ready; request review|0|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-04T17:39:46+00:00|
|[#10075](https://github.com/opsmill/infrahub/pull/10075) fix: omit task related nodes that are missing from the graph / pa-lem|pa-lem: Finish draft; ready; request review|17|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10133](https://github.com/opsmill/infrahub/pull/10133) feat&#40;backend&#41;: add Redis Streams message bus driver / fatih-acar|fatih-acar: Finish draft; ready; request review|39|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10226](https://github.com/opsmill/infrahub/pull/10226) docs&#40;cut-release&#41;: avoid release-&#42; branch names for patch releases / ogenstad|ogenstad: Finish draft; ready; request review|39|merge conflicts, merge requirements pending or unknown / approval|Reminder due|
|[#10229](https://github.com/opsmill/infrahub/pull/10229) chore: drop the vestigial obj&#95;type parameter from &#95;diff&#95;element / ogenstad|ogenstad: Finish draft; ready; request review|47|checks pending or failing, merge requirements pending or unknown / —|Reminder due|
|[#10249](https://github.com/opsmill/infrahub/pull/10249) test&#40;events&#41;: prove an event on the maximum is rejected after the run-context append &#91;IFC-3008&#93; / ogenstad|ogenstad: Finish draft; ready; request review|42|checks pending or failing, merge requirements pending or unknown / —|Reminder due|
|[#10293](https://github.com/opsmill/infrahub/pull/10293) docs: document how query targeting scopes artifact regeneration &#91;IFC-2504&#93; / ogenstad|ogenstad: Finish draft; ready; request review|38|merge conflicts, merge requirements pending or unknown / approval|Reminder due|
|[#10379](https://github.com/opsmill/infrahub/pull/10379) fix&#40;backend&#41;: stop task-manager event queries from flipping to a quadratic generic plan / fatih-acar|fatih-acar: Finish draft; ready; request review|20|merge requirements pending or unknown / —|Reminder due|
|[#10391](https://github.com/opsmill/infrahub/pull/10391) docs: capture the context gaps found retrospecting the dark theme work / saltas888|saltas888: Finish draft; ready; request review|3|— / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10411](https://github.com/opsmill/infrahub/pull/10411) &#91;PoC — reference, do not merge&#93; CI-verified e2e reproduction for &#35;3890 &#40;bug pipeline proof runs&#41; / saltas888|saltas888: Finish draft; ready; request review|18|checks pending or failing, merge requirements pending or unknown / —|Reminder due|
|[#10431](https://github.com/opsmill/infrahub/pull/10431) feat&#40;ci&#41;: E2E proof runs for the bug pipeline &#91;IFC-3059&#93; / saltas888|saltas888: Finish draft; ready; request review|17|merge requirements pending or unknown / —|Reminder due|
|[#10465](https://github.com/opsmill/infrahub/pull/10465) fix: stop recording a repository merge when the remote rejects the push &#91;&#35;6298&#93; / ogenstad|ogenstad: Finish draft; ready; request review|11|— / —|Reminder due|
|[#10496](https://github.com/opsmill/infrahub/pull/10496) fix&#40;graphql&#41;: give every mutation one uniform retry budget &#91;&#35;10119&#93; / ogenstad|ogenstad: Finish draft; ready; request review|11|merge requirements pending or unknown / —|Reminder due|
|[#10513](https://github.com/opsmill/infrahub/pull/10513) docs&#40;specs&#41;: cross-branch repository status query &#40;INFP-671&#41; / ogenstad|ogenstad: Finish draft; ready; request review|0|— / —|Reminder: 2026-10-05T09:35:30+00:00|
|[#10519](https://github.com/opsmill/infrahub/pull/10519) fix&#40;frontend&#41;: keep the active branch when navigating the app chrome / wvandeun|wvandeun: Finish draft; ready; request review|9|checks pending or failing, merge requirements pending or unknown / —|Reminder due|
|[#10530](https://github.com/opsmill/infrahub/pull/10530) docs&#40;spec&#41;: git repository commit visibility spec set &#40;IFC-3101&#41; / ogenstad|ogenstad: Finish draft; ready; request review|11|merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10542](https://github.com/opsmill/infrahub/pull/10542) docs&#40;specs&#41;: spec set for honouring the repository default branch &#91;IFC-3105&#93; / ogenstad|ogenstad: Finish draft; ready; request review|3|— / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10561](https://github.com/opsmill/infrahub/pull/10561) Name each end of a hop from the stored edge orientation / gmazoyer|gmazoyer: Finish draft; ready; request review|3|merge conflicts, merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10595](https://github.com/opsmill/infrahub/pull/10595) Share the query automations of one transform / gmazoyer|gmazoyer: Finish draft; ready; request review|0|merge conflicts, merge requirements pending or unknown / —|Reminder: 2026-10-05T09:08:21+00:00|
|[#10596](https://github.com/opsmill/infrahub/pull/10596) Recompute only what the matching query feeds / gmazoyer|gmazoyer: Finish draft; ready; request review|0|— / —|Reminder: 2026-10-05T09:05:45+00:00|
|[#10609](https://github.com/opsmill/infrahub/pull/10609) fix: retrieve a named diff by name on DiffTree and DiffTreeSummary &#91;&#35;10592&#93; / ogenstad|ogenstad: Finish draft; ready; request review|2|merge requirements pending or unknown / —|Reminder: 2026-10-03T02:15:59+00:00|
|[#10610](https://github.com/opsmill/infrahub/pull/10610) fix&#40;changelog&#41;: report each affected peer once with full edge metadata / polmichel|polmichel: Finish draft; ready; request review|0|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-05T13:08:02+00:00|
|[#10619](https://github.com/opsmill/infrahub/pull/10619) feat: fail proposed change checks when a repository import failed / ogenstad|ogenstad: Finish draft; ready; request review|11|— / —|Reminder due|
|[#10631](https://github.com/opsmill/infrahub/pull/10631) fix&#40;workflows&#41;: expire task results stored in Redis / fatih-acar|fatih-acar: Finish draft; ready; request review|10|checks pending or failing, merge conflicts, merge requirements pending or unknown / —|Reminder due|
|[#10638](https://github.com/opsmill/infrahub/pull/10638) perf&#40;changelog&#41;: read labels without loading whole nodes / polmichel|polmichel: Finish draft; ready; request review|0|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-05T12:56:11+00:00|
|[#10660](https://github.com/opsmill/infrahub/pull/10660) fix&#40;core&#41;: enforce kind in get&#95;one&#95;by&#95;id&#95;or&#95;default&#95;filter / ogenstad|ogenstad: Finish draft; ready; request review|11|merge requirements pending or unknown / —|Reminder due|
|[#10678](https://github.com/opsmill/infrahub/pull/10678) feat&#40;backend&#41;: generate the SDK&&#35;x27;s error catalogue bindings / ogenstad|ogenstad: Finish draft; ready; request review|0|state/blocked / —|Reminder: 2026-10-05T08:01:29+00:00|
|[#10691](https://github.com/opsmill/infrahub/pull/10691) feat&#40;graphql&#41;: carry a schema deprecation through to the generated types &#91;IFC-3211&#93; / polmichel|polmichel: Finish draft; ready; request review|3|— / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10693](https://github.com/opsmill/infrahub/pull/10693) Manual merge stable into develop / polmichel|polmichel: Finish draft; ready; request review|3|— / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10694](https://github.com/opsmill/infrahub/pull/10694) fix&#40;branch&#41;: keep the deleting task out of a deleted branch&&#35;x27;s task purge / fatih-acar|fatih-acar: Finish draft; ready; request review|3|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10702](https://github.com/opsmill/infrahub/pull/10702) docs: address the Cubic documentation-accuracy and doc-style findings from &#35;10693 / polmichel|polmichel: Finish draft; ready; request review|3|merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10710](https://github.com/opsmill/infrahub/pull/10710) docs&#40;deploy&#41;: organize the installation guides by deployment method / fatih-acar|fatih-acar: Finish draft; ready; request review|3|merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10712](https://github.com/opsmill/infrahub/pull/10712) feat&#40;ci&#41;: request a default reviewer on ready pull requests / polmichel|polmichel: Finish draft; ready; request review|3|merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10713](https://github.com/opsmill/infrahub/pull/10713) chore: track which internal docs Claude Code sessions read, and why / ajtmccarty|ajtmccarty: Finish draft; ready; request review|3|merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10715](https://github.com/opsmill/infrahub/pull/10715) chore: add local cubic review with Infrahub checklists / pa-lem|pa-lem: Finish draft; ready; request review|0|merge requirements pending or unknown / —|Reminder: 2026-10-05T07:27:10+00:00|
|[#10716](https://github.com/opsmill/infrahub/pull/10716) feat&#40;ci&#41;: analyse and auto-merge Dependabot PRs with a dependency-bump autopilot / polmichel|polmichel: Finish draft; ready; request review|3|merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10717](https://github.com/opsmill/infrahub/pull/10717) chore: add repo-aware code review skill / ogenstad|ogenstad: Finish draft; ready; request review|3|merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10720](https://github.com/opsmill/infrahub/pull/10720) fix&#40;ipam&#41;: render each prefix once when IPAM tree pages overlap &#40;closes &#35;10719&#41; / BeArchiTek|BeArchiTek: Finish draft; ready; request review|3|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10722](https://github.com/opsmill/infrahub/pull/10722) feat&#40;tasks&#41;: show internal and scheduled background flows in the Tasks view &#91;infp-68&#93; / minitriga|minitriga: Finish draft; ready; request review|3|— / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10724](https://github.com/opsmill/infrahub/pull/10724) feat&#40;config&#41;: add tls&#95;insecure to S3 storage and syslog destinations / fatih-acar|fatih-acar: Finish draft; ready; request review|3|merge requirements pending or unknown / —|Reminder: 2026-10-02T07:36:33+00:00|
|[#10736](https://github.com/opsmill/infrahub/pull/10736) refactor&#40;changelog&#41;: extract the relationship getter&&#35;x27;s components / polmichel|polmichel: Finish draft; ready; request review|0|checks pending or failing, merge requirements pending or unknown / —|Reminder: 2026-10-05T13:07:59+00:00|
|[#10744](https://github.com/opsmill/infrahub/pull/10744) docs&#40;guidelines&#41;: typing and test-fixture lessons from PR &#35;10735&&#35;x27;s review &#91;INBOX-35&#93; / saltas888|saltas888: Finish draft; ready; request review|0|— / —|Reminder: 2026-10-05T12:28:29+00:00|

## Closing soon (0)

None.

## Bot-authored PRs (5)

Excluded from reminders and cleanup.

- [#10099](https://github.com/opsmill/infrahub/pull/10099) Serve frontend via FastAPI native app.frontend&#40;&#41; / claude&#91;bot&#93;
- [#10206](https://github.com/opsmill/infrahub/pull/10206) docs: add Community to Enterprise migration guide / claude&#91;bot&#93;
- [#10370](https://github.com/opsmill/infrahub/pull/10370) test: failing test for &#35;6293 -- generator instance orphaned when target object deleted / opsmill-bug-pipeline&#91;bot&#93;
- [#10659](https://github.com/opsmill/infrahub/pull/10659) Merge stable into develop / infrahub-github-bot-app&#91;bot&#93;
- [#10733](https://github.com/opsmill/infrahub/pull/10733) chore&#40;deps&#41;: bump anthropics/claude-code-action from 1.0.230 to 1.0.235 / dependabot&#91;bot&#93;
