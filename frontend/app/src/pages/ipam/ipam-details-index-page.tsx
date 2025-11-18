import { Navigate, useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";

import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { constructPathForIpam } from "@/entities/ipam/utils";
import type { NodeAttribute } from "@/entities/nodes/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

const IpamDetailsIndexPage = () => {
  const { objectKind, objectId } = useParams();
  const { parentSchema, parentData } = useCurrentFormContext();

  if (!parentSchema) {
    return <ErrorScreen message={`Schema ${objectKind} not found`} />;
  }

  if (!parentData) {
    return <ErrorScreen message={`${parentSchema.label} with id ${objectId} not found`} />;
  }

  if (isOfKind(IP_PREFIX_GENERIC, parentSchema)) {
    const memberType = (parentData.member_type as NodeAttribute)?.value;

    if (memberType === "prefix") {
      return <Navigate to={constructPathForIpam("children")} replace />;
    }

    if (memberType === "address") {
      return <Navigate to={constructPathForIpam("ip_addresses")} replace />;
    }
  }

  return <Navigate to={constructPathForIpam("details")} replace />;
};

export const Component = IpamDetailsIndexPage;
