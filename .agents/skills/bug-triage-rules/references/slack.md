# Slack recipes

Channel names, prefixes, titles and the lookback come from the constitution's Slack section. The
skills only read Slack.

## Find every link to a bug

Search all public and private channels for links, not keywords: a keyword search of a few channels
misses the threads in customer and prospect channels.

- Call `slack_search_public_and_private` with:
  - `keywords`: `["\"<owner>/<name>/issues\""]`, once for each repository
  - `filters`: `after:<the day before the start date>`, so messages from the start day count
  - `channel_types`: `public_channel,private_channel`, which leaves out the notification messages
    sent to people directly
  - `sort`: `timestamp`
- Add `-in:#<channel>` to the filters for each of the constitution's channels left out of link
  searches.
- Page with `cursor` until no results are left. Search in windows of at most two weeks, because a
  longer window can fill the search's page limit before it reaches the start date.
- Search again with the Jira issue link of each Jira project, `"<Jira site host>/browse/<project key>-"`,
  to catch the threads that link the Jira issue instead.
- The start date is the lookback for triaging-new-bugs, and the period start for scheduling-bugs.

## Sort the hits

1. Drop every hit from a channel whose name starts with a never-read prefix. The search returns
   their text with the other hits: drop them before you read on, never open their threads, and use
   nothing from them.
2. Keep only hits whose text holds a link to one issue: `github.com/<owner>/<name>/issues/<number>`
   or `<Jira site host>/browse/<key>`. The search also returns pull request links and messages that
   only mention the repository.
3. Keep the issue number or Jira key, the channel, the date, the person who posted, and the
   message link.
4. Group the rest:
   - **Escalation:** the escalation channel.
   - **Customer or prospect:** a channel whose name starts with a customer channel prefix and is not
     one of the constitution's customer channel exceptions. The rest of the name names the customer
     or prospect.
   - **Other channels:** for triaging-new-bugs, a hit here counts only as an SA or FAE report, when
     the person who posted it is one. For scheduling-bugs, it also counts as discussion, unless a
     bot posted it.

Read a thread with `slack_read_thread` only when the table needs what it says: the customer impact,
a workaround, a deadline, or who is blocked.

## SA and FAE reports

Read the profile of the person with `slack_read_user_profile`, once per person. A title that
contains one of the constitution's SA and FAE titles, ignoring case, marks an SA or FAE report. Do
not rely on a list of names.

- **The person who posted a link:** the hit names them.
- **The person who filed a GitHub issue:** search for them with `slack_search_users`, by the name
  on their GitHub profile when it can be read, otherwise by their GitHub login.
