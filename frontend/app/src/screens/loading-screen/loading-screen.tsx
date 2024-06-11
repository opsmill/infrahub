import { classNames } from "@/utils/common";
import ReactLoading, { LoadingType } from "react-loading";

interface Props {
  size?: string | number;
  hideText?: boolean;
  className?: string;
  colorClass?: string;
  type?: LoadingType;
}

export default function LoadingScreen(props: Props) {
  const { hideText, size, className, colorClass, type } = props;

  const color = colorClass ?? "!fill-custom-blue-500";

  return (
    <div
      className={classNames(
        "flex-1 flex flex-col items-center justify-center h-auto w-auto",
        className ?? ""
      )}>
      <ReactLoading
        className={color}
        type={type ?? "bars"}
        height={size ?? 70}
        width={size ?? 70}
      />
      {!hideText && <div className="text-xl mt-2">Just a moment</div>}
    </div>
  );
}
