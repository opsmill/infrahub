import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import renderer from "react-test-renderer";
import { afterAll, describe, expect, it } from "vitest";
import { BUTTON_TYPES, Button } from "../../../src/components/buttons/button";

afterAll(cleanup);

describe("Buttons component", () => {
  it("should create a button component and verify the snapshot", () => {
    const component = renderer.create(
      <Button buttonType={BUTTON_TYPES.VALIDATE}>{"That's working"}</Button>
    );

    const tree = component.toJSON();

    expect(tree).toMatchSnapshot();
  });

  it("should create a button component and verify the rendered content", () => {
    render(<Button buttonType={BUTTON_TYPES.VALIDATE}>{"That's working"}</Button>);

    expect(screen.getByText(/That's working/i)).toBeTruthy();

    fireEvent.click(screen.getByText(/That's working/i));

    expect(screen.getByText(/That's working/i)).toBeTruthy();
  });
});
