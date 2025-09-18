import { forwardRef, type HTMLAttributes, useMemo } from "react";

import { classNames } from "@/shared/utils/common";

export type KbdKey =
  | "command"
  | "shift"
  | "ctrl"
  | "option"
  | "enter"
  | "delete"
  | "escape"
  | "tab";

export const kbdKeysMap: Record<KbdKey, string> = {
  command: "⌘",
  shift: "⇧",
  ctrl: "⌃",
  option: "⌥",
  enter: "↵",
  delete: "⌫",
  escape: "⎋",
  tab: "⇥",
};

export const kbdKeysLabelMap: Record<KbdKey, string> = {
  command: "Command",
  shift: "Shift",
  ctrl: "Control",
  option: "Option",
  enter: "Enter",
  delete: "Delete",
  escape: "Escape",
  tab: "Tab",
};

export interface KbdProps extends HTMLAttributes<HTMLElement> {
  keys?: KbdKey | KbdKey[];
  keyClassName?: string;
}

const Kbd = forwardRef<HTMLElement, KbdProps>((props, ref) => {
  const { children, keys, keyClassName, className } = props;

  const keysToRender = typeof keys === "string" ? [keys] : Array.isArray(keys) ? keys : [];

  const keysContent = useMemo(() => {
    return keysToRender.map((key) => (
      <abbr
        key={key}
        title={kbdKeysLabelMap[key]}
        className={classNames("no-underline", keyClassName)}
      >
        {kbdKeysMap[key]}
      </abbr>
    ));
  }, [keysToRender.toString()]);

  return (
    <kbd
      ref={ref}
      className={classNames(
        "rounded-sm bg-gray-100 px-1.5 py-0.5 font-sans text-gray-600 text-xs",
        className
      )}
    >
      {keysContent}
      {children && <span>{children}</span>}
    </kbd>
  );
});

export default Kbd;
