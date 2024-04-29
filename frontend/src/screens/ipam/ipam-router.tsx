import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { ButtonWithTooltip } from "../../components/buttons/button-with-tooltip";
import SlideOver from "../../components/display/slide-over";
import { Tabs } from "../../components/tabs";
import { Card } from "../../components/ui/card";
import { DEFAULT_BRANCH_NAME } from "../../config/constants";
import { usePermission } from "../../hooks/usePermission";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import ObjectItemCreate from "../object-item-create/object-item-create-paginated";
import {
  IPAM_QSP,
  IPAM_ROUTE,
  IPAM_TABS,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "./constants";
import IpamIPAddresses from "./ip-addresses/ipam-ip-address";
import IpamIPPrefixes from "./prefixes/ipam-prefixes";

const tabToKind = {
  [IPAM_TABS.IP_DETAILS]: IP_ADDRESS_GENERIC,
  [IPAM_TABS.PREFIX_DETAILS]: IP_PREFIX_GENERIC,
};

export default function IpamRouter() {
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);
  const navigate = useNavigate();
  const { prefix } = useParams();
  const permission = usePermission();
  const branch = useAtomValue(currentBranchAtom);
  const schemaList = useAtomValue(schemaState);
  const genericList = useAtomValue(genericsState);
  const refetchRef = useRef(null);

  const objectname = qspTab ? tabToKind[qspTab] : IP_PREFIX_GENERIC;
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
          navigate(`${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(prefix)}`);
          return;
        }

        navigate(IPAM_ROUTE.PREFIXES);
        return;
      },
    },
    {
      label: "Prefix Details",
      name: IPAM_TABS.PREFIX_DETAILS,
      onClick: () => {
        if (prefix) {
          navigate(
            `${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(prefix)}?${IPAM_QSP}=${
              IPAM_TABS.PREFIX_DETAILS
            }`
          );
          return;
        }

        navigate(`${IPAM_ROUTE.PREFIXES}?${IPAM_QSP}=${IPAM_TABS.PREFIX_DETAILS}`);
        return;
      },
    },
    {
      label: "IP Details",
      name: IPAM_TABS.IP_DETAILS,
      onClick: () => {
        if (prefix) {
          navigate(
            `${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(prefix)}?${IPAM_QSP}=${
              IPAM_TABS.IP_DETAILS
            }`
          );
          return;
        }

        navigate(`${IPAM_ROUTE.ADDRESSES}?${IPAM_QSP}=${IPAM_TABS.IP_DETAILS}`);
        return;
      },
    },
  ];

  const renderContent = () => {
    switch (qspTab) {
      case IPAM_TABS.IP_DETAILS: {
        return <IpamIPAddresses ref={refetchRef} />;
      }
      case IPAM_TABS.PREFIX_DETAILS:
      default: {
        return <IpamIPPrefixes ref={refetchRef} />;
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
    <Card className="p-0 overflow-hidden flex flex-col h-full">
      <Tabs tabs={tabs} qsp={IPAM_QSP} rightItems={rightitems} />

      <div className="m-4 flex-grow overflow-auto">{renderContent()}</div>

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
          refetch={refetchRef?.current?.refetch}
        />
      </SlideOver>
    </Card>
  );
}
