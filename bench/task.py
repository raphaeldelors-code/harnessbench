"""Shared task text — identical for every harness (the only variable is the harness)."""

TASK_TEMPLATE = """\
You are working in a git repository at /testbed, checked out at the base commit \
of a bug report. Do not create branches and do not commit.

Bug report:
{problem_statement}

Investigate the repository, reproduce the problem, and fix it with a minimal \
change to the repository sources (do not edit installed copies of the package \
under site-packages). Run the relevant tests if practical. Leave your changes \
in the working tree when you are done."""
