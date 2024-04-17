import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Tabs } from "../../components/tabs";
import { IPAM_QSP, IPAM_TABS } from "./constants";
import IpamIPAddresses from "./ip-addresses/ipam-ip-address";
import IpamIPPrefixes from "./prefixes/ipam-prefixes";

export default function IpamRouter() {
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);
  const navigate = useNavigate();
  const { prefix } = useParams();

  const tabs = [
    {
      label: "Summary",
      name: IPAM_TABS.SUMMARY,
      onClick: () => {
        if (prefix) {
          navigate(`/ipam/prefixes/${encodeURIComponent(prefix)}`);
          return;
        }

        navigate("/ipam/prefixes");
        return;
      },
    },
    {
      label: "Prefix Details",
      name: IPAM_TABS.PREFIX_DETAILS,
      onClick: () => {
        if (prefix) {
          navigate(
            `/ipam/prefixes/${encodeURIComponent(prefix)}?${IPAM_QSP}=${IPAM_TABS.PREFIX_DETAILS}`
          );
          return;
        }

        navigate(`/ipam/prefixes?${IPAM_QSP}=${IPAM_TABS.PREFIX_DETAILS}`);
        return;
      },
    },
    {
      label: "IP Details",
      name: IPAM_TABS.IP_DETAILS,
      onClick: () => {
        if (prefix) {
          navigate(
            `/ipam/prefixes/${encodeURIComponent(prefix)}?${IPAM_QSP}=${IPAM_TABS.IP_DETAILS}`
          );
          return;
        }

        navigate(`/ipam/ip-addresses?${IPAM_QSP}=${IPAM_TABS.IP_DETAILS}`);
        return;
      },
    },
  ];

  const renderContent = () => {
    switch (qspTab) {
      case IPAM_TABS.IP_DETAILS: {
        return <IpamIPAddresses />;
      }
      case IPAM_TABS.PREFIX_DETAILS: {
        return <IpamIPPrefixes />;
      }
      default: {
        return <IpamIPPrefixes />;
      }
    }
  };

  return (
    <div>
      <Tabs tabs={tabs} qsp={IPAM_QSP} />

      <div className="m-4">{renderContent()}</div>
    </div>
  );
}
