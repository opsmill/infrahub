import { useState } from "react";
import { Select2Step, iTwoStepDropdownData } from "../components/select-2-step";
import { SelectOption } from "../components/select";

const optionsLeft: SelectOption[] = [
  {
    name: "Account",
    id: "account"
  },
  {
    name: "Group",
    id: "group"
  },
  {
    name: "Repository",
    id: "repository"
  }
];

export const Select2StepPreview = () => {
  const [value, setValue] = useState<iTwoStepDropdownData>();
  return (
    <div className="bg-white py-12 flex-1 overflow-auto">
      <div className="mx-auto px-6 lg:px-8">
        <div className="mx-auto grid grid-cols-1 items-start gap-x-8 gap-y-6 sm:gap-y-10 lg:mx-0 lg:max-w-none lg:grid-cols-1">
          <div className="col-span-8 sm:col-span-3">
            <div className="text-base leading-7 text-gray-700 max-w-4xl">
              <p className="text-base font-semibold leading-7 text-indigo-600">
                Form component
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
                A 2 step dropdown
              </h1>
              <div className="">
                <p className="mt-6">
                  A dropdown component which has multiple categories of options
                  to be selected. For selecting the final value, first you have
                  to select the category from the first dropdown after which the
                  second dropdown is populated with the relevant options. If you
                  change the category in the first dropdown, the options in the
                  second dropdown are updated according to the selected category.
                </p>
              </div>
            </div>
          </div>
          <div className="lg:pr-4 col-span-8 sm:col-span-5">
            <h1 className="mt-2 text-xl font-bold tracking-tight text-gray-900 pb-2">
              Sample data
            </h1>
            <div className="relative rounded-xl bg-gray-900 px-6 pb-9 shadow-2xl sm:px-12 lg:px-8 lg:py-8 xl:px-10 xl:py-10 h-96 overflow-auto">
              <pre className="text-sm text-white">
                const options = {JSON.stringify(optionsLeft, null, 4)}
              </pre>
            </div>
            <h1 className="mt-16 text-xl font-bold tracking-tight text-gray-900 pb-2">
              Component
            </h1>
            <div>
              <Select2Step
                defaultValue={{ parent: "group", child: "0831f2dd-4138-4b00-9fdc-c366abee2bd0" }}
                label="Peer"
                optionsLeft={optionsLeft}
                onChange={(value) => {
                  setValue(value);
                }}
              />
            </div>
            <h1 className="mt-16 text-xl font-bold tracking-tight text-gray-900 pb-2">
              Output
            </h1>
            <div className="relative rounded-xl bg-gray-900 px-6 pb-9 shadow-2xl sm:px-12 lg:px-8 lg:py-8 xl:px-10 xl:py-10 overflow-auto">
              {value && <pre className="text-sm text-white">{JSON.stringify(value, null, 4)}</pre>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
