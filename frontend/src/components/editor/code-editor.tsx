// import "prismjs/components/prism-clike";
import { ClipboardDocumentCheckIcon, ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import Prism from "prismjs";
// import "prismjs/components/prism-javascript";
import "prismjs/components/prism-json"; // need this
import "prismjs/themes/prism.css"; //Example style, you can use another

import { useState } from "react";
import Editor from "react-simple-code-editor";
import { toast } from "react-toastify";
import { BUTTON_TYPES, Button } from "../buttons/button";
import { ALERT_TYPES, Alert } from "../utils/alert";

export const CodeEditor = (props: any) => {
  const { onChange, enableCopy, ...propsToPass } = props;

  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    setIsCopied(true);

    await navigator.clipboard.writeText(props.value);

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
          onClick={handleCopy}>
          {!isCopied && <ClipboardDocumentIcon className="h-4 w-4" />}

          {isCopied && <ClipboardDocumentCheckIcon className="h-4 w-4" />}
        </Button>
      )}

      <Editor
        {...propsToPass}
        // value={code}
        onValueChange={(code) => onChange(code)}
        highlight={(code) => Prism.highlight(code, Prism.languages.json, "json")}
        padding={10}
        style={{
          fontFamily: "'Fira code', 'Fira Mono', monospace",
          fontSize: 12,
          resize: "vertical",
        }}
        preClassName="!break-all"
        textareaClassName="!break-all"
        className="rounded-md shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 border-gray-300 bg-custom-white sm:text-sm sm:leading-6 disabled:cursor-not-allowed disabled:bg-gray-100 focus:ring-2 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 focus:outline-none"
      />
    </div>
  );
};
