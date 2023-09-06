// import "prismjs/components/prism-clike";
import Prism from "prismjs";
// import "prismjs/components/prism-javascript";
import "prismjs/components/prism-json"; // need this
import "prismjs/themes/prism.css"; //Example style, you can use another

import Editor from "react-simple-code-editor";

export const CodeEditor = (props: any) => {
  const { onChange, ...propsToPass } = props;

  return (
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
      className="rounded-md shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 border-gray-300 bg-custom-white sm:text-sm sm:leading-6 disabled:cursor-not-allowed disabled:bg-gray-100 focus:ring-2 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 focus:outline-none"
    />
  );
};
