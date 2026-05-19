import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { LOGIN_ERRORS } from "@/entities/authentication/constants";
import { useAuth } from "@/entities/authentication/ui/useAuth";

import { render } from "../../../../tests/components/render";
import { CredentialsForm } from "./credentials-form";

vi.mock("@/entities/authentication/ui/useAuth");

const setToken = vi.fn();

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    accessToken: null,
    isAuthenticated: false,
    setToken,
    user: null,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("CredentialsForm", () => {
  test("renders username and password fields", async () => {
    const component = await render(<CredentialsForm onSubmit={vi.fn()} />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByLabelText("Password")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Log in" })).toBeVisible();
  });

  test("calls onSubmit with the entered username and password", async () => {
    const onSubmit = vi.fn().mockResolvedValue({
      access_token: "tok",
      refresh_token: "ref",
    });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    expect(onSubmit).toHaveBeenCalledWith({ username: "alice", password: "secret" });
  });

  test("calls setToken with the result on success", async () => {
    const token = { access_token: "tok", refresh_token: "ref" };
    const onSubmit = vi.fn().mockResolvedValue(token);

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await vi.waitFor(() => expect(setToken).toHaveBeenCalledWith(token));
  });

  test("shows 'Invalid username or password' toast on 401 error", async () => {
    const onSubmit = vi.fn().mockRejectedValue({ status: 401 });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("wrong");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect
      .element(component.getByText(LOGIN_ERRORS.invalid_credentials.message))
      .toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("shows 'Invalid username or password' toast on 404 error", async () => {
    const onSubmit = vi.fn().mockRejectedValue({ status: 404 });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("unknown");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect
      .element(component.getByText(LOGIN_ERRORS.invalid_credentials.message))
      .toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("shows account-collision toast on 409 error", async () => {
    const onSubmit = vi.fn().mockRejectedValue({ status: 409 });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect.element(component.getByText(LOGIN_ERRORS.account_collision.message)).toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("shows enterprise-required toast on 403 error", async () => {
    const onSubmit = vi.fn().mockRejectedValue({ status: 403 });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect
      .element(component.getByText(LOGIN_ERRORS.enterprise_required.message))
      .toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("prefers the server-provided message when the error body has one", async () => {
    const onSubmit = vi.fn().mockRejectedValue({
      status: 409,
      body: { error_code: "LDAP_ACCOUNT_COLLISION", message: "Username 'alice' is already taken" },
    });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect
      .element(component.getByText("Username 'alice' is already taken"))
      .toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("shows server-error toast on 5xx error", async () => {
    const onSubmit = vi.fn().mockRejectedValue({ status: 503 });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect.element(component.getByText(LOGIN_ERRORS.server.message)).toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("shows network-error toast when fetch fails with a TypeError", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect.element(component.getByText(LOGIN_ERRORS.network.message)).toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("shows generic 'Could not log in' toast for unrecognized errors", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("something weird"));

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect.element(component.getByText(LOGIN_ERRORS.unknown.message)).toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("validates required fields before submitting", async () => {
    const onSubmit = vi.fn();

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);
    await component.getByRole("button", { name: "Log in" }).click();

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
