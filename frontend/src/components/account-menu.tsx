import { gql } from "@apollo/client";
import { Menu, Transition } from "@headlessui/react";
import { useAtom } from "jotai/index";
import { Fragment, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT } from "../config/constants";
import { getProfileDetails } from "../graphql/queries/accounts/getProfileDetails";
import { useLazyQuery } from "../hooks/useQuery";
import { userNavigation } from "../screens/layout/navigation-list";
import { schemaState } from "../state/atoms/schema.atom";
import { classNames, parseJwt } from "../utils/common";
import { Avatar } from "./display/avatar";
import { ALERT_TYPES, Alert } from "./utils/alert";
import { useAuth } from "../hooks/useAuth";

const customId = "profile-alert";

export const AccountMenu = () => {
  const { isAuthenticated, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
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

  const [fetchProfile, { error, loading, data }] = useLazyQuery(query);

  useEffect(() => {
    if (schema && accountId) {
      fetchProfile();
    }
  }, [schema, accountId]);

  if (loading || !schema) {
    return <Avatar isLoading />;
  }

  const profile = data?.AccountProfile;

  if (error) {
    toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading profile data" />, {
      toastId: customId,
    });

    // Sign out because there is nothing from the API for that user id
    signOut();
    navigate("/");
  }

  return isAuthenticated ? (
    <Menu as="div">
      <Menu.Button
        className="flex max-w-xs items-center rounded-full bg-custom-white text-sm focus:outline-none focus:ring-2 focus:ring-custom-blue-500 focus:ring-offset-2"
        data-cy="current-user-avatar-button"
        data-testid="current-user-avatar-button">
        <Avatar name={profile?.name?.value} data-cy="user-avatar" />
      </Menu.Button>

      <Transition
        as={Fragment}
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95">
        <Menu.Items className="absolute right-0 mt-2 w-48 origin-top-right rounded-md bg-custom-white py-1 shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none">
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
            <button
              className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-200"
              onClick={() => signOut()}>
              Sign out
            </button>
          </Menu.Item>
        </Menu.Items>
      </Transition>
    </Menu>
  ) : (
    <Link
      to="/signin"
      state={{ from: location }}
      className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-200 rounded-md whitespace-nowrap">
      Sign in
    </Link>
  );
};
