import { Cog6ToothIcon } from "@heroicons/react/24/outline";

export default function TabPreferences() {
  return (
    <div className="bg-custom-white flex-1 p-8">
      <div className="flex relative justify-center items-center w-full rounded-lg border-2 border-dashed border-gray-300 p-12 text-center hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-custom-blue-500 focus:ring-offset-2">
        <Cog6ToothIcon className="w-6 h-6 text-gray-600" />
        <div className="text-gray-700 ml-2">User preferences here</div>
      </div>
    </div>
  );
}
