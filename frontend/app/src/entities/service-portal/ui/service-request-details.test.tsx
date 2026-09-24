import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type {
  ServiceRequest,
  ServiceRequestStatus,
} from "@/entities/service-portal/domain/model/service-request";
import { getServiceRequest } from "@/entities/service-portal/domain/use-cases/get-service-request";

import { render } from "../../../../tests/components/render";
import { ServiceRequestDetails } from "./service-request-details";

vi.mock("@/entities/service-portal/domain/use-cases/get-service-request");

const buildRequest = (overrides?: Partial<ServiceRequest>): ServiceRequest => ({
  id: "request-1",
  status: "submitted",
  message: null,
  branch: null,
  entryName: "Layer 2 VPN",
  proposedChangeId: null,
  service: null,
  ...overrides,
});

const defaultBranchCalls = () =>
  vi.mocked(getServiceRequest).mock.calls.filter(([params]) => !params.branchName).length;

describe("ServiceRequestDetails", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test.each([
    ["submitted", "Submitted"],
    ["generating", "Building"],
    ["failed", "Failed"],
    ["in_review", "In review"],
    ["merged", "Delivered"],
    ["rejected", "Rejected"],
  ] satisfies Array<
    [ServiceRequestStatus, string]
  >)("renders the %s status as %s with the request message", async (status, label) => {
    vi.mocked(getServiceRequest).mockResolvedValue(
      buildRequest({ status, message: `Message for ${status}` })
    );

    const component = await render(<ServiceRequestDetails requestId="request-1" />);

    await expect.element(component.getByRole("heading", { name: "Layer 2 VPN" })).toBeVisible();
    await expect.element(component.getByText(label, { exact: true })).toBeVisible();
    await expect.element(component.getByText(`Message for ${status}`)).toBeVisible();
  });

  test("shows no proposed change or service link until they are set", async () => {
    vi.mocked(getServiceRequest).mockResolvedValue(buildRequest({ status: "generating" }));

    const component = await render(<ServiceRequestDetails requestId="request-1" />);

    await expect.element(component.getByText("Building", { exact: true })).toBeVisible();
    expect(component.getByRole("link").all()).toHaveLength(0);
  });

  test("links to the proposed change and to the service on the request branch", async () => {
    vi.mocked(getServiceRequest).mockImplementation(async ({ branchName }) =>
      buildRequest({
        status: "in_review",
        branch: "service-request-1",
        proposedChangeId: "pc-1",
        // The service relationship is only visible on the request branch
        service: branchName === "service-request-1" ? { id: "vpn-1", kind: "ServiceL2Vpn" } : null,
      })
    );

    const component = await render(<ServiceRequestDetails requestId="request-1" />);

    await expect
      .element(component.getByRole("link", { name: "View the proposed change" }))
      .toHaveAttribute("href", "/proposed-changes/pc-1");
    await expect
      .element(component.getByRole("link", { name: "Open your service" }))
      .toHaveAttribute("href", "/objects/ServiceL2Vpn/vpn-1?branch=service-request-1");
    expect(getServiceRequest).toHaveBeenCalledWith({ requestId: "request-1" });
    expect(getServiceRequest).toHaveBeenCalledWith({
      requestId: "request-1",
      branchName: "service-request-1",
    });
  });

  test.each([
    "submitted",
    "generating",
  ] satisfies Array<ServiceRequestStatus>)("keeps polling while the request is %s", async (status) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getServiceRequest).mockResolvedValue(buildRequest({ status }));

    const component = await render(<ServiceRequestDetails requestId="request-1" />);
    await expect.element(component.getByRole("heading", { name: "Layer 2 VPN" })).toBeVisible();
    const callsBefore = defaultBranchCalls();

    await vi.advanceTimersByTimeAsync(5000);

    await vi.waitFor(() => expect(defaultBranchCalls()).toBeGreaterThan(callsBefore));
  });

  test.each([
    "in_review",
    "failed",
    "merged",
    "rejected",
  ] satisfies Array<ServiceRequestStatus>)("stops polling once the request is %s", async (status) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getServiceRequest).mockResolvedValue(buildRequest({ status }));

    const component = await render(<ServiceRequestDetails requestId="request-1" />);
    await expect.element(component.getByRole("heading", { name: "Layer 2 VPN" })).toBeVisible();
    const callsBefore = defaultBranchCalls();

    await vi.advanceTimersByTimeAsync(15_000);

    expect(defaultBranchCalls()).toBe(callsBefore);
  });
});
