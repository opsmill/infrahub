import { IPAM_QSP, IPAM_TABS } from "@/entities/ipam/constants";
import IpamIPAddresses from "@/entities/ipam/ip-addresses/ipam-ip-address";
import { forwardRef } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import IpamIPPrefixDetails from "./ipam-prefix-details";
import IpamIPPrefixesSummary from "./ipam-prefixes-summary";

const IpamIPPrefixes = forwardRef((_, ref) => {
  const [qspTab] = useQueryParam(IPAM_QSP.TAB, StringParam);

  switch (qspTab) {
    case IPAM_TABS.PREFIX_DETAILS: {
      return <IpamIPPrefixDetails ref={ref} />;
    }
    case IPAM_TABS.IP_DETAILS: {
      return <IpamIPAddresses ref={ref} />;
    }
    default: {
      return <IpamIPPrefixesSummary ref={ref} />;
    }
  }
});

export default IpamIPPrefixes;
