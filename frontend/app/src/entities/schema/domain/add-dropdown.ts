import {
  type AddDropdownFromApiParams,
  addDropdownFromApi,
} from "@/entities/schema/api/add-dropdown-from-api";

export type AddDropdownParams = AddDropdownFromApiParams;

export interface AddDropdownOutcome {
  value: string;
  label: string | null;
  color: string | null;
  description: string | null;
}

export async function addDropdown(params: AddDropdownParams): Promise<AddDropdownOutcome> {
  const { data, errors } = await addDropdownFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.SchemaDropdownAdd?.ok) {
    throw new Error("SchemaDropdownAdd did not return ok");
  }

  const obj = data.SchemaDropdownAdd.object;

  return {
    value: obj?.value ?? params.dropdown,
    label: obj?.label ?? null,
    color: obj?.color ?? null,
    description: obj?.description ?? null,
  };
}
