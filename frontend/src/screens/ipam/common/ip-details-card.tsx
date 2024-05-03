import { Icon } from "@iconify-icon/react";

import { useAtomValue } from "jotai";
import { useState } from "react";
import { ButtonWithTooltip } from "../../../components/buttons/button-primitive";
import SlideOver from "../../../components/display/slide-over";
import ProgressBarChart from "../../../components/stats/progress-bar-chart";
import { Property, PropertyList } from "../../../components/table/property-list";
import { Badge } from "../../../components/ui/badge";
import { CardWithBorder } from "../../../components/ui/card";
import { Link } from "../../../components/utils/link";
import { DEFAULT_BRANCH_NAME } from "../../../config/constants";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { IModelSchema } from "../../../state/atoms/schema.atom";
import { constructPath } from "../../../utils/fetch";
import { AttributeType, ObjectAttributeValue } from "../../../utils/getObjectItemDisplayValue";
import { getObjectDetailsUrl } from "../../../utils/objects";
import ObjectItemEditComponent from "../../object-item-edit/object-item-edit-paginated";
import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "../constants";

type tIpDetailsCard = {
  schema: IModelSchema;
  data: { id: string; display_label: string } & Record<string, AttributeType>;
  refetch: Function;
};

export function IpDetailsCard({ schema, data, refetch }: tIpDetailsCard) {
  const branch = useAtomValue(currentBranchAtom);
  const [showEditDrawer, setShowEditDrawer] = useState(false);

  const properties: Property[] = [
    { name: "ID", value: data.id },
    ...(schema.attributes ?? []).map((schemaAttribute) => {
      if (schemaAttribute.name === "utilization") {
        return {
          name: schemaAttribute.label || schemaAttribute.name,
          value: <ProgressBarChart value={parseInt(data[schemaAttribute.name].value, 10)} />,
        };
      }

      return {
        name: schemaAttribute.label || schemaAttribute.name,
        value: (
          <ObjectAttributeValue
            attributeSchema={schemaAttribute}
            attributeValue={data[schemaAttribute.name]}
          />
        ),
      };
    }),
    ...(schema.relationships ?? [])
      .filter(({ name }) => !IP_SUMMARY_RELATIONSHIPS_BLACKLIST.includes(name))
      .map((schemaRelationship) => {
        const relationshipData = data[schemaRelationship.name]?.node;

        return {
          name: schemaRelationship.label || schemaRelationship.name,
          value: relationshipData && (
            <Link
              to={constructPath(
                getObjectDetailsUrl(relationshipData.id, relationshipData.__typename)
              )}>
              {relationshipData?.display_label}
            </Link>
          ),
        };
      }),
  ];

  return (
    <CardWithBorder>
      <CardWithBorder.Title className="flex items-center justify-between gap-1">
        <div>
          <Badge variant="blue">{schema.namespace}</Badge> {schema.label} summary
        </div>
        <ButtonWithTooltip variant="outline" size="icon" onClick={() => setShowEditDrawer(true)}>
          <Icon icon={"mdi:pencil-outline"} />
        </ButtonWithTooltip>
      </CardWithBorder.Title>

      <PropertyList properties={properties} labelClassName="font-semibold" />

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-start">
              <div className="flex-grow flex items-center flex-wrap overflow-hidden">
                <span className="font-semibold text-gray-900 truncate">{schema.label}</span>

                <Icon icon="mdi:chevron-right" />

                <span className="flex-grow text-gray-500 overflow-hidden break-words line-clamp-3">
                  {data.display_label}
                </span>
              </div>

              <div className="flex items-center ml-3">
                <Icon icon="mdi:layers-triple" />
                <span className="ml-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</span>
              </div>
            </div>

            <div className="">{schema?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {data.id}
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditDrawer(false)}
          onUpdateComplete={() => refetch()}
          objectid={data.id!}
          objectname={schema.kind!}
        />
      </SlideOver>
    </CardWithBorder>
  );
}
