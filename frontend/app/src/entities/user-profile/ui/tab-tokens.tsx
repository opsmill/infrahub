import { AccountTokenCreateAction } from "@/entities/user-profile/ui/account-token-create-action";
import { AccountTokenList } from "@/entities/user-profile/ui/account-token-list";

export default function TabTokens() {
  return (
    <main className="p-4">
      <div className="mb-4 flex justify-between p-2">
        <div>
          <h1 className="font-semibold text-xl">Infrahub account tokens</h1>
          <p className="text-gray-600 text-sm">
            Account tokens can be used as an authentication mechanism for Infrahub's REST- and
            GraphQL API, the Python SDK and infrahubctl.
          </p>
        </div>

        <AccountTokenCreateAction />
      </div>

      <AccountTokenList />
    </main>
  );
}
