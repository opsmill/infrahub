import loader from "./loading.gif";

export default function LoadingScreen() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center">
      <img
        className="w-20 h-20"
        src={loader}
      />
      <div className="text-xl mt-2">Just a moment</div>
    </div>
  );
}
