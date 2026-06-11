"""Port of frontend/app/tests/e2e/objects/file-upload/file-upload.spec.ts.

File upload on InfraCircuitContract (a serial flow): the unauthenticated
create-disabled state, the Admin upload / validation / update / multiple
file-type flows, and the Read-Only create-disabled / edit-disabled enforcement.

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
the CONTRACT-UPLOAD contract the first Admin test creates, which the Read-Only
"cannot edit" test later opens. Every test depends on the SAME class-scoped
`branch` fixture and the chain relies on pytest's default definition-order
collection (see the README's serial-specs gotcha). The branch is cut
from main; the Read-Only page authenticates as the demo `jbauer` account, hence
the data_rbac dependency (the InfraCircuitContract kind comes from the schema,
which data_rbac pulls).

Local helpers (upload_file / fill_circuit_contract_fields) live in the sibling
file_upload_helpers module (this directory is on sys.path at runtime).
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from file_upload_helpers import create_minimal_pdf_buffer, fill_circuit_contract_fields, upload_file
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Generator

    from data.handles import RbacHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page, Response

TEST_FILE_NAME = "contract.pdf"
TEST_FILE_CONTENT = "Mock PDF contract content for E2E testing"
CONTRACT_UPLOAD = "CONTRACT-UPLOAD"
CONTRACT_UPDATE = "CONTRACT-UPDATE"


@pytest.fixture
def install_500_guard() -> Generator[Callable[[Page], None], None, None]:
    """Mirror the source `beforeEach`: fail if any response comes back with a 500.

    Collect-then-assert: Playwright's sync API swallows exceptions raised inside
    a response handler, so an inline assert there can never fail the test (the
    TS source had the same flaw). The recorded URLs are asserted at teardown.
    """
    server_errors: list[str] = []

    def _install(page: Page) -> None:
        def _record_500(response: Response) -> None:
            if response.status == 500:
                server_errors.append(response.url)

        page.on("response", _record_500)

    yield _install
    assert not server_errors, f"Unexpected 500 responses: {server_errors}"


class TestFileUploadCircuitContract:
    @pytest.fixture(scope="class")
    async def branch(
        self,
        infrahub_client: InfrahubClient,
        data_rbac: RbacHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("file-upload")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    # --- when not logged in --------------------------------------------------
    async def test_should_not_be_able_to_create_file_object(
        self, page: Page, branch: str, install_500_guard: Callable[[Page], None]
    ) -> None:
        install_500_guard(page)
        await page.goto(f"/objects/InfraCircuitContract?branch={branch}")

        await expect(page.get_by_test_id("create-object-button")).to_be_disabled()

    # --- when logged in as Admin --------------------------------------------
    async def test_should_successfully_upload_a_file(
        self, admin_page: Page, branch: str, install_500_guard: Callable[[Page], None]
    ) -> None:
        install_500_guard(admin_page)
        await admin_page.goto(f"/objects/InfraCircuitContract?branch={branch}")

        # click create button
        await admin_page.get_by_test_id("create-object-button").click()

        # display file upload dropzone
        await expect(admin_page.get_by_text("Drag and drop a file here, or click to select")).to_be_visible()
        await expect(admin_page.get_by_text("Max file size: 10MB")).to_be_visible()

        # upload a file
        await upload_file(
            admin_page,
            name=TEST_FILE_NAME,
            mime_type="application/pdf",
            buffer=create_minimal_pdf_buffer(TEST_FILE_CONTENT),
        )

        # Verify file info card is displayed
        await expect(admin_page.get_by_text(TEST_FILE_NAME)).to_be_visible()
        await expect(admin_page.get_by_text(re.compile(r"\d+\s*(B|KB|MB)"))).to_be_visible()  # File size

        # fill required fields
        await fill_circuit_contract_fields(admin_page, contract_number=CONTRACT_UPLOAD)

        # submit the form
        await admin_page.get_by_role("button", name="Save").click()

        # Wait for success message (just "created" to be more flexible)
        await expect(admin_page.get_by_text(re.compile(r"created", re.IGNORECASE))).to_be_visible()

        # verify contract appears in list
        await admin_page.goto(f"/objects/InfraCircuitContract?branch={branch}")
        await expect(admin_page.get_by_role("link", name=CONTRACT_UPLOAD)).to_be_visible()

    async def test_should_validate_required_file_field(
        self, admin_page: Page, branch: str, install_500_guard: Callable[[Page], None]
    ) -> None:
        install_500_guard(admin_page)
        await admin_page.goto(f"/objects/InfraCircuitContract?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        # try to submit without file
        await admin_page.get_by_role("button", name="Save").click()

        # Should show validation error (multiple "Required" messages for all required fields)
        await expect(admin_page.get_by_text(re.compile(r"required", re.IGNORECASE)).first).to_be_visible()

        # upload file to clear error
        await upload_file(
            admin_page,
            name="valid-contract.pdf",
            mime_type="application/pdf",
            buffer=create_minimal_pdf_buffer("Valid contract content"),
        )

        # Error should be cleared or file should be visible
        await expect(admin_page.get_by_text("valid-contract.pdf")).to_be_visible()

    async def test_should_update_existing_file(
        self, admin_page: Page, branch: str, install_500_guard: Callable[[Page], None]
    ) -> None:
        install_500_guard(admin_page)
        initial_file_name = "initial-contract.pdf"
        updated_file_name = "updated-contract.pdf"

        # create initial file
        await admin_page.goto(f"/objects/InfraCircuitContract?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        await upload_file(
            admin_page,
            name=initial_file_name,
            mime_type="application/pdf",
            buffer=create_minimal_pdf_buffer("Initial contract content"),
        )

        await fill_circuit_contract_fields(admin_page, contract_number=CONTRACT_UPDATE)

        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text(re.compile(r"created", re.IGNORECASE))).to_be_visible()

        # navigate to edit the file object
        # Navigate back to list and click on the created contract by its contract number
        await admin_page.goto(f"/objects/InfraCircuitContract?branch={branch}")

        # Click on the contract by its contract_number (which is the display label)
        await admin_page.get_by_role("link", name=CONTRACT_UPDATE).click()

        # Click edit button
        await admin_page.get_by_test_id("edit-button").click()

        # Verify existing file is shown (use .first to avoid strict mode violation)
        await expect(admin_page.get_by_text(initial_file_name).first).to_be_visible()

        # upload new file
        await upload_file(
            admin_page,
            name=updated_file_name,
            mime_type="application/pdf",
            buffer=create_minimal_pdf_buffer("Updated contract content"),
        )

        await expect(admin_page.get_by_text(updated_file_name)).to_be_visible()

        # save the update
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text(re.compile(r"updated", re.IGNORECASE))).to_be_visible()
        await expect(admin_page.get_by_text(updated_file_name)).to_be_visible()

    async def test_should_handle_different_file_types(
        self, admin_page: Page, branch: str, install_500_guard: Callable[[Page], None]
    ) -> None:
        install_500_guard(admin_page)
        test_files = [
            {"name": "contract.json", "mime_type": "application/json", "content": '{"contract": "data"}'},
            {"name": "contract.yaml", "mime_type": "application/x-yaml", "content": "contract: data\nstatus: active\n"},
            {"name": "contract.txt", "mime_type": "text/plain", "content": "Plain text contract\n"},
        ]

        for test_file in test_files:
            # upload <test_file["name"]>
            await admin_page.goto(f"/objects/InfraCircuitContract?branch={branch}")
            await admin_page.get_by_test_id("create-object-button").click()

            await upload_file(
                admin_page,
                name=test_file["name"],
                mime_type=test_file["mime_type"],
                content=test_file["content"],
            )

            await expect(admin_page.get_by_text(test_file["name"])).to_be_visible()

            await fill_circuit_contract_fields(admin_page, contract_number=f"CONTRACT-{test_file['name']}")

            await admin_page.get_by_role("button", name="Save").click()
            await expect(admin_page.get_by_text(re.compile(r"created", re.IGNORECASE))).to_be_visible()

    # --- when logged in as Read-Only ----------------------------------------
    async def test_should_not_be_able_to_upload_files(
        self, read_only_page: Page, branch: str, install_500_guard: Callable[[Page], None]
    ) -> None:
        install_500_guard(read_only_page)
        await read_only_page.goto(f"/objects/InfraCircuitContract?branch={branch}")

        await expect(read_only_page.get_by_test_id("create-object-button")).to_be_disabled()

    async def test_should_not_be_able_to_edit_existing_file(
        self, read_only_page: Page, branch: str, install_500_guard: Callable[[Page], None]
    ) -> None:
        install_500_guard(read_only_page)
        # navigate to an existing file object
        await read_only_page.goto(f"/objects/InfraCircuitContract?branch={branch}")

        await read_only_page.get_by_role("link", name=CONTRACT_UPLOAD).click()

        # verify edit button is disabled
        await expect(read_only_page.get_by_test_id("edit-button")).to_be_disabled()
