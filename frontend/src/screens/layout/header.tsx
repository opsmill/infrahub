import { gql } from "@apollo/client";
import { Menu, Transition } from "@headlessui/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import { Bars3BottomLeftIcon } from "@heroicons/react/24/outline";
import { formatISO, isEqual, isValid } from "date-fns";
import { useAtom } from "jotai";
import React, { Fragment, useContext, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { Avatar } from "../../components/avatar";
import BranchSelector from "../../components/branch-selector";
import { DatePicker } from "../../components/date-picker";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { AuthContext } from "../../decorators/withAuth";
import { getProfileDetails } from "../../graphql/queries/profile/getProfileDetails";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { classNames, debounce, parseJwt } from "../../utils/common";
import LoadingScreen from "../loading-screen/loading-screen";
import { userNavigation } from "./navigation-list";
import { datetimeAtom } from "../../state/atoms/time.atom";

interface Props {
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

const customId = "profile-alert";

export default function Header(props: Props) {
  const { setSidebarOpen } = props;

  const [qspDate, setQspDate] = useQueryParam(QSP.DATETIME, StringParam);
  const [date, setDate] = useAtom(datetimeAtom);
  const auth = useContext(AuthContext);
  const [schemaList] = useAtom(schemaState);
  const navigate = useNavigate();

  const schema = schemaList.find((s) => s.kind === ACCOUNT_OBJECT);

  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const accountId = tokenData?.sub;

  const queryString = schema
    ? getProfileDetails({ ...schema })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { error, loading, data } = useQuery(query, { skip: !schema || !accountId });

  useEffect(() => {
    // Remove the date from the state
    if (!qspDate || (qspDate && !isValid(new Date(qspDate)))) {
      setDate(null);
    }

    if (qspDate) {
      const newQspDate = new Date(qspDate);

      // Store the new QSP date only if it's not defined OR if it's different
      if (!date || (date && !isEqual(newQspDate, date))) {
        setDate(newQspDate);
      }
    }
  }, [date, qspDate]);

  const handleDateChange = (newDate: any) => {
    if (newDate) {
      setQspDate(formatISO(newDate));
    } else {
      // Undefined is needed to remove a parameter from the QSP
      setQspDate(undefined);
    }
  };

  const debouncedHandleDateChange = debounce(handleDateChange);

  const handleClickNow = () => {
    // Undefined is needed to remove a parameter from the QSP
    setQspDate(undefined);
  };

  if (loading || !schema) {
    return (
      <div className="z-10 flex h-16 flex-shrink-0 bg-custom-white shadow">
        <LoadingScreen size={32} hideText />
      </div>
    );
  }

  const profile = data?.AccountProfile;

  if (!loading && auth?.accessToken && (error || !profile)) {
    toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading profile data" />, {
      toastId: customId,
    });

    // Sign out because there is nothing from the API for that user id
    if (auth?.signOut) {
      auth?.signOut();
    }

    navigate("/");

    return null;
  }

  return (
    <div className="z-10 flex h-16 flex-shrink-0 bg-custom-white shadow">
      <button
        type="button"
        className="border-r border-gray-200 px-4 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-custom-blue-500 md:hidden"
        onClick={() => setSidebarOpen(true)}>
        <span className="sr-only">Open sidebar</span>
        <Bars3BottomLeftIcon className="h-6 w-6" aria-hidden="true" />
      </button>

      <div className="flex flex-1 justify-between px-4">
        <div className="flex flex-1 opacity-30">
          <form className="flex w-full md:ml-0" action="#" method="GET">
            <label htmlFor="search-field" className="sr-only">
              Search
            </label>
            <div className="relative w-full text-gray-400 focus-within:text-gray-600">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center">
                <MagnifyingGlassIcon className="w-4 h-4" aria-hidden="true" />
              </div>
              <input
                onChange={() => {}}
                id="search-field"
                className="block h-full w-full border-transparent py-2 pl-8 pr-3 text-gray-900 placeholder-gray-500 focus:border-transparent focus:placeholder-gray-400 focus:outline-none focus:ring-0 sm:text-sm cursor-not-allowed"
                placeholder="Search"
                type="search"
                name="search"
              />
            </div>
          </form>
        </div>
        <div className="ml-4 flex items-center md:ml-6">
          <div className="mr-4">
            <DatePicker
              date={date}
              onChange={debouncedHandleDateChange}
              onClickNow={handleClickNow}
            />
          </div>

          <BranchSelector />

          {/* Profile dropdown */}
          {!auth?.accessToken && (
            <Link
              to={window.location.pathname}
              className={"block ml-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-200 rounded-md"}
              onClick={() => auth?.displaySignIn && auth?.displaySignIn()}>
              Sign in
            </Link>
          )}

          {auth?.accessToken && (
            <Menu as="div" className="relative ml-3">
              <div>
                <Menu.Button
                  className="flex max-w-xs items-center rounded-full bg-custom-white text-sm focus:outline-none focus:ring-2 focus:ring-custom-blue-500 focus:ring-offset-2"
                  data-cy="current-user-avatar-button">
                  <Avatar name={profile?.name?.value} data-cy="user-avatar" />
                </Menu.Button>
              </div>
              <Transition
                as={Fragment}
                enter="transition ease-out duration-100"
                enterFrom="transform opacity-0 scale-95"
                enterTo="transform opacity-100 scale-100"
                leave="transition ease-in duration-75"
                leaveFrom="transform opacity-100 scale-100"
                leaveTo="transform opacity-0 scale-95">
                <Menu.Items className="absolute right-0 z-10 mt-2 w-48 origin-top-right rounded-md bg-custom-white py-1 shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none">
                  {userNavigation.map((item) => (
                    <Menu.Item key={item.name}>
                      {({ active }) => (
                        <Link
                          to={item.href}
                          className={classNames(
                            active ? "bg-gray-100" : "",
                            "block px-4 py-2 text-sm text-gray-700 hover:bg-gray-200"
                          )}>
                          {item.name}
                        </Link>
                      )}
                    </Menu.Item>
                  ))}

                  <Menu.Item>
                    <Link
                      to={"/"}
                      className={"block px-4 py-2 text-sm text-gray-700 hover:bg-gray-200"}
                      onClick={() => auth?.signOut && auth?.signOut()}>
                      Sign out
                    </Link>
                  </Menu.Item>
                </Menu.Items>
              </Transition>
            </Menu>
          )}
        </div>
      </div>
    </div>
  );
}
