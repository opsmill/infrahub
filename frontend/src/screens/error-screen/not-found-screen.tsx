import notFoundImage from "./images/not-found.webp";

export default function NotFoundScreen() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center">
      <img
        alt="Page error"
        className="w-56 h-56 object-cover"
        src={notFoundImage}
      />
      <div className="text-xl mt-2">404 not found</div>
    </div>
  );
}