Fixed merges that re-run a Generator set to execute after merge leaving an unused diff stored in the database. The diffs left by earlier merges can be removed with `infrahub db delete-diffs`.
