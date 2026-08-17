import type React from "react";

import "./prism-setup";

import Prism from "prismjs";
import "prismjs/components/prism-json";

import EditorImport from "react-simple-code-editor";

import { focusWithinStyle, inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

// Handle CJS/ESM interop — Vite may double-wrap the default export
const Editor =
  "default" in EditorImport
    ? (EditorImport as unknown as { default: typeof EditorImport }).default
    : EditorImport;

interface JsonEditorProps {
  onChange: (value: string) => void;
  defaultValue?: string;
  disabled?: boolean;
  value?: string;
  className?: string;
  id?: string;
  ref?: React.Ref<React.ComponentRef<typeof Editor>>;
}

export const JsonEditor = ({ id, onChange, value, className, ref, ...props }: JsonEditorProps) => {
  return (
    <Editor
      onValueChange={onChange}
      ref={ref}
      textareaId={id}
      ignoreTabKey={true}
      value={value ? (typeof value === "string" ? value : JSON.stringify(value)) : ""}
      style={{
        fontFamily: "'Fira code', 'Fira Mono', monospace",
        fontSize: 12,
      }}
      preClassName="break-all!"
      textareaClassName="break-all disabled:cursor-not-allowed disabled:opacity-60 rounded-[inherit]"
      className={classNames(focusWithinStyle, inputStyle, className)}
      {...props}
      padding={10}
      highlight={(code) => Prism.highlight(code, Prism.languages.json, "json")}
    />
  );
};
