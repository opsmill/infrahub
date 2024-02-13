import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import { Form } from "../edit-form-hook/form";

const fields: DynamicFieldData[] = [
  {
    name: "password-current",
    label: "Current password",
    type: "text",
    value: "",
  },
  {
    name: "password-new",
    label: "New password",
    type: "text",
    value: "",
  },
  {
    name: "password-confirm",
    label: "Confirm password",
    type: "text",
    value: "",
  },
];

export default function TabAccount() {
  return (
    <div className="flex-1 bg-custom-white">
      <main>
        <div className="px-2">
          <div className="p-4">
            <h2 className="text-base font-semibold leading-7 text-gray-600">Change password</h2>
            <p className="text-sm leading-6 text-gray-400">
              Update your password associated with your account.
            </p>
          </div>
          <Form fields={fields} onSubmit={() => {}} />
          <div className="px-4 py-16 sm:px-6 lg:px-8 max-w-xl">
            <div>
              <h2 className="text-base font-semibold leading-7 text-gray-600">Delete account</h2>
              <p className="text-sm leading-6 text-gray-400">
                No longer want to use our service? You can delete your account here. This action is
                not reversible. All information related to this account will be deleted permanently.
              </p>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
              }}
              className="flex items-start md:col-span-2 mt-4">
              <button
                type="submit"
                className="rounded-md bg-red-500 px-3 py-2 text-sm font-semibold text-custom-white shadow-sm hover:bg-red-400">
                Yes, delete my account
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
