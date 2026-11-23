import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import DynamicForm from "@/shared/components/form/dynamic-form";
import type { SelectOption } from "@/shared/components/inputs/select-old";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAddRelationships } from "@/entities/nodes/relationships/ui/queries/add-relationships.mutation";
import { getPoolKindFromSchema } from "@/entities/resource-manager/domain/rules/get-pool-kind-from-schema";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface SelectPeerFormProps {
  objectId: string;
  relationshipSchema: RelationshipSchema;
  onSuccess: () => Promise<void>;
  onCancel: () => void;
}

export function SelectPeerForm({
  objectId,
  relationshipSchema,
  onSuccess,
  onCancel,
}: SelectPeerFormProps) {
  const { mutateAsync: addRelationship } = useAddRelationships();
  const generics = useAtomValue(genericSchemasAtom);
  const schemaList = useAtomValue(nodeSchemasAtom);
  const peerSchema = useSchema(relationshipSchema.peer);

  const generic = generics.find((g) => g.kind === relationshipSchema.kind);
  const poolKind = peerSchema.schema ? getPoolKindFromSchema(peerSchema.schema) : null;
  const relationshipLabel = relationshipSchema.label ?? relationshipSchema.kind ?? "relationship";

  const options: SelectOption[] = [];

  if (generic) {
    for (const kind of generic.used_by ?? []) {
      const relatedSchema = schemaList.find((s) => s.kind === kind);
      if (relatedSchema?.kind) {
        options.push({ id: relatedSchema.kind, name: relatedSchema.name });
      }
    }
  } else {
    const relatedSchema = schemaList.find((s) => s.kind === relationshipSchema.peer);
    if (relatedSchema?.kind) {
      options.push({
        id: relatedSchema.kind,
        name: relatedSchema.label ?? relatedSchema.name,
      });
    }
  }

  const handleSubmit = async (data: any) => {
    const { relation } = data;

    if (!relation?.id && !relation?.from_pool) return;

    const relationshipId = relation.from_pool
      ? { from_pool: { id: relation.from_pool.id } }
      : relation.id;

    await addRelationship({
      objectId,
      relationshipIds: [relationshipId],
      relationshipName: relationshipSchema.name,
    });

    toast(
      <Alert
        type={ALERT_TYPES.SUCCESS}
        message={`Association with ${relationshipSchema.peer} added`}
      />
    );

    await onSuccess();
  };

  return (
    <DynamicForm
      fields={[
        {
          name: "relation",
          label: relationshipLabel,
          type: "relationship",
          relationship: {
            ...relationshipSchema,
            cardinality: "one",
            inherited: true,
          } as RelationshipSchema,
          options,
          pool:
            poolKind && peerSchema.schema?.kind
              ? {
                  kind: poolKind,
                  defaultAllocatedObjectKind: peerSchema.schema.kind,
                }
              : undefined,
        },
      ]}
      onSubmit={async ({ relation }) => {
        await handleSubmit({ relation: relation?.value });
      }}
      onCancel={onCancel}
    />
  );
}
