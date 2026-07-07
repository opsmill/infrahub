Fixed the branch merge rollback so that a database error (such as an out-of-memory error) raised
partway through the merge queries no longer leaves partially merged data on the destination
branch. The rollback now removes every change stamped with the merge timestamp even when the
failure occurred before the merge finished writing all of its batches.
