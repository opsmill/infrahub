"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {
	MARKER,
	reviewState,
	classify,
	render,
	run,
} = require("./pr-lifecycle.cjs");

const repository = { owner: "opsmill", repo: "infrahub" };
function pull(overrides = {}) {
	return {
		number: 1,
		state: "open",
		title: "A pull request",
		draft: false,
		head: { sha: "abc" },
		user: { login: "author", type: "User" },
		updated_at: "2026-07-01T12:00:00Z",
		labels: [],
		requested_reviewers: [],
		requested_teams: [],
		...overrides,
	};
}
function review(state, id = 1, login = "reviewer") {
	return { id, state, user: { login } };
}
function fixture(pulls = [pull()], reviews = [], mergeOverrides = {}) {
	const writes = [],
		reads = [];
	const issue = { number: 9, state: "open", body: `${MARKER}\nseed` };
	const github = {
		rest: {
			pulls: {
				list: "pulls",
				listReviews: "reviews",
				requestedReviewers: async ({ pull_number }) => ({
					headers: {},
					data: {
						users: pulls.find((pr) => pr.number === pull_number)
							.requested_reviewers,
						teams: pulls.find((pr) => pr.number === pull_number)
							.requested_teams,
					},
				}),
			},
			issues: {
				get: async () => ({ data: issue }),
				addLabels: async (args) => {
					writes.push(["add", args]);
					pulls
						.find((pr) => pr.number === args.issue_number)
						.labels.push(...args.labels.map((name) => ({ name })));
				},
				removeLabel: async (args) => {
					writes.push(["remove", args]);
					const pr = pulls.find((item) => item.number === args.issue_number);
					pr.labels = pr.labels.filter((label) => label.name !== args.name);
				},
				update: async (args) => {
					writes.push(["update", args]);
					issue.body = args.body;
				},
			},
		},
		paginate: async (route, args) => {
			reads.push([route, args]);
			assert.equal(args.per_page, 100);
			if (route === "pulls") return pulls;
			return typeof reviews === "function"
				? reviews(args.pull_number)
				: reviews;
		},
		graphql: async () => ({
			repository: {
				pullRequest: {
					headRefOid: "abc",
					mergeable: "MERGEABLE",
					mergeStateStatus: "CLEAN",
					reviewDecision: "APPROVED",
					...mergeOverrides,
				},
			},
		}),
	};
	return { github, writes, reads, issue };
}
async function execute(f, options = {}) {
	return run({
		github: f.github,
		...repository,
		now: new Date("2026-09-29T12:00:00Z"),
		...options,
	});
}
function observed(overrides = {}) {
	return {
		...pull(),
		author: "Author Name",
		reviewers: [],
		review: { approved: false, changes: false },
		merge: {},
		...overrides,
	};
}

test("preview defaults to zero writes and uses complete paginated PR and review endpoints", async () => {
	const f = fixture(
		Array.from({ length: 101 }, (_, i) => pull({ number: i + 1 })),
		[review("APPROVED")],
	);
	const result = await execute(f);
	assert.equal(result.count, 101);
	assert.equal(f.reads.filter(([route]) => route === "reviews").length, 101);
	assert.match(result.body, /author/);
	assert.deepEqual(f.writes, []);
});

test("comment-only reviews preserve decisive approval and dismissal clears it", () => {
	assert.deepEqual(
		reviewState([review("COMMENTED", 3), review("APPROVED", 2)]),
		{ approved: true, changes: false },
	);
	assert.deepEqual(
		reviewState([
			review("APPROVED"),
			review("DISMISSED", 2),
			review("COMMENTED", 3),
		]),
		{ approved: false, changes: false },
	);
	assert.deepEqual(
		reviewState([review("CHANGES_REQUESTED"), review("COMMENTED", 2)]),
		{ approved: false, changes: true },
	);
	assert.deepEqual(
		reviewState([review("APPROVED"), review("CHANGES_REQUESTED", 2)]),
		{ approved: false, changes: true },
	);
	assert.deepEqual(
		reviewState([review("APPROVED"), review("CHANGES_REQUESTED", 2, "other")]),
		{ approved: true, changes: true },
	);
});

test("routing covers drafts, requested changes, blockers, readiness and review ownership", () => {
	assert.equal(classify(observed({ draft: true })).state, "Draft");
	assert.equal(
		classify(observed({ review: { approved: true, changes: true } })).state,
		"Changes requested",
	);
	assert.equal(
		classify(
			observed({ merge: { headRefOid: "abc", mergeStateStatus: "DIRTY" } }),
		).state,
		"Blocked",
	);
	assert.equal(
		classify(observed({ reviewers: ["Alice", "Network team"] })).actor,
		"Alice, Network team",
	);
	assert.equal(classify(observed()).state, "Needs reviewer");
	assert.equal(classify(observed({ user: { type: "Bot" } })).state, "Bot");
});

test("ready requires same-head clean aggregate and explicit approved or null decision", () => {
	const base = observed({
		review: { approved: true, changes: false },
		merge: {
			headRefOid: "abc",
			mergeable: "MERGEABLE",
			mergeStateStatus: "CLEAN",
			reviewDecision: "APPROVED",
		},
	});
	assert.equal(classify(base).state, "Ready to merge");
	assert.equal(
		classify({ ...base, merge: { ...base.merge, reviewDecision: null } }).state,
		"Ready to merge",
	);
	for (const changed of [
		{ headRefOid: "old" },
		{ mergeable: "UNKNOWN" },
		{ mergeStateStatus: "UNKNOWN" },
		{ reviewDecision: "REVIEW_REQUIRED" },
		{ reviewDecision: undefined },
	]) {
		const status = classify({ ...base, merge: { ...base.merge, ...changed } });
		assert.notEqual(status.state, "Ready to merge");
		assert.match(status.cleanup, /current approval/);
	}
	assert.notEqual(
		classify({ ...base, review: { approved: false, changes: false } }).state,
		"Ready to merge",
	);
});

test("render escapes full names, titles, teams, mentions and Markdown links without truncating rows", () => {
	const dangerous = "@team [click](https://evil.invalid) <img> |\n# title";
	const body = render(
		[observed({ title: dangerous, author: dangerous, reviewers: [dangerous] })],
		repository,
	);
	assert.ok(!body.includes("@team"));
	assert.ok(!body.includes("[click]"));
	assert.ok(!body.includes("<img>"));
	assert.ok(body.includes("&#64;team"));
	assert.ok(body.includes("https://github.com/opsmill/infrahub/pull/1"));
	assert.match(body, /Last updated \(UTC\)/);
	assert.match(body, /rough estimates/);
	assert.throws(
		() => render([observed({ title: "x".repeat(65000) })], repository),
		/body limit/,
	);
});

test("publish synchronizes only owned exemption labels and configured issue; repeat is idempotent", async () => {
	const f = fixture(
		[
			pull({ labels: [{ name: "lifecycle-bot" }, { name: "keep-open" }] }),
			pull({
				number: 2,
				user: { login: "robot", type: "Bot" },
				labels: [{ name: "lifecycle-approved" }],
			}),
		],
		(number) => (number === 1 ? [review("APPROVED")] : []),
	);
	await execute(f, { apply: true, dashboardIssue: 9 });
	assert.deepEqual(
		f.writes.map(([kind, args]) => [
			kind,
			args.issue_number,
			args.labels || args.name,
		]),
		[
			["add", 1, ["lifecycle-approved"]],
			["remove", 1, "lifecycle-bot"],
			["remove", 2, "lifecycle-approved"],
			["add", 2, ["lifecycle-bot"]],
			["update", 9, undefined],
		],
	);
	f.writes.length = 0;
	await execute(f, { apply: true, dashboardIssue: 9 });
	assert.deepEqual(f.writes, []);
});

test("publish rejects missing issue configuration, PR targets, closed or unmarked issues before writes", async () => {
	for (const change of [
		{},
		{ dashboardIssue: 0 },
		{ dashboardIssue: 9, body: "unmarked" },
		{ dashboardIssue: 9, pull_request: {} },
		{ dashboardIssue: 9, state: "closed" },
		{ dashboardIssue: 9, number: 10 },
	]) {
		const f = fixture([pull()], [review("APPROVED")]);
		Object.assign(f.issue, change);
		await assert.rejects(
			execute(f, { apply: true, dashboardIssue: change.dashboardIssue }),
		);
		assert.deepEqual(f.writes, []);
	}
});

test("late collection errors prevent all writes, including exemption synchronization", async () => {
	for (const failure of [
		"reviews",
		"graphql",
		"inventory",
		"shape",
		"review-shape",
	]) {
		const f = fixture([pull(), pull({ number: 2 })], [review("APPROVED")]);
		if (failure === "reviews")
			f.github.paginate = async (route, args) => {
				if (route === "pulls") return [pull(), pull({ number: 2 })];
				if (args.pull_number === 2) throw new Error("page two unavailable");
				return [review("APPROVED")];
			};
		if (failure === "graphql")
			f.github.graphql = async () => {
				throw new Error("GraphQL failure");
			};
		if (failure === "inventory")
			f.github.paginate = async () => {
				throw new Error("PR page failure");
			};
		if (failure === "shape")
			f.github.paginate = async () => [pull({ labels: null })];
		if (failure === "review-shape")
			f.github.paginate = async (route) =>
				route === "pulls" ? [pull()] : [{ state: "APPROVED" }];
		await assert.rejects(execute(f, { apply: true, dashboardIssue: 9 }));
		assert.deepEqual(f.writes, [], failure);
	}
});

test("oversize dashboard and write failures reject without reporting success", async () => {
	const large = fixture(
		[pull({ title: "x".repeat(65000) })],
		[review("APPROVED")],
	);
	await assert.rejects(
		execute(large, { apply: true, dashboardIssue: 9 }),
		/body limit/,
	);
	assert.deepEqual(large.writes, []);
	const f = fixture([pull()], [review("APPROVED")]);
	f.github.rest.issues.addLabels = async () => {
		throw new Error("write denied");
	};
	await assert.rejects(
		execute(f, { apply: true, dashboardIssue: 9 }),
		/write denied/,
	);
	assert.deepEqual(f.writes, []);
});

test("requested reviewer pages preserve all users and teams and fail before writes", async () => {
	const f = fixture();
	f.github.rest.pulls.requestedReviewers = async ({ page }) => ({
		headers: page === 1 ? { link: '<next>; rel="next"' } : {},
		data: {
			users: [{ login: `reviewer${page}` }],
			teams: [{ name: `Team ${page}` }],
		},
	});
	const result = await execute(f);
	assert.match(result.body, /reviewer1, reviewer2, Team 1, Team 2/);
	assert.match(result.body, /Generated at 2026-09-29T12:00:00.000Z/);
	f.github.rest.pulls.requestedReviewers = async ({ page }) => {
		if (page === 2) throw new Error("second reviewer page failed");
		return {
			headers: { link: '<next>; rel="next"' },
			data: { users: [], teams: [] },
		};
	};
	await assert.rejects(execute(f, { apply: true, dashboardIssue: 9 }));
	assert.deepEqual(f.writes, []);
});

test("bots need no review reads and unavailable merge aggregates never establish readiness", async () => {
	const bot = fixture([pull({ user: { login: "robot", type: "Bot" } })]);
	bot.github.graphql = async () => {
		throw new Error("unexpected bot read");
	};
	bot.github.rest.pulls.requestedReviewers = bot.github.graphql;
	const result = await execute(bot);
	assert.match(result.body, /Exempt: bot author/);
	assert.equal(bot.reads.length, 1);
	const human = fixture([pull()], [review("APPROVED")]);
	for (const aggregate of [null, {}, { repository: { pullRequest: null } }]) {
		human.github.graphql = async () => aggregate;
		const preview = await execute(human);
		assert.match(preview.body, /Readiness unconfirmed/);
		assert.match(preview.body, /Exempt: current approval/);
	}
});

test("review-required blocks retain reviewers and author as next actors", () => {
	const pr = observed({
		reviewers: ["reviewer", "Network team"],
		merge: {
			headRefOid: "abc",
			mergeStateStatus: "BLOCKED",
			reviewDecision: "REVIEW_REQUIRED",
		},
	});
	const status = classify(pr);
	assert.match(status.actor, /reviewer/);
	assert.match(status.actor, /Network team/);
	assert.match(status.actor, new RegExp(pr.author));
	assert.match(status.action, /review/i);
	assert.notEqual(status.state, "Ready to merge");
});
