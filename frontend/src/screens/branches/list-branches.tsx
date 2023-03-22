import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import * as R from "ramda";
import { branchesState } from "../../state/atoms/branches.atom";
import { classNames } from "../../utils/common";
import NoDataFound from "../no-data-found/no-data-found";

export const ListBranches = () => {
  const [storedBranches] = useAtom(branchesState);

  const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));

  const sortedBranches = sortByName(storedBranches.filter(b => b.name !== "main"));

  const branches = [
    ...storedBranches.filter(b => b.name === "main"),
    ...sortedBranches
  ]

  const columns = [
    {
      name: "name",
      label: "Name"
    },
    {
      name: "created_at",
      label: "Created"
    },
  ]

  const deleteBranch = (id: string) => {
    console.log("id: ", id);
  }

  const getObjectItemDisplayValue = (branch: any, attribute: any) => {
    if (attribute.name === "created_at") {
      return formatDistanceToNow(
        new Date(branch.created_at),
        { addSuffix: true }
      )
    }

    return branch[attribute.name];
  }

  return (
    <div className="flex-1 pt-0 px-4 sm:px-0 md:px-0 overflow-x-auto flex flex-col">
      <div className="sm:flex sm:items-center py-4 px-4 sm:px-6 lg:px-8 w-full">
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          {/* <DeviceFilters /> */}
        </div>
      </div>

      {/* {
        schema
        && <DeviceFilterBar schema={schema} />
      } */}

      <div className="mt-0 flex flex-col px-4 sm:px-6 lg:px-8 w-full overflow-x-auto flex-1">
        <div className="-my-2 -mx-4 sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full pt-2 align-middle">
            <div className="shadow-sm ring-1 ring-black ring-opacity-5">
              <table
                className="min-w-full border-separate"
                style={{ borderSpacing: 0 }}
              >
                <thead className="bg-gray-50">
                  <tr>
                    {
                      columns
                      ?.map(
                        (attribute) => (
                          <th
                            key={attribute.name}
                            scope="col"
                            className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8"
                          >
                            {attribute.label}
                          </th>
                        )
                      )
                    }

                    <th
                      scope="col"
                      className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-4 text-right text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pr-6 lg:pr-8"
                    >
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white">
                  {
                    branches
                    ?.map(
                      (branch, index) => (
                        <tr
                          key={index}
                          className={classNames(branch.name === "main" ? "bg-blue-50" : "")}
                        >
                          {
                            columns?.map(
                              (attribute) => (
                                <td
                                  key={branch.id + "-" + attribute.name}
                                  className={classNames(
                                    index !== branches.length - 1
                                      ? "border-b border-gray-200"
                                      : "",
                                    "whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                                  )}
                                >
                                  {getObjectItemDisplayValue(branch, attribute)}
                                </td>
                              )
                            )}

                          <td
                            className={classNames(
                              index !== branches.length - 1
                                ? "border-b border-gray-200"
                                : "",
                              "whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                            )}
                          >
                            {
                              branch.name !== "main"
                              && (
                                <>
                                  <button
                                    onClick={() => deleteBranch(branch.id)}
                                    type="button"
                                    className="float-right mr-3 inline-flex items-center gap-x-1.5 rounded-md py-1.5 px-2.5 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 bg-red-600  text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-red-400"
                                  >
                                    Delete
                                    <XMarkIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                                  </button>

                                  <button
                                    onClick={() => deleteBranch(branch.id)}
                                    type="button"
                                    className="float-right mr-3 inline-flex items-center gap-x-1.5 rounded-md py-1.5 px-2.5 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 bg-red  text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-200"
                                  >
                                    Pull request
                                    <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                                  </button>
                                </>
                              )
                            }
                          </td>
                        </tr>
                      )
                    )
                  }
                </tbody>
              </table>

              {
                !branches?.length
                && <NoDataFound />
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}