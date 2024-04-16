import { StringParam, useQueryParam } from "use-query-params";
import IpamIPAddresses from "../ipam-ip-address";
import { IPAM_QSP, IPAM_TABS } from "./constants";
import IpamIPPrefixDetails from "./ipam-prefix-details";
import IpamIPPrefixesSummary from "./ipam-prefixes-summary";

export default function IpamIPPrefixes() {
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);

  switch (qspTab) {
    case IPAM_TABS.PREFIX_DETAILS: {
      return <IpamIPPrefixDetails />;
    }
    case IPAM_TABS.IP_DETAILS: {
      return <IpamIPAddresses />;
    }
    default: {
      return <IpamIPPrefixesSummary />;
    }
  }
}
