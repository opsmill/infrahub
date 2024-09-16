import { Icon } from "@iconify-icon/react";
import { LinkButton, LinkButtonProps } from "@/components/buttons/button-primitive";
import React from "react";
import { getLoginUrl } from "@/screens/authentification/utils";

export function GoogleLoginButton({
  redirect,
  ...props
}: Omit<LinkButtonProps, "children" | "variant" | "to"> & {
  redirect?: string | null;
}) {
  const loginUrl = getLoginUrl("http://localhost:8080/auth/google");

  return (
    <LinkButton variant="outline" to={loginUrl} target="_parent" {...props}>
      <Icon icon="mdi:google" className="mr-2" /> Login with Google
    </LinkButton>
  );
}
