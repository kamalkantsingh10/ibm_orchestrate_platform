"""Repository layer — the only path that touches SQL.

Per ``architecture.md#Architectural Boundaries`` (data boundary):
* Repos own all SQL.
* ORM rows never escape a repo.
* Wire types are the ``packages/contracts`` Pydantic models.
"""
