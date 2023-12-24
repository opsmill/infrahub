import { Link, useNavigate } from "react-router-dom";
import React, { Fragment, useContext, useEffect } from "react";
import { Menu, Transition } from "@headlessui/react";
import { Avatar } from "./avatar";
import { userNavigation } from "../screens/layout/navigation-list";
import { classNames, parseJwt } from "../utils/common";
import { AuthContext } from "../decorators/withAuth";
import { getProfileDetails } from "../graphql/queries/profile/getProfileDetails";
import { gql, useLazyQuery } from "@apollo/client";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT } from "../config/constants";
import { useAtom } from "jotai/index";
import { schemaState } from "../state/atoms/schema.atom";
import LoadingScreen from "../screens/loading-screen/loading-screen";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "./alert";

const customId = "profile-alert";

export const AccountManager = () => {
  const auth = useContext(AuthContext);
  const navigate = useNavigate();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.find((s) => s.kind === ACCOUNT_OBJECT);

  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const tokenData = parseJwt(localToken);
  const accountId = tokenData?.sub;

  const queryString = schema
    ? getProfileDetails({ ...schema })
    : // Empty query to make the gql parsing work
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const [getProfile, { error, loading, data }] = useLazyQuery(query);

  useEffect(() => {
    if (schema && accountId) {
      getProfile();
    }
  }, [schema, accountId]);

  if (loading || !schema) {
    return (
      <div className="z-10 flex h-16 flex-shrink-0 bg-custom-white shadow">
        <LoadingScreen size={32} hideText />
      </div>
    );
  }

  const profile = data?.AccountProfile;

  if (error) {
    toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading profile data" />, {
      toastId: customId,
    });

    // Sign out because there is nothing from the API for that user id
    if (auth?.signOut) {
      auth?.signOut();
    }

    navigate("/");
  }

  return auth?.accessToken ? (
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
  ) : (
    <Link
      to={window.location.pathname}
      className={"block ml-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-200 rounded-md"}
      onClick={() => auth?.displaySignIn && auth?.displaySignIn()}>
      Sign in
    </Link>
  );
};
