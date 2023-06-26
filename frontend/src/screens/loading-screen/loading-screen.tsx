import ReactLoading from "react-loading";
import { classNames } from "../../utils/common";

interface Props {
  size?: string | number;
  hideText?: boolean;
  className?: string;
  colorClass?: string;
}

export default function LoadingScreen(props: Props) {
  const { hideText, size, className, colorClass } = props;

  const color = colorClass ?? "!fill-custom-blue";

  return (
    <div
      className={classNames(
        "flex-1 flex flex-col items-center justify-center h-auto w-auto",
        className ?? ""
      )}>
      <ReactLoading className={color} type={"bars"} height={size ?? 70} width={size ?? 70} />
      {!hideText && <div className="text-xl mt-2">Just a moment</div>}
    </div>
  );
}
