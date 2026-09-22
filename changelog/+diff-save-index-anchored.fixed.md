Fixed saving the diff of a large branch slowing down as more nodes were written: every batch of diff nodes now costs the same however many nodes the diff already holds.
