import { Popover } from "@headlessui/react";
import { InformationCircleIcon } from "@heroicons/react/24/outline";
import { formatDistance } from "date-fns";
import { useAtom } from "jotai";
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { classNames } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { usePopper } from "react-popper";

export type TooltipDetailItemType = "date" | "text" | "link";

interface TooltipListItem {
  label: string;
  type: TooltipDetailItemType;
  value: any;
}

interface Props {
  items: TooltipListItem[];
  header?: React.ReactNode;
}

export default function MetaDetailsTooltip(props: Props) {
  const { header, items } = props;

  const navigate = useNavigate();
  const [schemaKindName] = useAtom(schemaKindNameState);
  let [referenceElement, setReferenceElement] = useState<HTMLButtonElement | null>();
  let [popperElement, setPopperElement] = useState<HTMLDivElement | null>();
  let { styles, attributes } = usePopper(referenceElement, popperElement, {
    modifiers: [
      {
        name: "flip",
      },
    ],
  });

  const navigateToObjectDetailsPage = (obj: any) =>
    navigate(constructPath(`/objects/${schemaKindName[obj.__typename]}/${obj.id}`));

  // TODO: use the popover component
  return (
    <Popover className="flex">
      <Popover.Button data-testid="view-metadata-button" ref={setReferenceElement}>
        <div className="w-4 h-4" data-cy="metadata-button">
          <InformationCircleIcon className="w-4 h-4 text-gray-500" />
        </div>
      </Popover.Button>

      <Popover.Panel
        ref={setPopperElement}
        style={styles.popper}
        {...attributes.popper}
        className={classNames("z-10 bg-custom-white rounded-lg border shadow-xl")}
        data-testid="metadata-tooltip"
        data-cy="metadata-tooltip">
        <div className="w-80 text-sm divide-y">
          {!!header && header}
          {items.map((item) => {
            return (
              <div key={item.label} className="flex justify-between items-center w-full p-4">
                <div>{item.label}: </div>
                {item.type === "date" && item.value && (
                  <div>{formatDistance(new Date(item.value), new Date(), { addSuffix: true })}</div>
                )}

                {item.type === "link" && (
                  <div
                    className="underline cursor-pointer"
                    onClick={() => navigateToObjectDetailsPage(item.value)}>
                    {item.value?.display_label}
                  </div>
                )}

                {item.type === "text" && <div>{item.value}</div>}
              </div>
            );
          })}
        </div>
      </Popover.Panel>
    </Popover>
  );
}
