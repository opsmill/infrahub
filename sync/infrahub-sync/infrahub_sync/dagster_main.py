import argparse
import sys
import time
import uuid

from dagster import (
    AssetKey,
    AssetMaterialization,
    AssetObservation,
    DagsterType,
    In,
    MetadataEntry,
    Nothing,
    Out,
    Output,
    PythonObjectDagsterType,
    get_dagster_logger,
    job,
    op,
    repository,
    resource,
)

# Resource definition for InfrahubAdapter
@resource(config_schema={"target": str, "adapter": SyncAdapter, "config": SyncConfig, "branch": str})
def infrahub_adapter(init_context):
    return InfrahubAdapter(
        target=init_context.resource_config["target"],
        adapter=init_context.resource_config["adapter"],
        config=init_context.resource_config["config"],
        branch=init_context.resource_config.get("branch")
    )

# Resource definition for NautobotAdapter
@resource(config_schema={"target": str, "adapter": SyncAdapter, "config": SyncConfig})
def nautobot_adapter(init_context):
    return NautobotAdapter(
        target=init_context.resource_config["target"],
        adapter=init_context.resource_config["adapter"],
        config=init_context.resource_config["config"]
    )

# Resource definition for NetboxAdapter
@resource(config_schema={"target": str, "adapter": SyncAdapter, "config": SyncConfig})
def netbox_adapter(init_context):
    return NetboxAdapter(
        target=init_context.resource_config["target"],
        adapter=init_context.resource_config["adapter"],
        config=init_context.resource_config["config"]
    )

@op(required_resource_keys={"adapter"})
def load_data_from_adapter(context):
    adapter = context.resources.adapter
    # Implement logic to load data using the adapter
    data = adapter.load_data()
    return data

@op(required_resource_keys={"source_adapter", "destination_adapter"})
def sync_data(context):
    source = context.resources.source_adapter
    destination = context.resources.destination_adapter
    # Implement logic for syncing data
    sync_result = source.sync_to(destination)
    return sync_result

@job
def main():
    # Retrieve the adapter names from environment variables or command-line arguments
    source_adapter_name = os.getenv("SOURCE_ADAPTER", "default_source_adapter")
    destination_adapter_name = os.getenv("DESTINATION_ADAPTER", "default_destination_adapter")

    # Dynamically select the adapters based on the names
    source_adapter = globals().get(source_adapter_name, default_source_adapter)
    destination_adapter = globals().get(destination_adapter_name, default_destination_adapter)

    # Use the dynamically selected adapters in the job
    source_id, destination_id = initialize_adapters()

    diff_sync(
        source_id=source_id,
        source_load=load_source(source_id),
        destination_id=destination_id,
        destination_load=load_destination(destination_id),
    ).with_resource_defs({
        "source": source_adapter,
        "destination": destination_adapter
    })

# Run the job with the dynamically selected adapters
if __name__ == "__main__":
    main.execute_in_process()