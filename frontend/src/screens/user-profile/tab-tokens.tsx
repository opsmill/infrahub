import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { classNames } from "../../utils/common";

const tokens = [
  {
    id: 205,
    key: "41375584c009c2dab65373c8dc5c3f777bf38ac3",
    write: true,
    created: "2023-05-11",
    expires: null,
    lastUsed: "2023-05-11 05:40",
    allowedIps: null,
  },
  {
    id: 206,
    key: "91649269c009c2dab65373c8dc5c3f7782537291",
    write: false,
    created: "2023-10-11",
    expires: null,
    lastUsed: "2023-05-11 05:40",
    allowedIps: null,
  },
  {
    id: 207,
    key: "91675584c009c2dab65373c8dc5c3f777bf38017",
    write: true,
    created: "2023-08-11",
    expires: null,
    lastUsed: "2023-05-11 05:40",
    allowedIps: null,
  },
];

export default function TabTokens() {
  return (
    <div className="px-4 sm:px-6 lg:px-8 flex-1 bg-white p-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-base font-semibold leading-6 text-gray-900">Tokens</h1>
          <p className="mt-2 text-sm text-gray-700">
            A list of all the tokens in your account including their keys, permissions, and expiry.
          </p>
        </div>
        <div className="mt-4 sm:ml-16 sm:mt-0 sm:flex-none">
          <button
            type="button"
            className="block rounded-md bg-indigo-600 px-3 py-2 text-center text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
            Add Token
          </button>
        </div>
      </div>
      <div className="mt-8 flow-root">
        <div className="-mx-4 -my-2 sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full py-2 align-middle">
            <table className="min-w-full border-separate border-spacing-0">
              <thead>
                <tr>
                  <th
                    scope="col"
                    className="sticky top-0 z-10 border-b border-gray-300 bg-white bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8">
                    Key
                  </th>
                  <th
                    scope="col"
                    className="sticky top-0 z-10 hidden border-b border-gray-300 bg-white bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter lg:table-cell">
                    Write
                  </th>
                  <th
                    scope="col"
                    className="sticky top-0 z-10 border-b border-gray-300 bg-white bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter">
                    Created
                  </th>
                  <th
                    scope="col"
                    className="sticky top-0 z-10 border-b border-gray-300 bg-white bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter">
                    Expires
                  </th>
                  <th
                    scope="col"
                    className="sticky top-0 z-10 border-b border-gray-300 bg-white bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter">
                    Last used
                  </th>
                  <th
                    scope="col"
                    className="sticky top-0 z-10 border-b border-gray-300 bg-white bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter">
                    Allowed IPs
                  </th>
                  <th
                    scope="col"
                    className="sticky top-0 z-10 border-b border-gray-300 bg-white bg-opacity-75 py-3.5 pl-3 pr-4 backdrop-blur backdrop-filter sm:pr-6 lg:pr-8">
                    <span className="sr-only">Edit</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((token, tokenIdx) => (
                  <tr key={token.id} className="hover:bg-gray-100 cursor-pointer">
                    <td
                      className={classNames(
                        tokenIdx !== tokens.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                      )}>
                      {token.key}
                    </td>
                    <td
                      className={classNames(
                        tokenIdx !== tokens.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-nowrap hidden px-3 py-4 text-sm text-gray-500 lg:table-cell"
                      )}>
                      {token.write ? (
                        <CheckIcon className="w-5 h-5 text-green-600" />
                      ) : (
                        <XMarkIcon className="w-5 h-5 text-red-600" />
                      )}
                    </td>
                    <td
                      className={classNames(
                        tokenIdx !== tokens.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-nowrap px-3 py-4 text-sm text-gray-500"
                      )}>
                      {token.created}
                    </td>
                    <td
                      className={classNames(
                        tokenIdx !== tokens.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-nowrap px-3 py-4 text-sm text-gray-500"
                      )}>
                      {token.expires ?? "-"}
                    </td>
                    <td
                      className={classNames(
                        tokenIdx !== tokens.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-nowrap px-3 py-4 text-sm text-gray-500"
                      )}>
                      {token.lastUsed}
                    </td>
                    <td
                      className={classNames(
                        tokenIdx !== tokens.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-nowrap px-3 py-4 text-sm text-gray-500"
                      )}>
                      {token.allowedIps ?? "-"}
                    </td>
                    <td
                      className={classNames(
                        tokenIdx !== tokens.length - 1 ? "border-b border-gray-200" : "",
                        "relative whitespace-nowrap py-4 pr-4 pl-3 text-right text-sm font-medium sm:pr-8 lg:pr-8"
                      )}>
                      <a href="#" className="text-indigo-600 hover:text-indigo-900">
                        Edit<span className="sr-only">, {token.id}</span>
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
