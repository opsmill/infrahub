// type PopOver = {}

import { Popover } from "@headlessui/react";
import { CSSProperties, forwardRef, useState } from "react";
import { usePopper } from "react-popper";
import { classNames } from "../../utils/common";
import Transition from "../utils/transition";

export enum POPOVER_SIZE {
  NONE,
  SMALL,
  MEDIUM,
  LARGE,
}

type PopOverProps = {
  children?: any;
  className?: string;
  buttonComponent?: any;
  fixed?: boolean;
  title?: string;
  disabled?: boolean;
  width?: POPOVER_SIZE;
  height?: POPOVER_SIZE;
  maxWidth?: POPOVER_SIZE;
  maxHeight?: POPOVER_SIZE;
  static?: boolean;
  style?: CSSProperties;
  open?: boolean;
};

const widthClass = {
  [POPOVER_SIZE.NONE]: "",
  [POPOVER_SIZE.SMALL]: "w-[300px]",
  [POPOVER_SIZE.MEDIUM]: "w-[500px]",
  [POPOVER_SIZE.LARGE]: "w-[800px]",
};

const heightClass = {
  [POPOVER_SIZE.NONE]: "",
  [POPOVER_SIZE.SMALL]: "h-[300px]",
  [POPOVER_SIZE.MEDIUM]: "h-[500px]",
  [POPOVER_SIZE.LARGE]: "h-[800px]",
};

const maxWidthClass = {
  [POPOVER_SIZE.NONE]: "",
  [POPOVER_SIZE.SMALL]: "max-w-[300px]",
  [POPOVER_SIZE.MEDIUM]: "max-w-[500px]",
  [POPOVER_SIZE.LARGE]: "max-w-[800px]",
};

const maxHeightClass = {
  [POPOVER_SIZE.NONE]: "",
  [POPOVER_SIZE.SMALL]: "max-h-[300px]",
  [POPOVER_SIZE.MEDIUM]: "max-h-[500px]",
  [POPOVER_SIZE.LARGE]: "max-h-[800px]",
};

const PopOverPanel = forwardRef<HTMLDivElement, PopOverProps>(
  (
    { className, title, children, static: staticProp, width, height, maxWidth, maxHeight, style },
    ref
  ) => {
    return (
      <Popover.Panel
        ref={ref}
        className={classNames(
          "absolute overflow-scroll z-10 rounded-lg border shadow-xl grid grid-cols-1 divide-y divide-gray-200",
          className?.includes("bg-") ? "" : "bg-custom-white",
          className ?? "",
          widthClass[width ?? POPOVER_SIZE.NONE],
          heightClass[height ?? POPOVER_SIZE.NONE],
          maxWidthClass[maxWidth ?? POPOVER_SIZE.NONE],
          maxHeightClass[maxHeight ?? POPOVER_SIZE.NONE]
        )}
        style={style}
        static={staticProp}>
        {({ close }) => (
          <>
            {title && <div className="font-semibold text-center p-2">{title}</div>}

            <div className="flex-1 p-2">
              {typeof children === "function" ? children({ close }) : children}
            </div>
          </>
        )}
      </Popover.Panel>
    );
  }
);

export const PopOver = (props: PopOverProps) => {
  const { buttonComponent, fixed, disabled, static: staticProp, open, ...propsToPass } = props;
  let [referenceElement, setReferenceElement] = useState();
  let [popperElement, setPopperElement] = useState();
  let { styles, attributes } = usePopper(referenceElement, popperElement, {
    modifiers: [
      {
        name: "preventOverflow",
        enabled: !fixed,
        options: {
          padding: 8,
        },
      },
    ],
  });

  if (staticProp) {
    return <Popover className="flex-1">{open && <PopOverPanel {...propsToPass} static />}</Popover>;
  }

  return (
    <Popover>
      <Popover.Button as="div" className="h-full" disabled={disabled} ref={setReferenceElement}>
        {buttonComponent}
      </Popover.Button>

      <Transition>
        <PopOverPanel
          {...propsToPass}
          ref={setPopperElement}
          style={styles.popper}
          {...attributes.popper}
        />
      </Transition>
    </Popover>
  );
};
