import {
  type UpdateAccountPasswordFromApiParams,
  updateAccountPasswordFromApi,
} from "@/entities/user-profile/api/update-account-password-from-api";

export type UpdateAccountPasswordParams = UpdateAccountPasswordFromApiParams;

export async function updateAccountPassword(params: UpdateAccountPasswordParams): Promise<void> {
  const { data, errors } = await updateAccountPasswordFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.InfrahubAccountSelfUpdate?.ok) {
    throw new Error("InfrahubAccountSelfUpdate did not return ok");
  }
}
