import { parseJwt } from "@/utils/common";
import { ACCESS_TOKEN_KEY, ACCOUNT_TOKEN_OBJECT } from "../../config/constants";
import ObjectItems from "../object-items/object-items-paginated";

export default function TabProfile() {
  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const accountId = tokenData?.sub;

  const filters = [`account__ids: "${accountId}"`];

  return <ObjectItems objectname={ACCOUNT_TOKEN_OBJECT} filters={filters} preventBlock />;
}
