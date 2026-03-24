import { gql, useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { Link, useLocation } from "react-router";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { Avatar } from "@/shared/components/display/avatar";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button, LinkButton } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuDivider,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Spinner } from "@/shared/components/ui/spinner";
import {
  INFRAHUB_DISCORD_URL,
  INFRAHUB_DOC_LOCAL,
  INFRAHUB_GITHUB_URL,
  INFRAHUB_SWAGGER_DOC_URL,
} from "@/shared/config/config";
import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";

import { useLogoutMutation } from "@/entities/authentication/domain/logout.mutation";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { AppInfo } from "@/entities/config/ui/app-info";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";
import { getProfileDetails } from "@/entities/user-profile/api/getProfileDetails";

export const AccountMenu = () => {
  const { isAuthenticated } = useAuth();
  const generics = useAtomValue(genericSchemasAtom);
  const schema = generics.find((s) => s.kind === ACCOUNT_GENERIC_OBJECT);

  if (!isAuthenticated) {
    return <UnauthenticatedAccountMenu />;
  }

  if (!schema) {
    return <AccountMenuSkeleton />;
  }

  return <AuthenticatedAccountMenu schema={schema} />;
};

const CommonMenuItems = () => (
  <>
    <DropdownMenuItem asChild>
      <Link to={INFRAHUB_DOC_LOCAL} target="_blank" rel="noreferrer">
        <Icon icon="mdi:file-document" className="text-base" />
        Infrahub documentation
      </Link>
    </DropdownMenuItem>

    <DropdownMenuItem asChild>
      <Link to={constructPath("/graphql")} className="text-base">
        <Icon icon="mdi:graphql" className="text-base" />
        GraphQL Sandbox
      </Link>
    </DropdownMenuItem>

    <DropdownMenuItem asChild>
      <Link to={INFRAHUB_SWAGGER_DOC_URL} target="_blank" rel="noreferrer">
        <Icon icon="mdi:code-json" className="text-base" />
        Swagger documentation
      </Link>
    </DropdownMenuItem>

    <DropdownMenuDivider />

    <DropdownMenuItem asChild>
      <Link to={INFRAHUB_GITHUB_URL} target="_blank" rel="noreferrer">
        <Icon icon="mdi:github" className="text-base" />
        GitHub Repository
      </Link>
    </DropdownMenuItem>

    <DropdownMenuItem asChild>
      <Link to={INFRAHUB_DISCORD_URL} target="_blank" rel="noreferrer">
        <Icon icon="mdi:discord" className="text-base" />
        Join our Discord server
      </Link>
    </DropdownMenuItem>
  </>
);

const UnauthenticatedAccountMenu = () => {
  const location = useLocation();

  return (
    <DropdownMenu>
      <LinkButton
        variant="ghost"
        className="h-auto w-full shrink-0 gap-2 overflow-hidden rounded-lg p-2 hover:bg-indigo-50"
        to="/login"
        state={{ from: location }}
      >
        <div className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white bg-indigo-50">
          <Icon icon="mdi:user" className="relative top-1 text-5xl text-neutral-600" />
        </div>

        <div className="overflow-hidden group-data-[collapsed=true]/sidebar:hidden">
          <div className="truncate font-semibold text-sm">Log in</div>
          <div className="truncate text-neutral-500 text-xs">anonymous</div>
        </div>

        <DropdownMenuTrigger
          onClick={(event) => {
            event.preventDefault();
          }}
          asChild
        >
          <Button
            variant="ghost"
            size="square"
            data-testid="unauthenticated-menu-trigger"
            className="ml-auto shrink-0 hover:bg-indigo-100 group-data-[collapsed=true]/sidebar:hidden"
          >
            <Icon icon="mdi:dots-vertical" className="text-lg" />
          </Button>
        </DropdownMenuTrigger>
      </LinkButton>

      <DropdownMenuContent align="end" side="right">
        <CommonMenuItems />
        <DropdownMenuDivider />
        <DropdownMenuItem asChild>
          <Link to="/login" state={{ from: location }}>
            <Icon icon="mdi:login" className="text-base" />
            Log in
          </Link>
        </DropdownMenuItem>
        <DropdownMenuDivider />
        <AppInfo />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const AuthenticatedAccountMenu = ({ schema }: { schema: ModelSchema }) => {
  const query = gql(getProfileDetails({ ...schema }));
  const { setToken } = useAuth();
  const { loading, data } = useQuery(query);
  const { mutateAsync: logout, isPending } = useLogoutMutation();

  const handleSignOut = async () => {
    await logout(undefined, {
      onSuccess: () => {
        setToken(null);
        queryClient.refetchQueries();
        graphqlClient.refetchQueries({
          include: "active",
          onQueryUpdated: ({ queryName }) => queryName !== "GET_PROFILE_DETAILS",
        });
      },
      onError: (error) => {
        console.error("Error when logging out: ", error);
        toast(<Alert type={ALERT_TYPES.ERROR} message="Failed to log out" />, {
          toastId: "alert-error-sign-out",
        });
      },
    });
  };

  if (loading) {
    return <AccountMenuSkeleton />;
  }

  const profile = data?.AccountProfile;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="h-auto w-full shrink-0 justify-start gap-2 overflow-hidden rounded-lg p-2 text-left hover:bg-indigo-50"
          data-testid="authenticated-menu-trigger"
        >
          <Avatar name={profile?.name?.value} className="size-9 shrink-0" />

          <div className="overflow-hidden group-data-[collapsed=true]/sidebar:hidden">
            <div className="truncate font-semibold text-sm">{profile?.label?.value}</div>
          </div>

          <Icon
            icon="mdi:dots-vertical"
            className="m-2 ml-auto text-lg transition-all group-data-[collapsed=true]/sidebar:hidden"
          />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" side="right">
        <DropdownMenuItem asChild>
          <Link to={constructPath("/profile")}>
            <Icon icon="mdi:account-circle" className="text-base" />
            Account settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuDivider />
        <CommonMenuItems />
        <DropdownMenuDivider />
        <DropdownMenuItem onClick={handleSignOut} disabled={isPending}>
          {isPending ? <Spinner /> : <Icon icon="mdi:logout" className="text-base" />}
          Logout
        </DropdownMenuItem>
        <DropdownMenuDivider />
        <AppInfo />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const AccountMenuSkeleton = () => {
  return (
    <div className="flex shrink-0 items-center gap-2 border border-transparent p-2">
      <Skeleton className="size-9 rounded-full" />

      <div className="grow space-y-2 group-data-[collapsed=true]/sidebar:hidden">
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-2 w-3/5" />
      </div>
    </div>
  );
};
