import Accordion from "../../../components/accordion";
import { DataDiffProperty } from "./data-diff-property";
import { tDataDiffNodeElement, tDataDiffNodeProperty } from "./data-diff-node";
import { Badge } from "../../../components/badge";
import { DiffPill } from "./diff-pill";
import { diffContent, diffPeerContent } from "../../../utils/diff";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { DateDisplay } from "../../../components/date-display";
import { constructPath } from "../../../utils/fetch";
import { getObjectDetailsUrl } from "../../../utils/objects";
import { useAtom } from "jotai";
import { schemaKindNameState } from "../../../state/atoms/schemaKindName.atom";
import { useNavigate } from "react-router-dom";

export type tDataDiffNodeElementProps = {
  element: tDataDiffNodeElement;
};

export const DataDiffElement = (props: tDataDiffNodeElementProps) => {
  const { element } = props;

  const [schemaKindName] = useAtom(schemaKindNameState);
  const navigate = useNavigate();

  const {
    branch,
    action,
    value,
    name,
    changed_at,
    properties,
    summary,
    peer,
    peers,
  } = element;

  const renderDiffDisplay = () => {
    if (value?.action) {
      return diffContent[value.action](value);
    }

    if (peer?.kind && peer?.id) {
      const objectUrl = getObjectDetailsUrl(
        { __typename: peer.kind },
        schemaKindName,
        peer.id
      );

      const url = branch
        ? constructPath(`${objectUrl}?branch=${branch}`)
        : constructPath(objectUrl);

      const onClick = () => navigate(url);

      return diffPeerContent(peer, action, onClick);
    }

    return null;
  };

  const titleContent = (
    <div className="p-2 pr-0 hover:bg-gray-50 grid grid-cols-3 gap-4">
      <div className="flex">
        {!name && peer?.kind && <Badge>{peer?.kind}</Badge>}

        <span className="mr-2 font-semibold">{name}</span>
      </div>

      <div className="flex">
        <span className="font-semibold">{renderDiffDisplay()}</span>
      </div>

      <div className="flex justify-end">
        <DiffPill {...summary} />

        <div className="w-[160px] flex justify-end">
          {changed_at && <DateDisplay date={changed_at} hideDefault />}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col">
      {properties?.length || peers?.length ? (
        <Accordion title={titleContent}>
          <div className="divide-y">
            {properties?.map(
              (property: tDataDiffNodeProperty, index: number) => (
                <DataDiffProperty key={index} property={property} />
              )
            )}

            {peers?.map((element, index) => (
              <DataDiffElement key={index} element={element} />
            ))}
          </div>
        </Accordion>
      ) : (
        <div className="flex">
          {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
          <ChevronDownIcon
            className="h-5 w-5 mr-2 text-transparent"
            aria-hidden="true"
          />
          <div className="flex-1">{titleContent}</div>
        </div>
      )}
    </div>
  );
};
