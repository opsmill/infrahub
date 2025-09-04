import { gql, useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useCallback, useEffect } from "react";
import { Link, useLocation } from "react-router";
import { toast } from "react-toastify";

import {
  INFRAHUB_DISCORD_URL,
  INFRAHUB_DOC_LOCAL,
  INFRAHUB_GITHUB_URL,
  INFRAHUB_SWAGGER_DOC_URL,
} from "@/config/config";
import { ACCOUNT_GENERIC_OBJECT } from "@/config/constants";

import { constructPath } from "@/shared/api/rest/fetch";
import { Button, LinkButton } from "@/shared/components/buttons/button-primitive";
import { Avatar } from "@/shared/components/display/avatar";
import { AppVersion } from "@/shared/components/layout/app-version";
import { Skeleton } from "@/shared/components/skeleton";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuDivider,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { ModelSchema } from "@/entities/schema/types";
import { getProfileDetails } from "@/entities/user-profile/api/getProfileDetails";

export const AccountMenu = () => {
  const { isAuthenticated, signOut } = useAuth();
  const generics = useAtomValue(genericSchemasAtom);
  const schema = generics.find((s) => s.kind === ACCOUNT_GENERIC_OBJECT);

  if (!isAuthenticated) {
    return <UnauthenticatedAccountMenu />;
  }

  if (!schema) {
    return <AccountMenuSkeleton />;
  }

  return <AuthenticatedAccountMenu schema={schema} signOut={signOut} />;
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
        className="p-2 h-auto w-full rounded-lg gap-2 hover:bg-indigo-50 overflow-hidden shrink-0"
        to="/login"
        state={{ from: location }}
      >
        <div className="bg-indigo-50 rounded-full size-9 flex items-center justify-center overflow-hidden border border-white shrink-0">
          <Icon icon="mdi:user" className="text-5xl relative top-1 text-neutral-600" />
        </div>

        <div className="group-data-[collapsed=true]/sidebar:hidden overflow-hidden">
          <div className="font-semibold text-sm truncate">Log in</div>
          <div className="text-xs text-neutral-500 truncate">anonymous</div>
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
            className="shrink-0 ml-auto hover:bg-indigo-100 group-data-[collapsed=true]/sidebar:hidden"
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
        <AppVersion />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const AuthenticatedAccountMenu = ({
  schema,
  signOut,
}: {
  schema: ModelSchema;
  signOut: () => void;
}) => {
  const query = gql(getProfileDetails({ ...schema }));
  const { error, loading, data } = useQuery(query);

  const handleSignOut = useCallback(async () => {
    await signOut();

    toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading profile data" />, {
      toastId: "profile-alert",
    });
  }, []);

  useEffect(() => {
    if (error) {
      handleSignOut();
    }
  }, [error, signOut]);

  if (loading) {
    return <AccountMenuSkeleton />;
  }

  const profile = data?.AccountProfile;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="h-auto w-full justify-start gap-2 hover:bg-indigo-50 rounded-lg p-2 overflow-hidden text-left shrink-0"
          data-testid="authenticated-menu-trigger"
        >
          <Avatar name={profile?.name?.value} className="size-9 shrink-0" />

          <div className="group-data-[collapsed=true]/sidebar:hidden overflow-hidden">
            <div className="font-semibold text-sm truncate">{profile?.label?.value}</div>
          </div>

          <Icon
            icon="mdi:dots-vertical"
            className="text-lg m-2 ml-auto group-data-[collapsed=true]/sidebar:hidden transition-all"
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
        <DropdownMenuItem onClick={signOut}>
          <Icon icon="mdi:logout" className="text-base" />
          Logout
        </DropdownMenuItem>
        <DropdownMenuDivider />
        <AppVersion />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const AccountMenuSkeleton = () => {
  return (
    <div className="flex items-center gap-2 p-2 shrink-0 border border-transparent">
      <Skeleton className="rounded-full size-9" />

      <div className="grow space-y-2 group-data-[collapsed=true]/sidebar:hidden">
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-2 w-3/5" />
      </div>
    </div>
  );
};
