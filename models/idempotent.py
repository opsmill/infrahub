import logging

import networkx as nx
from infrahub_sdk import InfrahubClient, NodeStore

# flake8: noqa
# pylint: skip-file

store = NodeStore()

ORGANIZATIONS = (
    ("ORG1", ("BLUE", "RED")),
    ("ORG2", ("BLUE", "RED", "YELLOW")),
)


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run <script>
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str):
    # batch = await client.create_batch()
    nx.DiGraph()

    batch = await client.create_batch()

    account = await client.create(
        branch=branch,
        kind="CoreAccount",
        data={
            "name": "test-script",
            "password": "test-script",
            "type": "Script",
            "role": "read-write",
        },
    )
    await account.save()
    store.set(key="test-script", node=account)

    for tag in ["BLUE", "RED"]:
        obj = await client.create(
            branch=branch, kind="BuiltinTag", name={"value": tag, "source": account.id}
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=tag, node=obj)

    for org in ORGANIZATIONS:
        tags = [store.get(kind="BuiltinTag", key=tag_name) for tag_name in org[1]]

        obj = await client.create(
            branch=branch,
            kind="CoreOrganization",
            data={"name": {"value": org[0], "is_protected": True}, "tags": tags},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=org[0], node=obj)

    # schema = await client.schema.all()
    # for node_kind, node in schema.items():

    #     if node_kind in NODES_TO_EXCLUDE or NODES_TO_INCLUDE and node_kind not in NODES_TO_INCLUDE:
    #         continue

    #     G.add_node(node_kind)
    #     print(f"Added node {node_kind}")

    # for node_kind, node in schema.items():
    #     if node_kind in NODES_TO_EXCLUDE or NODES_TO_INCLUDE and node_kind not in NODES_TO_INCLUDE:
    #         continue

    #     for rel in node.relationships:
    #         if rel.optional:
    #             continue

    #         if rel.peer in NODES_TO_EXCLUDE or NODES_TO_INCLUDE and node_kind not in NODES_TO_INCLUDE:
    #             continue

    #         G.add_edge(rel.peer, node_kind, name=rel.name)
    #         print(f"Added Edge {rel.peer} > {node_kind} | {rel.name}")

    # is_dag = nx.is_directed_acyclic_graph(G)
    # print(f"DAG : {is_dag}")

    # seed = 13648  # Seed random number generators for reproducibility
    # pos = nx.spring_layout(G, seed=seed)

    # node_sizes = [3 + 10 * i for i in range(len(G))]
    # M = G.number_of_edges()
    # edge_colors = range(2, M + 2)
    # edge_alphas = [(5 + i) / (M + 4) for i in range(M)]
    # cmap = plt.cm.plasma

    # nodes = nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color="indigo")
    # edges = nx.draw_networkx_edges(
    #     G,
    #     pos,
    #     node_size=node_sizes,
    #     arrowstyle="->",
    #     arrowsize=10,
    #     edge_color=edge_colors,
    #     edge_cmap=cmap,
    #     width=2,
    # )

    # options = {
    #     "font_size": 36,
    #     "node_size": 3000,
    #     "node_color": "white",
    #     "edgecolors": "black",
    #     "linewidths": 5,
    #     "width": 5,
    # }
    # nx.draw_networkx(G, pos)

    # ax = plt.gca()
    # ax.margins(0.20)
    # plt.axis("off")

    # for i in range(M):
    #     edges[i].set_alpha(edge_alphas[i])

    # pc = mpl.collections.PatchCollection(edges, cmap=cmap)
    # pc.set_array(edge_colors)

    # ax = plt.gca()
    # ax.set_axis_off()
    # plt.colorbar(pc, ax=ax)
    # list(reversed(list(nx.topological_sort(G))))
    # breakpoint()
    # plt.show()
