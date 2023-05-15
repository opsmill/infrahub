import { Cog6ToothIcon } from "@heroicons/react/24/outline";
import { StringParam, useQueryParam } from "use-query-params";
import { Avatar } from "../../components/avatar";
import { Tabs } from "../../components/tabs";
import { QSP } from "../../config/qsp";
import TabPassword from "./tab-account";
import TabPreferences from "./tab-preferences";
import TabProfile from "./tab-profile";
import TabTokens from "./tab-tokens";

const PROFILE_TABS = {
  PREFERENCES: "preferences",
  PROFILE: "profile",
  TOKENS: "tokens",
  ACCOUNT: "account",
};

const tabs = [
  {
    label: "Profile",
    name: PROFILE_TABS.PROFILE,
  },
  {
    label: "Preferences",
    name: PROFILE_TABS.PREFERENCES,
  },
  {
    label: "API Tokens",
    name: PROFILE_TABS.TOKENS,
  },
  {
    label: "Account",
    name: PROFILE_TABS.ACCOUNT,
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch (tab) {
    case PROFILE_TABS.TOKENS:
      return <TabTokens />;
    case PROFILE_TABS.ACCOUNT:
      return <TabPassword />;
    case PROFILE_TABS.PREFERENCES:
      return <TabPreferences />;
    default:
      return <TabProfile />;
  }
};

export default function UserProfile() {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  return (
    <div className="flex flex-col flex-1 overflow-auto">
      <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
        <div className="-ml-4 -mt-4 flex flex-wrap items-center justify-between sm:flex-nowrap">
          <div className="ml-4 mt-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Avatar
                  image="https://shotkit.com/wp-content/uploads/2020/07/headshots_image002.jpg"
                  name="Richard Martin"
                />
              </div>
              <div className="ml-4">
                <h3 className="text-base font-semibold leading-6 text-gray-900">Richard Martin</h3>
                <p className="text-sm text-gray-500">
                  <a href="#">@rmartin</a>
                </p>
              </div>
            </div>
          </div>
          <div className="ml-4 mt-4 flex flex-shrink-0">
            <Cog6ToothIcon className="w-6 h-6 text-gray-600 cursor-pointer hover:scale-110" />
          </div>
        </div>
      </div>
      <div className="sticky top-0 z-10 shadow-sm">
        <Tabs tabs={tabs} />
      </div>
      {renderContent(qspTab)}
    </div>
  );
}
