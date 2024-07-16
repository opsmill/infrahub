import { describe, expect, it } from "vitest";
import {
  isFieldDisabled,
  IsFieldDisabledParams,
} from "../../src/components/form/utils/isFieldDisabled";

describe("isFieldDisabled", () => {
  it("returns true when field is read only", () => {
    // GIVEN
    const params: IsFieldDisabledParams = {
      isProtected: false,
      isReadOnly: true,
      owner: null,
      auth: null,
    };

    // WHEN
    const disabled = isFieldDisabled(params);

    // THEN
    expect(disabled).to.equal(true);
  });

  it("returns false when field is not protected", () => {
    // GIVEN
    const params: IsFieldDisabledParams = {
      isProtected: false,
      isReadOnly: false,
      owner: null,
      auth: null,
    };

    // WHEN
    const disabled = isFieldDisabled(params);

    // THEN
    expect(disabled).to.equal(false);
  });

  it("returns false if field is protected but has no owner", () => {
    // GIVEN
    const params: IsFieldDisabledParams = {
      isProtected: true,
      isReadOnly: false,
      owner: null,
      auth: null,
    };

    // WHEN
    const disabled = isFieldDisabled(params);

    // THEN
    expect(disabled).to.equal(false);
  });

  it("returns true if field is protected but the current user is not the owner", () => {
    // GIVEN
    const params: IsFieldDisabledParams = {
      isProtected: true,
      isReadOnly: false,
      owner: { id: "user-1" },
      auth: { user: { id: "not-user-1" } },
    };

    // WHEN
    const disabled = isFieldDisabled(params);

    // THEN
    expect(disabled).to.equal(true);
  });

  it("returns false if field is protected and the current user is the owner", () => {
    // GIVEN
    const params: IsFieldDisabledParams = {
      isProtected: true,
      isReadOnly: false,
      owner: { id: "user-1" },
      auth: { user: { id: "user-1" } },
    };

    // WHEN
    const disabled = isFieldDisabled(params);

    // THEN
    expect(disabled).to.equal(false);
  });

  it("returns false if the auth is an admin", () => {
    // GIVEN
    const params: IsFieldDisabledParams = {
      isProtected: true,
      isReadOnly: false,
      owner: { id: "not-admin" },
      auth: { permissions: { isAdmin: true } },
    };

    // WHEN
    const disabled = isFieldDisabled(params);

    // THEN
    expect(disabled).to.equal(false);
  });
});
