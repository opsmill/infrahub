import {
  type CreateProposedChangeFromApiParams,
  createProposedChangeFromApi,
} from "@/entities/proposed-changes/api/create-proposed-change-from-api";

export type CreateProposedChangeParams = CreateProposedChangeFromApiParams;

export interface CreateProposedChangeResult {
  id: string;
  displayLabel: string;
}

export async function createProposedChange(
  params: CreateProposedChangeParams
): Promise<CreateProposedChangeResult> {
  const { data, errors } = await createProposedChangeFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const result = data?.CoreProposedChangeCreate;

  if (!result?.ok || !result.object) {
    throw new Error("Failed to create proposed change");
  }

  return {
    id: result.object.id,
    displayLabel: result.object.display_label ?? "",
  };
}
