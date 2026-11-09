import {
  type RemoveEnumFromApiParams,
  removeEnumFromApi,
} from "@/entities/schema/api/remove-enum-from-api";

export type RemoveEnumParams = RemoveEnumFromApiParams;

export async function removeEnum(params: RemoveEnumParams): Promise<void> {
  const { data, errors } = await removeEnumFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.SchemaEnumRemove?.ok) {
    throw new Error("SchemaEnumRemove did not return ok");
  }
}
