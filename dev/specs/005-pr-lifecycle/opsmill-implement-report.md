# PR lifecycle implementation report

Status: INCOMPLETE for activation. The observation-only draft is ready for review.
Reviewed implementation: `92c232e5e62ec2c8518e3a6a8b4d66c1f775a1e3`. Base: `19c7d8bb5e3fb64b60dda3308cde01f8f5639345`.
Report assembled: 2026-09-28T13:48:53.803793+00:00.

## Delivery and limits

The production read-only capture evaluated 117 PRs: 112 human and five bot-authored.
Final offline replay proposes 51 ordinary reminders, 12 fresh warnings, and zero closures.
No lifecycle writes, live stale execution, or activation occurred. Both workflow entry points
remain observation-only; the mutation job has an unconditional false guard.

T027 remains partial because hosted capacity is unverified. T030 needs a named authorized isolated
repository. The first notice batch exceeds the conservative mutation estimate, so preflight stops
before writes. Validate and optimize capacity before a separate reviewed activation. Local fixtures
cannot establish hosted cache, permission, timing, or production-recovery behavior.

## Execution and review

| Chunk | Commit | Outcome |
| --- | --- | --- |
| Setup | `35b6b9ea3` | Six tests passed |
| Foundations | `ce19e676d` | 28 tests passed |
| Reliability | `db2685437` | 41 tests, 34 upstream assertions passed |
| Cleanup | `8ebbd18aa` | 59 tests, 36 upstream assertions passed |
| Reminders | `7af54cd5a` | 69 tests, 36 upstream assertions passed |
| Dashboard | `3962ef5fb` | 84 tests, 36 upstream assertions passed |
| Final review fixes | `92c232e5e` | 86 tests passed |

The implementation used serial specialist chunks. The final review ran once in an independent
context, applying all six review aspects sequentially because the agent thread limit prevented
further specialist creation. The coordinating agent completed final validation and documentation
after the same limit prevented a separate delivery agent. This fallback did not skip review.

The two findings and regression evidence are in [the review report](review-report.md).
Exact commands, output timestamps, environments, and verbatim passing lines are in
[final evidence](evidence/final-validation.txt) and the six phase evidence files.
The final suite includes the earlier phase tests; its identifiers are listed below.

## Validation

| Check | Result |
| --- | --- |
| Frontend format/lint | PASS |
| Frontend unused exports | PASS; existing configuration hint |
| Frontend TS regressions | PASS; baseline unchanged |
| Frontend unit tests | Skipped; no frontend changes |
| @infrahub/graph unit tests | Skipped; no frontend changes |
| OpenAPI types | Skipped; no triggering changes |
| Frontend GraphQL types | Skipped; no triggering changes |
| Error catalogue bindings | Skipped; no triggering changes |
| Python format | PASS |
| Main Python lint | PASS |
| Ruff CI parity | PASS |
| Both lockfiles | PASS |
| YAML lint | PASS; generated nested venv excluded temporarily |
| Type check | PASS |
| Backend mypy | Skipped; no backend changes |
| Generated backend files | Skipped; no backend changes |
| GraphQL schema | Skipped; no schema changes |
| JSON schema | Skipped; no schema changes |
| Docs lint | PASS; 30 existing Vale warnings |
| Generated docs | PASS |
| Backend unit tests | Skipped; no backend changes |
| Testcontainers unit tests | Default command blocked by macOS psutil; external shim: 10 passed, 2 skipped |

All applicable source checks passed with the disclosed environment qualifications. The default
testcontainers invocation did not pass on this Mac; its failure occurred before collection.
No backend, schema, or frontend runtime changes require the skipped checks.

### Python behavioral tests

Command: `.venv/bin/python -m unittest utilities.tests.test_pr_lifecycle -v`.
Environment and exact UTC output time: [final evidence](evidence/final-validation.txt).

| Test | Qualified test case | Result |
| --- | --- | --- |
| `test_delayed_reopen_observation_preserves_newer_activity` | utilities.tests.test_pr_lifecycle.TestActivity.test_delayed_reopen_observation_preserves_newer_activity | PASS |
| `test_head_change_uses_observation_not_commit_date` | utilities.tests.test_pr_lifecycle.TestActivity.test_head_change_uses_observation_not_commit_date | PASS |
| `test_human_comment_cancels_warning` | utilities.tests.test_pr_lifecycle.TestActivity.test_human_comment_cancels_warning | PASS |
| `test_human_reserved_label_and_forged_marker_count_as_activity` | utilities.tests.test_pr_lifecycle.TestActivity.test_human_reserved_label_and_forged_marker_count_as_activity | PASS |
| `test_inactivity_survives_weekly_owned_comment_and_recovery` | utilities.tests.test_pr_lifecycle.TestActivity.test_inactivity_survives_weekly_owned_comment_and_recovery | PASS |
| `test_other_bot_and_edited_owned_comment_reset` | utilities.tests.test_pr_lifecycle.TestActivity.test_other_bot_and_edited_owned_comment_reset | PASS |
| `test_reopened_clears_old_warning_and_notice` | utilities.tests.test_pr_lifecycle.TestActivity.test_reopened_clears_old_warning_and_notice | PASS |
| `test_unknown_raw_or_fingerprint_change_resets` | utilities.tests.test_pr_lifecycle.TestActivity.test_unknown_raw_or_fingerprint_change_resets | PASS |
| `test_bot_and_keep_open_are_independent` | utilities.tests.test_pr_lifecycle.TestCleanupPolicy.test_bot_and_keep_open_are_independent | PASS |
| `test_legacy_stale_does_not_authorize_closure` | utilities.tests.test_pr_lifecycle.TestCleanupPolicy.test_legacy_stale_does_not_authorize_closure | PASS |
| `test_partial_approval_and_comment_do_not_remove_exemption` | utilities.tests.test_pr_lifecycle.TestCleanupPolicy.test_partial_approval_and_comment_do_not_remove_exemption | PASS |
| `test_receipt_deadline_must_match_server_and_immutable_interval` | utilities.tests.test_pr_lifecycle.TestCleanupPolicy.test_receipt_deadline_must_match_server_and_immutable_interval | PASS |
| `test_unfinalized_warning_cannot_close` | utilities.tests.test_pr_lifecycle.TestCleanupPolicy.test_unfinalized_warning_cannot_close | PASS |
| `test_apply_mode_is_rejected_before_transport` | utilities.tests.test_pr_lifecycle.TestCliSkeleton.test_apply_mode_is_rejected_before_transport | PASS |
| `test_fixture_files_are_valid_json` | utilities.tests.test_pr_lifecycle.TestCliSkeleton.test_fixture_files_are_valid_json | PASS |
| `test_mismatched_server_identity_is_rejected` | utilities.tests.test_pr_lifecycle.TestCliSkeleton.test_mismatched_server_identity_is_rejected | PASS |
| `test_naive_clock_is_rejected_before_transport` | utilities.tests.test_pr_lifecycle.TestCliSkeleton.test_naive_clock_is_rejected_before_transport | PASS |
| `test_observe_default_reports_incomplete_without_writes` | utilities.tests.test_pr_lifecycle.TestCliSkeleton.test_observe_default_reports_incomplete_without_writes | PASS |
| `test_repository_guard_precedes_transport` | utilities.tests.test_pr_lifecycle.TestCliSkeleton.test_repository_guard_precedes_transport | PASS |
| `test_complete_pagination_and_duplicate_failure` | utilities.tests.test_pr_lifecycle.TestCollection.test_complete_pagination_and_duplicate_failure | PASS |
| `test_empty_inventory_succeeds_without_mutations` | utilities.tests.test_pr_lifecycle.TestCollection.test_empty_inventory_succeeds_without_mutations | PASS |
| `test_missing_page_fails_instead_of_partial_success` | utilities.tests.test_pr_lifecycle.TestCollection.test_missing_page_fails_instead_of_partial_success | PASS |
| `test_bot_rows_require_no_supplemental_reads` | utilities.tests.test_pr_lifecycle.TestDashboard.test_bot_rows_require_no_supplemental_reads | PASS |
| `test_compact_history_detects_old_edits_and_owned_deletion` | utilities.tests.test_pr_lifecycle.TestDashboard.test_compact_history_detects_old_edits_and_owned_deletion | PASS |
| `test_explicit_adoption_and_duplicate_rejection` | utilities.tests.test_pr_lifecycle.TestDashboard.test_explicit_adoption_and_duplicate_rejection | PASS |
| `test_final_refresh_reuses_issue_and_preserves_success_on_failure` | utilities.tests.test_pr_lifecycle.TestDashboard.test_final_refresh_reuses_issue_and_preserves_success_on_failure | PASS |
| `test_finalization_keeps_label_definition_with_open_references` | utilities.tests.test_pr_lifecycle.TestDashboard.test_finalization_keeps_label_definition_with_open_references | PASS |
| `test_forged_current_digest_cannot_hide_post_warning_human_activity` | utilities.tests.test_pr_lifecycle.TestDashboard.test_forged_current_digest_cannot_hide_post_warning_human_activity | PASS |
| `test_full_inventory_with_active_cycles_fits_after_receipt_compaction` | utilities.tests.test_pr_lifecycle.TestDashboard.test_full_inventory_with_active_cycles_fits_after_receipt_compaction | PASS |
| `test_label_recovery_rejects_two_identical_added_events` | utilities.tests.test_pr_lifecycle.TestDashboard.test_label_recovery_rejects_two_identical_added_events | PASS |
| `test_missing_warning_proof_prevents_successful_refresh` | utilities.tests.test_pr_lifecycle.TestDashboard.test_missing_warning_proof_prevents_successful_refresh | PASS |
| `test_oversize_and_partial_preview_fail_closed` | utilities.tests.test_pr_lifecycle.TestDashboard.test_oversize_and_partial_preview_fail_closed | PASS |
| `test_preview_escapes_content_and_has_honest_clocks` | utilities.tests.test_pr_lifecycle.TestDashboard.test_preview_escapes_content_and_has_honest_clocks | PASS |
| `test_pruning_rebases_receipts_without_resetting_activity` | utilities.tests.test_pr_lifecycle.TestDashboard.test_pruning_rebases_receipts_without_resetting_activity | PASS |
| `test_render_places_each_category_once_with_plain_actors` | utilities.tests.test_pr_lifecycle.TestDashboard.test_render_places_each_category_once_with_plain_actors | PASS |
| `test_repeated_confirmed_deliveries_keep_bounded_state_and_old_edit_detection` | utilities.tests.test_pr_lifecycle.TestDashboard.test_repeated_confirmed_deliveries_keep_bounded_state_and_old_edit_detection | PASS |
| `test_visible_body_survives_intermediate_persistence` | utilities.tests.test_pr_lifecycle.TestDashboard.test_visible_body_survives_intermediate_persistence | PASS |
| `test_ambiguous_post_receipt_is_not_retried_or_assumed` | utilities.tests.test_pr_lifecycle.TestLedger.test_ambiguous_post_receipt_is_not_retried_or_assumed | PASS |
| `test_corrupt_unsupported_missing_state_fails` | utilities.tests.test_pr_lifecycle.TestLedger.test_corrupt_unsupported_missing_state_fails | PASS |
| `test_dashboard_provenance_and_duplicates` | utilities.tests.test_pr_lifecycle.TestLedger.test_dashboard_provenance_and_duplicates | PASS |
| `test_failed_finalization_preserves_pending_intent` | utilities.tests.test_pr_lifecycle.TestLedger.test_failed_finalization_preserves_pending_intent | PASS |
| `test_generation_and_unversioned_human_edit_conflict` | utilities.tests.test_pr_lifecycle.TestLedger.test_generation_and_unversioned_human_edit_conflict | PASS |
| `test_recovery_never_trusts_forged_author_or_edited_content` | utilities.tests.test_pr_lifecycle.TestLedger.test_recovery_never_trusts_forged_author_or_edited_content | PASS |
| `test_roundtrip_and_guard` | utilities.tests.test_pr_lifecycle.TestLedger.test_roundtrip_and_guard | PASS |
| `test_unresolved_intent_survives_retention` | utilities.tests.test_pr_lifecycle.TestLedger.test_unresolved_intent_survives_retention | PASS |
| `test_apply_transport_rejects_closing_merging_and_manual_label_changes` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_apply_transport_rejects_closing_merging_and_manual_label_changes | PASS |
| `test_delayed_missing_finalization_gets_fresh_full_warning` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_delayed_missing_finalization_gets_fresh_full_warning | PASS |
| `test_failed_receipt_persistence_recovers_before_activity_comparison` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_failed_receipt_persistence_recovers_before_activity_comparison | PASS |
| `test_gate_refresh_catches_approval_and_cleanup_keeps_keep_open` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_gate_refresh_catches_approval_and_cleanup_keeps_keep_open | PASS |
| `test_human_activity_cancels_once_and_preserves_keep_open` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_human_activity_cancels_once_and_preserves_keep_open | PASS |
| `test_incomplete_post_gate_refresh_disables_entire_closer` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_incomplete_post_gate_refresh_disables_entire_closer | PASS |
| `test_initial_delivery_survives_deadline_edit_failure_without_arming` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_initial_delivery_survives_deadline_edit_failure_without_arming | PASS |
| `test_low_mutation_quota_stops_before_any_write` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_low_mutation_quota_stops_before_any_write | PASS |
| `test_noop_reconciliation_collects_each_pr_only_once` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_noop_reconciliation_collects_each_pr_only_once | PASS |
| `test_overlapping_comment_and_timeline_receipts_are_one_delivery` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_overlapping_comment_and_timeline_receipts_are_one_delivery | PASS |
| `test_real_shaped_comment_receipts_recover_and_rerun_without_duplicate` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_real_shaped_comment_receipts_recover_and_rerun_without_duplicate | PASS |
| `test_rejected_label_mutation_cannot_report_success` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_rejected_label_mutation_cannot_report_success | PASS |
| `test_successful_gate_and_finalization_remove_only_owned_labels` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_successful_gate_and_finalization_remove_only_owned_labels | PASS |
| `test_warning_migration_preserves_legacy_label_but_starts_new_receipt` | utilities.tests.test_pr_lifecycle.TestMutationLifecycle.test_warning_migration_preserves_legacy_label_but_starts_new_receipt | PASS |
| `test_budget_stops_before_partial_collection` | utilities.tests.test_pr_lifecycle.TestReliability.test_budget_stops_before_partial_collection | PASS |
| `test_complete_observe_has_no_write_transport_operations` | utilities.tests.test_pr_lifecycle.TestReliability.test_complete_observe_has_no_write_transport_operations | PASS |
| `test_continuation_requires_cache_replacement_or_semantic_progress` | utilities.tests.test_pr_lifecycle.TestReliability.test_continuation_requires_cache_replacement_or_semantic_progress | PASS |
| `test_current_and_larger_bot_backlogs_use_inventory_only` | utilities.tests.test_pr_lifecycle.TestReliability.test_current_and_larger_bot_backlogs_use_inventory_only | PASS |
| `test_current_mixed_backlog_fits_github_token_quota` | utilities.tests.test_pr_lifecycle.TestReliability.test_current_mixed_backlog_fits_github_token_quota | PASS |
| `test_exact_cache_key_and_ref_metadata` | utilities.tests.test_pr_lifecycle.TestReliability.test_exact_cache_key_and_ref_metadata | PASS |
| `test_full_human_inventory_with_sufficient_quota` | utilities.tests.test_pr_lifecycle.TestReliability.test_full_human_inventory_with_sufficient_quota | PASS |
| `test_http_transport_only_sends_get_and_fixed_graphql_query` | utilities.tests.test_pr_lifecycle.TestReliability.test_http_transport_only_sends_get_and_fixed_graphql_query | PASS |
| `test_incomplete_observation_never_authorizes_closure` | utilities.tests.test_pr_lifecycle.TestReliability.test_incomplete_observation_never_authorizes_closure | PASS |
| `test_independent_candidate_verification_rejects_unknown_state` | utilities.tests.test_pr_lifecycle.TestReliability.test_independent_candidate_verification_rejects_unknown_state | PASS |
| `test_insufficient_quota_stops_before_human_detail_reads` | utilities.tests.test_pr_lifecycle.TestReliability.test_insufficient_quota_stops_before_human_detail_reads | PASS |
| `test_rate_buckets_and_actual_http_budget_are_independent` | utilities.tests.test_pr_lifecycle.TestReliability.test_rate_buckets_and_actual_http_budget_are_independent | PASS |
| `test_workflow_has_only_trusted_observation` | utilities.tests.test_pr_lifecycle.TestReliability.test_workflow_has_only_trusted_observation | PASS |
| `test_fresh_reviewers_reroute_ordinary_and_warning_names_all` | utilities.tests.test_pr_lifecycle.TestReminderLifecycle.test_fresh_reviewers_reroute_ordinary_and_warning_names_all | PASS |
| `test_human_reset_after_milestone_neutralizes_only_once` | utilities.tests.test_pr_lifecycle.TestReminderLifecycle.test_human_reset_after_milestone_neutralizes_only_once | PASS |
| `test_missed_middle_window_posts_only_final` | utilities.tests.test_pr_lifecycle.TestReminderLifecycle.test_missed_middle_window_posts_only_final | PASS |
| `test_observation_uses_saved_ordinary_receipt_without_writes` | utilities.tests.test_pr_lifecycle.TestReminderLifecycle.test_observation_uses_saved_ordinary_receipt_without_writes | PASS |
| `test_ordinary_receipt_recovers_and_rate_limits_by_delivery` | utilities.tests.test_pr_lifecycle.TestReminderLifecycle.test_ordinary_receipt_recovers_and_rate_limits_by_delivery | PASS |
| `test_weekly_warning_milestones_and_gate` | utilities.tests.test_pr_lifecycle.TestReminderLifecycle.test_weekly_warning_milestones_and_gate | PASS |
| `test_calendar_windows_and_strongest_suppression` | utilities.tests.test_pr_lifecycle.TestReminderPolicy.test_calendar_windows_and_strongest_suppression | PASS |
| `test_latest_status_per_context_replaces_historical_failure` | utilities.tests.test_pr_lifecycle.TestReminderPolicy.test_latest_status_per_context_replaces_historical_failure | PASS |
| `test_ordinary_seven_day_cadence_and_exempt_messages` | utilities.tests.test_pr_lifecycle.TestReminderPolicy.test_ordinary_seven_day_cadence_and_exempt_messages | PASS |
| `test_routing_and_readiness_precedence` | utilities.tests.test_pr_lifecycle.TestReminderPolicy.test_routing_and_readiness_precedence | PASS |
| `test_complete_same_head_snapshot_accepts_explicit_null_review_rule` | utilities.tests.test_pr_lifecycle.TestSnapshotBoundary.test_complete_same_head_snapshot_accepts_explicit_null_review_rule | PASS |
| `test_missing_aggregate_error_or_head_mismatch_fails` | utilities.tests.test_pr_lifecycle.TestSnapshotBoundary.test_missing_aggregate_error_or_head_mismatch_fails | PASS |
| `test_review_comments_and_timeline_are_collected` | utilities.tests.test_pr_lifecycle.TestSnapshotBoundary.test_review_comments_and_timeline_are_collected | PASS |
| `test_unrelated_head_repository_metadata_is_not_activity` | utilities.tests.test_pr_lifecycle.TestSnapshotBoundary.test_unrelated_head_repository_metadata_is_not_activity | PASS |

### Pinned upstream contract assertions

Command: `STALE_SOURCE_DIR=/tmp node utilities/tests/pr_lifecycle_upstream.mjs`, Node 24.19.
These assertions execute hash-checked pinned source against fixture APIs, without hosted writes.
Exact timestamp and output: [final evidence](evidence/final-validation.txt).

| Assertion | Result |
| --- | --- |
| 61-day inactive PR exceeds 60-day threshold | PASS |
| weekly bot comment prevents 60-day stale threshold | PASS |
| no updates after warning allows closure | PASS |
| bot reminder blocks closure even if only label events are returned | PASS |
| bot reminder with an additional event removes stale label | PASS |
| disabling stale removal still lets bot reminder postpone closure | PASS |
| human comment cancels warning | PASS |
| commit/update with non-label event cancels warning | PASS |
| freshly marked timestamp prevents same-run closure | PASS |
| low-budget first scan persists progress | PASS |
| second scan advances to previously unprocessed items | PASS |
| third scan reaches tail | PASS |
| complete scan resets saved state | PASS |
| lost cache with sufficient budget covers all items | PASS |
| failed cache replacement processes same slice first time | PASS |
| failed cache replacement processes same slice again | PASS |
| fresh gate allows stock zero-day closure after bot reminder | PASS |
| human comment after gate prevents stock closure | PASS |
| arbitrary recent update does not stop zero-day closer | PASS |
| future updated timestamp defers closure | PASS |
| full processor closes a currently gated PR | PASS |
| full processor excludes legacy stale-only PR | PASS |
| full processor excludes prior-attempt gate | PASS |
| full processor keep-open label prevents closure | PASS |
| full processor human comment since gate vetoes closure | PASS |
| full processor cached ID skips newly eligible gate | PASS |
| mutable pagination covers 116 candidates within four passes | PASS |
| mutable pagination 116 needs continuation | PASS |
| mutable pagination covers 574 candidates within four passes | PASS |
| mutable pagination 574 needs continuation | PASS |
| interrupted state containing newly due IDs requires fresh sweep | PASS |
| expired cache restarts safely from full inventory | PASS |
| upstream reports attempted close despite swallowed API failure | PASS |
| independent candidate read detects swallowed close failure | PASS |
| 574 cached candidates complete within four passes | PASS |
| 574 cached candidates require four passes | PASS |
