import { forwardRef, HTMLAttributes, useMemo } from "react";
import { classNames } from "../../utils/common";

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
}

const Kbd = forwardRef<HTMLElement, KbdProps>((props, ref) => {
  const { children, keys, className } = props;

  const keysToRender = typeof keys === "string" ? [keys] : Array.isArray(keys) ? keys : [];

  const keysContent = useMemo(() => {
    return keysToRender.map((key) => (
      <abbr key={key} title={kbdKeysLabelMap[key]} className="no-underline">
        {kbdKeysMap[key]}
      </abbr>
    ));
  }, [keysToRender.toString()]);

  return (
    <kbd
      ref={ref}
      className={classNames(
        "text-gray-600 bg-gray-100 font-sans py-0.5 px-1.5 rounded-md text-xs",
        className
      )}>
      {keysContent}
      {children && <span>{children}</span>}
    </kbd>
  );
});

export default Kbd;
