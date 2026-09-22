A repository whose default branch is not Infrahub's own default branch could intermittently be read on
the wrong branch. Once a worker had cloned the repository, later operations on that worker - artifact
generation, transforms, generators, computed attributes and proposed change checks - fell back to
Infrahub's default branch instead of the repository's configured default branch. Depending on the
remote, this produced output built from the wrong branch's files or a failure naming a branch that was
never configured. The configured default branch is now resolved every time the repository is accessed,
so all workers behave the same whether or not they already had a local copy.
