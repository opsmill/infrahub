import type React from "react";

import "./prism-setup";

import Prism from "prismjs";
import "prismjs/components/prism-json";

import EditorImport from "react-simple-code-editor";

import { focusWithinStyle } from "@/shared/components/ui/style";
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
      textareaClassName="break-all! text-red-100! disabled:cursor-not-allowed disabled:bg-gray-100! mix-blend-multiply" // text-red-100 needed to make highligted text (in browser search) visible
      className={classNames(
        "w-full rounded-md border border-gray-300 bg-white text-sm shadow-xs placeholder:text-gray-400",
        focusWithinStyle,
        className
      )}
      {...props}
      padding={10}
      highlight={(code) => Prism.highlight(code, Prism.languages.json, "json")}
    />
  );
};
