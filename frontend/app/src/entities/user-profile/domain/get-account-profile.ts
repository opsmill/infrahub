import { getAccountProfileFromApi } from "@/entities/user-profile/api/get-account-profile-from-api";

export const getAccountProfile = async () => {
  const { data, errors } = await getAccountProfileFromApi();

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const account = data?.AccountProfile;

  if (!account) {
    throw new Error("No account found");
  }

  return account;
};
