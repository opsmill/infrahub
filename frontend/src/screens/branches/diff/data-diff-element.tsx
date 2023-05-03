import Accordion from "../../../components/accordion";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffProperty } from "./data-diff-property";
import { tDataDiffNodeElement, tDataDiffNodeProperty } from "./data-diff-node";
import { Badge } from "../../../components/badge";
import { DiffPill } from "./diff-pill";
import { diffContent, diffPeerContent } from "../../../utils/diff";

export type tDataDiffNodeElementProps = {
  element: tDataDiffNodeElement,
}

export const DataDiffElement = (props: tDataDiffNodeElementProps) => {
  const { element } = props;

  const {
    action,
    value,
    type,
    identifier,
    name,
    changed_at,
    properties,
    summary,
    peer,
    peers
  } = element;

  const renderDiffDisplay = () => {
    if (value?.action) {
      return diffContent[value.action](value);
    }

    if (peer) {
      return diffPeerContent(peer, action);
    }

    return null;
  };

  const titleContent = (
    <div className="p-2 pr-0 hover:bg-gray-50 grid grid-cols-3 gap-4">
      <div className="flex">
        <Badge>
          {
            type // From Attributes or peer relationship
            || identifier // From peers relationships
          }
        </Badge>

        <span className="mr-2 font-semibold">
          {name}
        </span>
      </div>

      <div className="flex">
        <span className="font-semibold">
          {
            renderDiffDisplay()
          }
        </span>
      </div>

      <div className="flex justify-end">
        <DiffPill {...summary} />

        {
          changed_at
          && (
            <DateDisplay date={changed_at} hideDefault />
          )
        }
      </div>
    </div>
  );

  return (
    <div className="flex flex-col">
      <Accordion title={titleContent}>
        <div className="divide-y">
          {
            properties
            ?.map(
              (property: tDataDiffNodeProperty, index: number) => (
                <DataDiffProperty key={index} property={property} />
              )
            )
          }

          {
            peers
            ?.map(
              (element, index) => (
                <DataDiffElement key={index} element={element} />
              )
            )
          }
        </div>
      </Accordion>
    </div>

  );
};