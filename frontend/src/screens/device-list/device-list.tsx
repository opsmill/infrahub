import { classNames } from "../../App";
import { gql } from "@apollo/client";
import { sampleDeviceList } from "./sample-devices.data";
import { Device } from "../../generated/graphql";
import DeviceFilters from "./device-filters";
import LoadingScreen from "../loading-screen/loading-screen";
import ErrorScreen from "../error-screen/error-screen";
import { useEffect, useState } from "react";
import { graphQLClient } from "../..";

const GET_DEVICES_QUERY = gql`
  query DeviceList {
    device {
      id
      name {
        value
      }
      type {
        value
      }
      asn {
        asn {
          value
        }
      }
      status {
        name {
          value
        }
      }
      role {
        name {
          value
        }
      }
      site {
        name {
          value
        }
      }
      tags {
        name {
          value
        }
      }
    }
  }
`;

interface DeviceListData {
  device: Device[];
}

export default function DeviceList() {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [objectRows, setObjectRows] = useState<Device[]>([]);

  useEffect(() => {
    const request = graphQLClient.request(GET_DEVICES_QUERY);
    request.then((data: DeviceListData) => {
      const rows = data.device;
      setObjectRows(rows);
      setIsLoading(false);
    }).catch(() => {
      setHasError(true);
    });
  }, []);

  if(hasError) {
    return <ErrorScreen />
  }

  if (isLoading) {
    return <LoadingScreen />;
  }

  return (
    <div className="flex-1 overflow-auto pt-0 px-4 sm:px-0 md:px-0">
      <div className="sm:flex sm:items-center pb-4 px-4 sm:px-6 lg:px-8">
        <div className="sm:flex-auto pt-6">
          <h1 className="text-xl font-semibold text-gray-900">Devices</h1>
          <p className="mt-2 text-sm text-gray-700">
            A list of all the devices in your infrastructure.
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          <DeviceFilters />
        </div>
      </div>
      <div className="mt-0 flex flex-col px-4 sm:px-6 lg:px-8">
        <div className="-my-2 -mx-4 sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full pt-2 align-middle">
            <div className="shadow-sm ring-1 ring-black ring-opacity-5">
              <table
                className="min-w-full border-separate"
                style={{ borderSpacing: 0 }}
              >
                <thead className="bg-gray-50">
                  <tr>
                    <th
                      scope="col"
                      className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8"
                    >
                      Name
                    </th>
                    <th
                      scope="col"
                      className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter lg:table-cell"
                    >
                      Status
                    </th>
                    <th
                      scope="col"
                      className="sticky top-0 hidden border-b border-gray-300 bg-gray-50 bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:table-cell lg:table-cell"
                    >
                      Type
                    </th>
                    <th
                      scope="col"
                      className="sticky top-0 hidden border-b border-gray-300 bg-gray-50 bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter lg:table-cell"
                    >
                      ASN
                    </th>
                    <th
                      scope="col"
                      className="sticky top-0 hidden border-b border-gray-300 bg-gray-50 bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter lg:table-cell"
                    >
                      Role
                    </th>
                    <th
                      scope="col"
                      className="sticky top-0 hidden border-b border-gray-300 bg-gray-50 bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter lg:table-cell"
                    >
                      Site
                    </th>
                    <th
                      scope="col"
                      className="sticky top-0 hidden border-b border-gray-300 bg-gray-50 bg-opacity-75 px-3 py-3.5 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter lg:table-cell"
                    >
                      Tags
                    </th>
                    <th
                      scope="col"
                      className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pr-4 pl-3 backdrop-blur backdrop-filter sm:pr-6 lg:pr-8"
                    >
                      <span className="sr-only">Edit</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white">
                  {objectRows.map((device, deviceIdx) => (
                    <tr key={deviceIdx} className="hover:bg-gray-50">
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8 uppercase"
                        )}
                      >
                        {device.name.value}
                      </td>
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "whitespace-nowrap px-3 py-4 text-sm text-gray-500 sm:table-cell"
                        )}
                      >
                        <span className="inline-flex rounded-full bg-green-100 px-2 text-xs font-semibold leading-5 text-green-800 capitalize">
                          {device.status?.name.value}
                        </span>
                      </td>
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "whitespace-nowrap px-3 py-4 text-sm text-gray-500 hidden sm:table-cell"
                        )}
                      >
                        {device.type.value}
                      </td>
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "whitespace-nowrap px-3 py-4 text-sm text-gray-500 hidden lg:table-cell"
                        )}
                      >
                        {device.asn?.asn.value}
                      </td>
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "whitespace-nowrap px-3 py-4 text-sm text-gray-500 hidden sm:table-cell capitalize"
                        )}
                      >
                        <span className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-800">
                          {device.role?.name.value}
                        </span>
                      </td>
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "whitespace-nowrap px-3 py-4 text-sm text-gray-500 hidden sm:table-cell uppercase"
                        )}
                      >
                        {device.site?.name.value}
                      </td>
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "whitespace-nowrap px-3 py-4 text-sm text-gray-500 hidden sm:table-cell"
                        )}
                      >
                        {/* Add dynamic background color classes, else they wont be added to the TailwindCSS build */}
                        {/* <div className="bg-red-500 bg-green-500 bg-blue-500"></div> */}
                        <div className="space-x-1">
                          {device.tags?.map((t) => (
                            <span
                              key={t?.name.value}
                              className={`w-4 h-4 bg-${t?.name.value}-500 rounded-full inline-block`}
                            />
                          ))}
                        </div>
                      </td>
                      <td
                        className={classNames(
                          deviceIdx !== sampleDeviceList.length - 1
                            ? "border-b border-gray-200"
                            : "",
                          "relative whitespace-nowrap py-4 pr-4 pl-3 text-right text-sm font-medium sm:pr-6 lg:pr-8"
                        )}
                      >
                        <a
                          href="#edit"
                          className="text-indigo-600 hover:text-indigo-900"
                        >
                          Edit
                          <span className="sr-only">{device.name.value}</span>
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
    </div>
  );
}
