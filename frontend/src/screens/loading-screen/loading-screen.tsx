import loader from "./loading.gif";

interface Props {
  size?: string;
  hideText?: boolean;
}

export default function LoadingScreen(props: Props) {
  const { hideText, size } = props;
  const sizeClass = props.size ? `w-${size} h-${size}` : "w-20 h-20";
  return (
    <div className="flex-1 flex flex-col items-center justify-center">
      <img alt="Loading" className={`${sizeClass}`} src={loader} />
      {!hideText && <div className="text-xl mt-2">Just a moment</div>}
    </div>
  );
}
