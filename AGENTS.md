for backend, use uv for dependency management. a few useful commands:

uv sync
uv add <PACKAGE-NAME>
uv run python <PYTHON-FILE>

regularly commit code to git

Before starting code modifications, create a new feature git branch
(e.g. `git checkout -b feat/<short-description>`) and do all work there,
never directly on main.

Ensure that the code follows SOLID clean code standard and functions are no longer than 50 lines.