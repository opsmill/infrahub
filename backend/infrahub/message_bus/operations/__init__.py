import ujson

from infrahub.message_bus import RPCErrorResponse, messages
from infrahub.message_bus.operations import (
    check,
    event,
    finalize,
    git,
    refresh,
    requests,
    schema,
    send,
    transform,
    trigger,
)
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.tasks.check import set_check_status

COMMAND_MAP = {
    "check.artifact.create": check.artifact.create,
    "check.generator.run": check.generator.run,
    "check.repository.check_definition": check.repository.check_definition,
    "check.repository.merge_conflicts": check.repository.merge_conflicts,
    "check.repository.user_check": check.repository.user_check,
    "event.branch.create": event.branch.create,
    "event.branch.delete": event.branch.delete,
    "event.branch.merge": event.branch.merge,
    "event.branch.rebased": event.branch.rebased,
    "event.node.mutated": event.node.mutated,
    "event.schema.update": event.schema.update,
    "event.worker.new_primary_api": event.worker.new_primary_api,
    "finalize.validator.execution": finalize.validator.execution,
    "git.branch.create": git.branch.create,
    "git.diff.names_only": git.diff.names_only,
    "git.file.get": git.file.get,
    "git.repository.add": git.repository.add,
    "git.repository.add_read_only": git.repository.add_read_only,
    "git.repository.pull_read_only": git.repository.pull_read_only,
    "git.repository.merge": git.repository.merge,
    "refresh.registry.branches": refresh.registry.branches,
    "refresh.registry.rebased_branch": refresh.registry.rebased_branch,
    "refresh.webhook.configuration": refresh.webhook.configuration,
    "request.generator_definition.check": requests.generator_definition.check,
    "request.git.create_branch": requests.git.create_branch,
    "request.git.sync": requests.git.sync,
    "request.graphql_query_group.update": requests.graphql_query_group.update,
    "request.artifact.generate": requests.artifact.generate,
    "request.artifact_definition.check": requests.artifact_definition.check,
    "request.artifact_definition.generate": requests.artifact_definition.generate,
    "request.proposed_change.cancel": requests.proposed_change.cancel,
    "request.proposed_change.data_integrity": requests.proposed_change.data_integrity,
    "request.proposed_change.pipeline": requests.proposed_change.pipeline,
    "request.proposed_change.refresh_artifacts": requests.proposed_change.refresh_artifacts,
    "request.proposed_change.repository_checks": requests.proposed_change.repository_checks,
    "request.proposed_change.run_generators": requests.proposed_change.run_generators,
    "request.proposed_change.run_tests": requests.proposed_change.run_tests,
    "request.proposed_change.schema_integrity": requests.proposed_change.schema_integrity,
    "request.repository.checks": requests.repository.checks,
    "request.repository.user_checks": requests.repository.user_checks,
    "send.echo.request": send.echo.request,
    "send.webhook.event": send.webhook.event,
    "schema.migration.path": schema.migration.path,
    "schema.validator.path": schema.validator.path,
    "transform.jinja.template": transform.jinja.template,
    "transform.python.data": transform.python.data,
    "trigger.artifact_definition.generate": trigger.artifact_definition.generate,
    "trigger.proposed_change.cancel": trigger.proposed_change.cancel,
    "trigger.webhook.actions": trigger.webhook.actions,
}


async def execute_message(routing_key: str, message_body: bytes, service: InfrahubServices):
    message_data = ujson.loads(message_body)
    message = messages.MESSAGE_MAP[routing_key](**message_data)
    message.set_log_data(routing_key=routing_key)
    try:
        await COMMAND_MAP[routing_key](message=message, service=service)
    except Exception as exc:  # pylint: disable=broad-except
        if message.reply_requested:
            response = RPCErrorResponse(errors=[str(exc)], initial_message=message.model_dump())
            await service.reply(message=response, initiator=message)
            return
        if message.reached_max_retries:
            service.log.exception("Message failed after maximum number of retries", error=exc)
            await set_check_status(message, conclusion="failure", service=service)
            return
        message.increase_retry_count()
        await service.send(message, delay=MessageTTL.FIVE)
