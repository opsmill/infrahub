import { StringParam, useQueryParam } from "use-query-params";
import { IPAM_QSP, IPAM_TABS } from "../constants";
import IpamIPAddresses from "../ip-addresses/ipam-ip-address";
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
