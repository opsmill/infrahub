import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { ButtonWithTooltip } from "../../components/buttons/button-with-tooltip";
import SlideOver from "../../components/display/slide-over";
import { Tabs } from "../../components/tabs";
import {
  DEFAULT_BRANCH_NAME,
  IPAM_IP_ADDRESS_GENERIC,
  IPAM_PREFIX_GENERIC,
  IPAM_PREFIX_OBJECT,
} from "../../config/constants";
import { usePermission } from "../../hooks/usePermission";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import ObjectItemCreate from "../object-item-create/object-item-create-paginated";
import { IPAM_QSP, IPAM_TABS } from "./constants";
import IpamIPAddresses from "./ip-addresses/ipam-ip-address";
import IpamIPPrefixes from "./prefixes/ipam-prefixes";

const tabToKind = {
  [IPAM_TABS.IP_DETAILS]: IPAM_IP_ADDRESS_GENERIC,
  [IPAM_TABS.PREFIX_DETAILS]: IPAM_PREFIX_GENERIC,
};

export default function IpamRouter() {
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);
  const navigate = useNavigate();
  const { prefix } = useParams();
  const permission = usePermission();
  const branch = useAtomValue(currentBranchAtom);
  const schemaList = useAtomValue(schemaState);
  const genericList = useAtomValue(genericsState);
  const objectname = qspTab ? tabToKind[qspTab] : IPAM_PREFIX_OBJECT;
  const schema = schemaList.find((s) => s.kind === objectname);
  const generic = genericList.find((s) => s.kind === objectname);
  const schemaData = schema || generic;

  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

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

  const rightitems = (
    <ButtonWithTooltip
      disabled={!permission.write.allow}
      tooltipEnabled={!permission.write.allow}
      tooltipContent={permission.write.message ?? undefined}
      onClick={() => setShowCreateDrawer(true)}
      className="mr-4"
      data-testid="create-object-button">
      <Icon icon="mdi:plus" className="text-sm" />
      Add {schemaData?.label}
    </ButtonWithTooltip>
  );

  return (
    <div>
      <Tabs tabs={tabs} qsp={IPAM_QSP} rightItems={rightitems} />

      <div className="m-4">{renderContent()}</div>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">Create {schemaData?.label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>

            <div className="text-sm">{schemaData?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schemaData?.kind}
            </span>
          </div>
        }
        open={showCreateDrawer}
        setOpen={setShowCreateDrawer}>
        <ObjectItemCreate
          onCreate={() => setShowCreateDrawer(false)}
          onCancel={() => setShowCreateDrawer(false)}
          objectname={objectname!}
          // refetch={refetch}
        />
      </SlideOver>
    </div>
  );
}
