import { Avatar } from "@/components/display/avatar";
import { getProfileDetails } from "@/graphql/queries/accounts/getProfileDetails";
import { useAuth } from "@/hooks/useAuth";
import useQuery from "@/hooks/useQuery";
import { userNavigation } from "@/screens/layout/navigation-list";
import { IModelSchema, schemaState } from "@/state/atoms/schema.atom";
import { classNames } from "@/utils/common";
import { gql } from "@apollo/client";
import { Menu, Transition } from "@headlessui/react";
import { Fragment, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAtomValue } from "jotai/index";
import { ACCOUNT_OBJECT } from "@/config/constants";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";

const customId = "profile-alert";

export const AccountMenu = () => {
  const { isAuthenticated } = useAuth();

  const location = useLocation();
  const schemas = useAtomValue(schemaState);
  const schema = schemas.find((s) => s.kind === ACCOUNT_OBJECT);

  if (!isAuthenticated) {
    return (
      <Link
        to="/signin"
        state={{ from: location }}
        className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-200 rounded-md whitespace-nowrap">
        Sign in
      </Link>
    );
  }

  if (!schema) {
    return <Avatar isLoading />;
  }

  return <AccountAvatarWithMenu schema={schema} />;
};

const AccountAvatarWithMenu = ({ schema }: { schema: IModelSchema }) => {
  const { signOut } = useAuth();

  const query = gql(getProfileDetails({ ...schema }));
  const { error, loading, data } = useQuery(query);

  useEffect(() => {
    if (error) {
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading profile data" />, {
        toastId: customId,
      });

      // Sign out because there is nothing from the API for that user id
      signOut();
    }
  }, [error]);

  if (loading || !schema) {
    return <Avatar isLoading />;
  }

  const profile = data?.AccountProfile;

  return (
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
  );
};
