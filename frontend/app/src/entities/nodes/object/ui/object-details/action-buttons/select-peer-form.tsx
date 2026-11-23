import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import DynamicForm from "@/shared/components/form/dynamic-form";
import type {
  DynamicRelationshipFieldProps,
  FormFieldPool,
  FormFieldValue,
} from "@/shared/components/form/type";
import type { SelectOption } from "@/shared/components/inputs/select-old";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import type { AddRelationshipsParams } from "@/entities/nodes/relationships/domain/use-cases/add-relationships";
import { useAddRelationships } from "@/entities/nodes/relationships/ui/queries/add-relationships.mutation";
import { getPoolKindFromSchema } from "@/entities/resource-manager/domain/rules/get-pool-kind-from-schema";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

type RelationshipId = AddRelationshipsParams["relationshipIds"][number];

const RELATION_FIELD_NAME = "relation";

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

  const kindOptions: Array<SelectOption> = generic
    ? (generic.used_by ?? []).flatMap((kind) => {
        const usedBySchema = schemaList.find((s) => s.kind === kind);
        return usedBySchema?.kind ? [{ id: usedBySchema.kind, name: usedBySchema.name }] : [];
      })
    : schemaList.flatMap((s) =>
        s.kind && s.kind === relationshipSchema.peer
          ? [{ id: s.kind, name: s.label ?? s.name }]
          : []
      );

  const pool: FormFieldPool | undefined =
    poolKind && peerSchema.schema?.kind
      ? { kind: poolKind, defaultAllocatedObjectKind: peerSchema.schema.kind }
      : undefined;

  const relationField: DynamicRelationshipFieldProps = {
    name: RELATION_FIELD_NAME,
    label: relationshipSchema.label ?? relationshipSchema.kind ?? "relationship",
    type: "relationship",
    relationship: { ...relationshipSchema, cardinality: "one", inherited: true },
    options: kindOptions,
    pool,
  };

  const addPeer = async (fieldValue: FormFieldValue | undefined) => {
    const relationshipId = toRelationshipId(fieldValue?.value);
    if (!relationshipId) return;

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
      fields={[relationField]}
      onSubmit={(formData) => addPeer(formData[RELATION_FIELD_NAME])}
      onCancel={onCancel}
    />
  );
}

function toRelationshipId(value: FormFieldValue["value"] | undefined): RelationshipId | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if ("from_pool" in value) return { from_pool: { id: value.from_pool.id } };
  if ("id" in value && typeof value.id === "string") return value.id;
  return null;
}
