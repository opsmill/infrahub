import { CopyToClipboard } from "../buttons/copy-to-clipboard";

type TokenInputProps = {
  value: string;
};

export const TokenInput = (props: TokenInputProps) => {
  return (
    <div className="flex items-center">
      <div className="p-2 bg-gray-100 rounded-md h-9">{props.value}</div>

      <CopyToClipboard
        text={props.value as string}
        size={"square"}
        variant={"primary"}
        className="ml-2"
      />
    </div>
  );
};
