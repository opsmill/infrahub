import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT } from "@/config/constants";
import { parseJwt } from "@/utils/common";
import ObjectItemDetails from "../object-item-details/object-item-details-paginated";

export default function TabProfile() {
  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const accountId = tokenData?.sub;

  return <ObjectItemDetails objectname={ACCOUNT_OBJECT} objectid={accountId} hideHeaders />;
}
