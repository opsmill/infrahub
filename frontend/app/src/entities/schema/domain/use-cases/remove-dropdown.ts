import {
  type RemoveDropdownFromApiParams,
  removeDropdownFromApi,
} from "@/entities/schema/api/remove-dropdown-from-api";

export type RemoveDropdownParams = RemoveDropdownFromApiParams;

export async function removeDropdown(params: RemoveDropdownParams): Promise<void> {
  const { data, errors } = await removeDropdownFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.SchemaDropdownRemove?.ok) {
    throw new Error("SchemaDropdownRemove did not return ok");
  }
}
