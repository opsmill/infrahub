import errorimage from "./images/error.webp";

export default function ErrorScreen() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center">
      <img alt="Page error" className="w-56 h-56 object-cover" src={errorimage} />
      <div className="text-xl mt-2">Something went wrong. We are looking into it</div>
    </div>
  );
}
