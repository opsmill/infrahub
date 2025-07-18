import logging

from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.proposed_change.constants import ProposedChangeState

log = logging.getLogger(__name__)


async def revoke_approvals_on_updated_pcs(db: InfrahubDatabase) -> None:
    """
    Revoke approvals if some changes have been performed since on corresponding branch since approval times.
    """

    proposed_changes = await NodeManager.query(
        db=db,
        schema=InfrahubKind.PROPOSEDCHANGE,
        filters={"state": ProposedChangeState.OPEN.value},
    )

    if not proposed_changes:
        return

    parent_adder = DiffParentNodeAdder()
    deserializer = EnrichedDiffDeserializer(parent_adder=parent_adder)
    diff_repo = DiffRepository(db=db, deserializer=deserializer)

    for proposed_change in proposed_changes:
        approvals = list((await proposed_change.approvals.get_peers(db=db)).values())
        approvals_to_keep = approvals

        if len(approvals) == 0:
            continue

        # Sort approval by approval timestamps, and for each interval (ie, pair of approval timestamps),
        # if there had been changes on corresponding branch within the interval, revoke the earliest approval of the interval
        # and any approval before it.
        approvals_and_timestamps = [(approval, Timestamp(approval.approved_at.value)) for approval in approvals]
        approvals_and_timestamps = sorted(
            approvals_and_timestamps, key=lambda approval_and_timestamp: approval_and_timestamp[1], reverse=True
        )

        # Add the current timestamp to check if we should revoke the most recent approval
        timestamps = [Timestamp()] + [timestamp for _, timestamp in approvals_and_timestamps]
        source_branch = proposed_change.source_branch.value
        for i in range(len(timestamps) - 1):
            changes_by_branch = await diff_repo.get_num_changes_in_time_range_by_branch(
                branch_names=[source_branch],
                from_time=timestamps[i + 1],
                to_time=timestamps[i],
            )

            if changes_by_branch[source_branch] > 0:
                # Changes detected, we keep the most recent approvals until above `to_time`.
                # approvals_sorted has 1 element less than timestamps,
                # so approvals_sorted[i] corresponds to above `from_time`.
                approvals_to_keep = [approval for approval, _ in approvals_and_timestamps[:i]]
                break

        if len(approvals_to_keep) != len(approvals):
            await proposed_change.approvals.update(db=db, data=[approval.id for approval in approvals_to_keep])
            await proposed_change.save(db=db)
