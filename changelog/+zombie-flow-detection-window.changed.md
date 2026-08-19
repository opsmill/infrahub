Flow runs that stop sending heartbeats are marked as crashed only after a longer grace period, so a run waiting out an automatic retry is no longer prematurely marked as crashed.
