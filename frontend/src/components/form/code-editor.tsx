import { FormFieldError } from "../../screens/edit-form-hook/form";
import { classNames } from "../../utils/common";
import { CodeEditor } from "../editor/code-editor";

type tOpsCodeEditor = {
  label: string;
  value: string | null;
  onChange: (value: string) => void;
  className?: string;
  error?: FormFieldError;
};

export const OpsCodeEditor = (props: tOpsCodeEditor) => {
  const { className, onChange, value, label, error } = props;

  return (
    <>
      <label className="block text-sm font-medium leading-6 text-gray-900">{label}</label>
      <CodeEditor
        onChange={onChange}
        value={value}
        className={classNames(className ?? "")}
        error={error}
      />
    </>
  );
};
