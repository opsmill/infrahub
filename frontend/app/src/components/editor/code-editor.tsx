// import "prismjs/components/prism-clike";
import { ClipboardDocumentCheckIcon, ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import Prism from "prismjs";
// import "prismjs/components/prism-javascript";
import "prismjs/components/prism-json"; // need this
import "prismjs/themes/prism.css"; //Example style, you can use another

import { BUTTON_TYPES, Button } from "@/components/buttons/button";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { classNames } from "@/utils/common";
import { useState } from "react";
import Editor from "react-simple-code-editor";
import { toast } from "react-toastify";

export const CodeEditor = (props: any) => {
  const { value, onChange, enableCopy, dark, ...propsToPass } = props;

  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    setIsCopied(true);

    await navigator.clipboard.writeText(value);

    toast(<Alert message="Content copied" type={ALERT_TYPES.INFO} />);

    setTimeout(() => {
      setIsCopied(false);
    }, 3000);
  };

  return (
    <div className="relative">
      {enableCopy && (
        <Button
          className="absolute z-10 top-0 right-0"
          buttonType={BUTTON_TYPES.INVISIBLE}
          onClick={handleCopy}
        >
          {!isCopied && <ClipboardDocumentIcon className="h-4 w-4" />}

          {isCopied && <ClipboardDocumentCheckIcon className="h-4 w-4" />}
        </Button>
      )}

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
