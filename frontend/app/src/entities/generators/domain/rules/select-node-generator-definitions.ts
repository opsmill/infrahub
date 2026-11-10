import type { NodeGeneratorDefinition } from "@/entities/generators/domain/model/node-generator-definition";

export interface GeneratorDefinitionTargetData {
  id: string;
  display_label?: string | null;
  targets: {
    node?: {
      id?: string | null;
      display_label?: string | null;
      members: { count: number };
    } | null;
  };
}

export interface SelectNodeGeneratorDefinitionsParams {
  definitions: GeneratorDefinitionTargetData[];
  kindCountByGroupId: Map<string, number>;
}

// A definition targets the node's kind when its target group already holds a node of that kind,
// because a generator definition does not declare the kind it targets.
export const selectNodeGeneratorDefinitions = ({
  definitions,
  kindCountByGroupId,
}: SelectNodeGeneratorDefinitionsParams): NodeGeneratorDefinition[] => {
  return definitions.flatMap((definition) => {
    const group = definition.targets.node;
    if (!group?.id) return [];

    const kindCount = kindCountByGroupId.get(group.id) ?? 0;
    if (kindCount === 0) return [];

    return [
      {
        id: definition.id,
        label: definition.display_label ?? definition.id,
        groupId: group.id,
        groupLabel: group.display_label ?? group.id,
        isMember: group.members.count > 0,
      },
    ];
  });
};
