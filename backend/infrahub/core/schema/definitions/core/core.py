from ...generic_schema import GenericSchema

core_node = GenericSchema(
    name="Node",
    namespace="Core",
    include_in_menu=False,
    description="Base Node in Infrahub.",
    label="Node",
)

core_task_target = GenericSchema(
    name="TaskTarget",
    include_in_menu=False,
    namespace="Core",
    description="Extend a node to be associated with tasks",
    label="Task Target",
)
