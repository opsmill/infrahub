import { type AddEnumFromApiParams, addEnumFromApi } from "@/entities/schema/api/add-enum-from-api";

export type AddEnumParams = AddEnumFromApiParams;

export async function addEnum(params: AddEnumParams): Promise<void> {
  const { data, errors } = await addEnumFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.SchemaEnumAdd?.ok) {
    throw new Error("SchemaEnumAdd did not return ok");
  }
}
