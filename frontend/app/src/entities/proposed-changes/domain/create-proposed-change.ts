import {
  type CreateProposedChangeFromApiParams,
  createProposedChangeFromApi,
} from "@/entities/proposed-changes/api/create-proposed-change-from-api";

export type CreateProposedChangeParams = CreateProposedChangeFromApiParams;

export interface CreateProposedChangeOutcome {
  id: string;
  displayLabel: string;
  ok: boolean;
}

export async function createProposedChange(
  params: CreateProposedChangeParams
): Promise<CreateProposedChangeOutcome> {
  const { data, errors } = await createProposedChangeFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const result = data?.CoreProposedChangeCreate;

  if (!result) {
    throw new Error("No data returned from CoreProposedChangeCreate mutation");
  }

  return {
    id: result.object?.id ?? "",
    displayLabel: result.object?.display_label ?? "",
    ok: result.ok ?? false,
  };
}
