from infrahub.core.constants import InfrahubKind
from infrahub.message_bus import messages
from infrahub.message_bus.types import ProposedChangeGeneratorDefinition
from infrahub.services import InfrahubServices


async def run(message: messages.TriggerGeneratorDefinitionRun, service: InfrahubServices) -> None:
    generators = await service.client.filters(
        kind=InfrahubKind.GENERATORDEFINITION, prefetch_relationships=True, populate_store=True, branch=message.branch
    )

    generator_definitions = [
        ProposedChangeGeneratorDefinition(
            definition_id=generator.id,
            definition_name=generator.name.value,
            class_name=generator.class_name.value,
            file_path=generator.file_path.value,
            query_name=generator.query.peer.name.value,
            query_models=generator.query.peer.models.value,
            repository_id=generator.repository.peer.id,
            parameters=generator.parameters.value,
            group_id=generator.targets.peer.id,
            convert_query_response=generator.convert_query_response.value,
        )
        for generator in generators
    ]

    events = [
        messages.RequestGeneratorDefinitionRun(branch=message.branch, generator_definition=generator_definition)
        for generator_definition in generator_definitions
    ]
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
