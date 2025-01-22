// import "prismjs/components/prism-clike";
import Prism from "prismjs";
// import "prismjs/components/prism-javascript";
import "prismjs/components/prism-json"; // need this
import "prismjs/themes/prism.css"; //Example style, you can use another

import { classNames } from "@/shared/utils/common";
import Editor from "react-simple-code-editor";
import { CopyToClipboard } from "../../buttons/copy-to-clipboard";

export const CodeEditor = (props: any) => {
  const { value, onChange, enableCopy, dark, ...propsToPass } = props;

  return (
    <div className="relative">
      {enableCopy && <CopyToClipboard text={value} />}

      <Editor
        {...propsToPass}
        value={value ? (typeof value === "string" ? value : JSON.stringify(value)) : ""}
        onValueChange={onChange}
        highlight={(code) => Prism.highlight(code, Prism.languages.json, "json")}
        padding={10}
        style={{
          fontFamily: "'Fira code', 'Fira Mono', monospace",
          fontSize: 12,
          resize: "vertical",
        }}
        preClassName="!break-all"
        textareaClassName="!break-all !text-red-100" // text-red-100 needed to make highligted text (in browser search) visible
        className={classNames(
          "rounded-md shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 border-gray-300 text-sm disabled:cursor-not-allowed disabled:bg-gray-300 focus:ring-2 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 focus:outline-none",
          dark ? "text-gray-300 bg-gray-800" : "bg-custom-white"
        )}
      />
    </div>
  );
};
