import { ACCESS_TOKEN_KEY } from "../../config/constants";
import { parseJwt } from "../../utils/common";
import ObjectItems from "../object-items/object-items-paginated";

export default function TabProfile() {
  const localToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const accountId = tokenData?.sub;

  const filters = [`account__id: "${accountId}"`];

  return <ObjectItems objectname={"account_token"} filters={filters} />;
}
