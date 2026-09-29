"use strict";

const MARKER = "<!-- infrahub-pr-lifecycle-dashboard -->";
const OWNED_LABELS = ["lifecycle-approved", "lifecycle-bot"];
const DAY = 86400000;
const QUERY = `query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) { headRefOid mergeable mergeStateStatus reviewDecision }
  }
}`;

function requireValue(condition, message) {
	if (!condition) throw new Error(message);
}

function plain(value) {
	return String(value)
		.replace(/[\r\n\t]/g, " ")
		.replace(
			/[&<>@\\`*_[\]{}()|!#~]/g,
			(character) => `&#${character.codePointAt(0)};`,
		);
}

function reviewState(reviews) {
	const decisive = new Map();
	for (const review of [...reviews].sort((a, b) => a.id - b.id)) {
		requireValue(
			Number.isSafeInteger(review.id) && typeof review.user?.login === "string",
			"Incomplete review identity",
		);
		requireValue(
			[
				"APPROVED",
				"CHANGES_REQUESTED",
				"DISMISSED",
				"COMMENTED",
				"PENDING",
			].includes(review.state),
			"Unknown review state",
		);
		if (["APPROVED", "CHANGES_REQUESTED", "DISMISSED"].includes(review.state)) {
			decisive.set(review.user.login, review.state);
		}
	}
	return {
		approved: [...decisive.values()].includes("APPROVED"),
		changes: [...decisive.values()].includes("CHANGES_REQUESTED"),
	};
}

async function collect(github, repository) {
	const pulls = await github.paginate(github.rest.pulls.list, {
		...repository,
		state: "open",
		per_page: 100,
	});
	requireValue(Array.isArray(pulls), "Incomplete PR inventory");
	const seen = new Set();
	const inventory = [];
	for (const pr of pulls) {
		requireValue(
			Number.isSafeInteger(pr.number) && pr.number > 0 && !seen.has(pr.number),
			"Invalid PR number",
		);
		seen.add(pr.number);
		requireValue(
			pr.state === "open" &&
				typeof pr.title === "string" &&
				typeof pr.draft === "boolean" &&
				typeof pr.head?.sha === "string" &&
				pr.head.sha.length > 0 &&
				typeof pr.user?.login === "string" &&
				pr.user.login.length > 0 &&
				["User", "Bot"].includes(pr.user?.type) &&
				Number.isFinite(Date.parse(pr.updated_at)) &&
				Array.isArray(pr.labels) &&
				pr.labels.every((label) => typeof label.name === "string") &&
				Array.isArray(pr.requested_reviewers) &&
				Array.isArray(pr.requested_teams),
			"Incomplete PR data",
		);
		if (pr.user.type === "Bot") {
			inventory.push({
				...pr,
				review: { approved: false, changes: false },
				merge: null,
				author: pr.user.login,
				reviewers: [],
			});
			continue;
		}
		const reviews = await github.paginate(github.rest.pulls.listReviews, {
			...repository,
			pull_number: pr.number,
			per_page: 100,
		});
		requireValue(Array.isArray(reviews), "Incomplete review inventory");
		const review = reviewState(reviews);
		const result = await github.graphql(QUERY, {
			...repository,
			number: pr.number,
		});
		const merge = result?.repository?.pullRequest;
		const author = pr.user.login;
		const requestedUsers = [],
			requestedTeams = [];
		for (let page = 1; ; page++) {
			const response = await github.rest.pulls.requestedReviewers({
				...repository,
				pull_number: pr.number,
				per_page: 100,
				page,
			});
			requireValue(
				Array.isArray(response.data?.users) &&
					Array.isArray(response.data?.teams) &&
					response.headers,
				"Incomplete requested reviewers",
			);
			requestedUsers.push(...response.data.users);
			requestedTeams.push(...response.data.teams);
			if (!response.headers.link?.includes('rel="next"')) break;
		}
		const reviewers = [];
		for (const user of requestedUsers) {
			requireValue(
				typeof user.login === "string" && user.login.length > 0,
				"Missing reviewer login",
			);
			reviewers.push(user.login);
		}
		for (const team of requestedTeams) {
			requireValue(typeof team.name === "string", "Incomplete requested team");
			reviewers.push(team.name);
		}
		inventory.push({ ...pr, review, merge, author, reviewers });
	}
	return inventory;
}

function classify(pr) {
	const bot = pr.user.type === "Bot";
	const labels = new Set(pr.labels.map((label) => label.name));
	const exemptions = [
		bot && "bot author",
		pr.review.approved && "current approval",
		labels.has("keep-open") && "keep-open",
	].filter(Boolean);
	const ready =
		pr.review.approved &&
		pr.merge?.headRefOid === pr.head.sha &&
		pr.merge?.mergeable === "MERGEABLE" &&
		pr.merge?.mergeStateStatus === "CLEAN" &&
		(pr.merge.reviewDecision === "APPROVED" ||
			pr.merge.reviewDecision === null);
	let state,
		actor = pr.author,
		action;
	if (bot) {
		state = "Bot";
		action = "Maintainer reviews automation";
		actor = "Maintainer";
	} else if (pr.draft) {
		state = "Draft";
		action = "Finish work and mark ready";
	} else if (pr.review.changes) {
		state = "Changes requested";
		action = "Address requested changes";
	} else if (
		pr.merge?.headRefOid === pr.head.sha &&
		["DIRTY", "UNSTABLE", "BLOCKED"].includes(pr.merge?.mergeStateStatus)
	) {
		state = "Blocked";
		action = "Resolve conflicts, checks or unmet requirements";
	} else if (ready) {
		state = "Ready to merge";
		action = "Merge the PR";
	} else if (pr.reviewers.length) {
		state = "Needs review";
		actor = pr.reviewers.join(", ");
		action = "Review the PR";
	} else if (pr.review.approved) {
		state = "Readiness unconfirmed";
		action = "Check remaining merge requirements";
	} else {
		state = "Needs reviewer";
		action = "Request review";
	}
	const warningDate = new Date(Date.parse(pr.updated_at) + 60 * DAY)
		.toISOString()
		.slice(0, 10);
	const cleanup = exemptions.length
		? `Exempt: ${exemptions.join(", ")}`
		: labels.has("lifecycle-stale")
			? "Warning active; native cleanup after its inactivity window"
			: `Warning estimated on/after ${warningDate}`;
	return { state, actor, action, cleanup, bot };
}

function render(inventory, repository, now = new Date()) {
	const rows = inventory.map((pr) => {
		const status = classify(pr);
		const url = `https://github.com/${repository.owner}/${repository.repo}/pull/${pr.number}`;
		return `| [#${pr.number}](${url}) ${plain(pr.title)} | ${plain(pr.author)} | ${status.state} | ${plain(status.actor)} | ${status.action} | ${new Date(pr.updated_at).toISOString().slice(0, 10)} | ${status.cleanup} |`;
	});
	const body = `${MARKER}\n# Pull request dashboard\n\nGenerated at ${now.toISOString()}.\n\nCleanup dates are rough estimates from GitHub's last update, not closure deadlines. Native stale activity and processing can delay them. Approved, bot-authored and keep-open PRs are exempt.\n\n| PR | Author | State | Next actor | Next action | Last updated (UTC) | Cleanup |\n| --- | --- | --- | --- | --- | --- | --- |\n${rows.join("\n")}\n`;
	requireValue(
		Buffer.byteLength(body, "utf8") <= 65000,
		"Dashboard exceeds issue body limit",
	);
	return body;
}

async function run({
	github,
	owner,
	repo,
	apply = false,
	dashboardIssue,
	now = new Date(),
}) {
	requireValue(
		typeof owner === "string" &&
			typeof repo === "string" &&
			/^[A-Za-z0-9_.-]+$/.test(owner) &&
			/^[A-Za-z0-9_.-]+$/.test(repo),
		"Invalid repository",
	);
	requireValue(typeof apply === "boolean", "apply must be boolean");
	const repository = { owner, repo };
	const inventory = await collect(github, repository);
	const body = render(inventory, repository, now);
	if (!apply) return { body, count: inventory.length };
	requireValue(
		Number.isSafeInteger(dashboardIssue) && dashboardIssue > 0,
		"Explicit dashboard issue required",
	);
	const { data: issue } = await github.rest.issues.get({
		...repository,
		issue_number: dashboardIssue,
	});
	requireValue(
		issue.number === dashboardIssue &&
			!issue.pull_request &&
			issue.state === "open" &&
			issue.body?.startsWith(`${MARKER}\n`),
		"Dashboard issue marker or identity invalid",
	);
	for (const pr of inventory) {
		const wanted = [pr.review.approved, pr.user.type === "Bot"];
		for (const [index, label] of OWNED_LABELS.entries()) {
			const present = pr.labels.some((existing) => existing.name === label);
			const args = { ...repository, issue_number: pr.number };
			if (wanted[index] && !present)
				await github.rest.issues.addLabels({ ...args, labels: [label] });
			if (!wanted[index] && present)
				await github.rest.issues.removeLabel({ ...args, name: label });
		}
	}
	if (issue.body !== body)
		await github.rest.issues.update({
			...repository,
			issue_number: dashboardIssue,
			body,
		});
	return { body, count: inventory.length };
}

module.exports = { MARKER, reviewState, collect, classify, render, run };
