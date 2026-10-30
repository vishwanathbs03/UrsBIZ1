"""JSON-backed knowledge repository.

Reads ``knowledge_catalog.json`` from disk on every instance
construction. The catalog is small (< 100 articles expected) so
re-reading on each request is cheap. The repository is
read-only — the Sprint 3 Part 1 spec says "store articles in a
simple JSON-based repository or lightweight database abstraction
for now", and the JSON file IS the database.

Why a separate class and not a module-level list:
  * The service receives the repository in its constructor, so a
    future milestone can substitute a SQLite or Postgres-backed
    implementation without touching the service or the endpoint.
  * Tests can construct an in-memory repository with a handful
    of hand-written articles.

Why the dataclass index:
  * ``list_articles()`` and ``get_article()`` both need a fast
    id → article map. Building it once at construction time
    keeps the per-request path O(1).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from app.services.knowledge.base import (
    Article,
    KnowledgeArticleNotFound,
    KnowledgeRepositoryBase,
    article_from_dict,
)


logger = logging.getLogger(__name__)


_CATALOG_CACHE: dict[str, dict[str, Article]] = {}


class JsonKnowledgeRepository(KnowledgeRepositoryBase):
    """Read-only repository backed by a JSON file on disk.

    The constructor reads the file once and builds an id → article
    map. If the file is missing or unparseable, the repository
    raises on construction — the failure should be loud, not
    silent (an empty catalog is a data bug, not a state of the
    world).
    """

    def __init__(self, catalog_path: Path | str | None = None) -> None:
        from app.services.knowledge.base import DEFAULT_CATALOG_PATH

        self._path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
        self._articles: dict[str, Article] = {}
        self._load()

    def _load(self) -> None:
        path_str = str(self._path)
        if path_str in _CATALOG_CACHE:
            self._articles = _CATALOG_CACHE[path_str]
            return

        if not self._path.exists():
            raise FileNotFoundError(
                f"Knowledge catalog not found at {self._path}"
            )
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Knowledge catalog at {self._path} is not valid JSON: {exc}"
            ) from exc

        articles_raw = raw.get("articles", []) if isinstance(raw, dict) else raw
        if not isinstance(articles_raw, list):
            raise ValueError(
                f"Knowledge catalog at {self._path} must have an 'articles' list"
            )

        for entry in articles_raw:
            if not isinstance(entry, dict):
                logger.warning("Skipping non-dict article entry in %s", self._path)
                continue
            if "id" not in entry:
                logger.warning("Skipping article without id in %s", self._path)
                continue
            entry_with_stamp = dict(entry)
            if not entry_with_stamp.get("created_at"):
                # Stamp with the file's mtime so the field is
                # always populated, but the value is stable for a
                # given catalog checkout.
                mtime = datetime.fromtimestamp(self._path.stat().st_mtime)
                entry_with_stamp["created_at"] = mtime.date().isoformat()
            self._articles[entry_with_stamp["id"]] = article_from_dict(entry_with_stamp)

        if not self._articles:
            raise ValueError(
                f"Knowledge catalog at {self._path} contained no articles"
            )

        _CATALOG_CACHE[path_str] = self._articles
        logger.info("Loaded %d knowledge articles from %s (cached)", len(self._articles), self._path)

    # ---- Read side --------------------------------------------------------- #

    def list_articles(self) -> list[Article]:
        """Return every article, in stable id-sorted order.

        Stable order matters for the API contract: two calls in a
        row must produce the same sequence of ids so the client can
        prove determinism by diffing the responses.
        """
        return [self._articles[k] for k in sorted(self._articles.keys())]

    def get_article(self, article_id: str) -> Article:
        if article_id not in self._articles:
            raise KnowledgeArticleNotFound(
                f"Knowledge article '{article_id}' not found"
            )
        return self._articles[article_id]

    def count(self) -> int:
        return len(self._articles)
