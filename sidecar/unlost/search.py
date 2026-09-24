"""Hybrid search: meaning (embeddings) + exact words (FTS5) + filenames (+ CLIP for photos), fused with RRF,
then nudged by the "when" and "what kind" parsed out of the query."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from .db import DB
from .embeddings import ClipEmbedder, TextEmbedder, VectorIndex
from .query_parse import KIND_WORDS, ParsedQuery, months_in_range, parse

RRF_K = 60
# Below this cosine similarity a meaning-only match is noise for bge-small.
MIN_SEMANTIC = 0.55
MIN_CLIP = 0.22
RELATIVE_CUTOFF = 0.15
SEMANTIC_BAND = 0.08

STOPWORDS = set("""a an and are as at be but by for from has have i i'm in is it its me my of on or our that the
their them this to was were what when where which who will with you your about into over that those these there
remember find show file files document documents thing stuff sent got received saved downloaded something
last this year month week ago did do does how much many""".split())


@dataclass
class Hit:
    file_id: int
    score: float = 0.0
    semantic: float = 0.0
    best_chunk: int | None = None
    best_chunk_score: float = -1.0
    reasons: list[str] = field(default_factory=list)


# File-type words are handled by the kind boost; as keywords they'd match every file card ("Image or photo").
TYPE_WORDS = {w for words in KIND_WORDS.values() for w in words if " " not in w} | {"image", "document", "file"}


def keywords(text: str) -> list[str]:
    toks = re.findall(r"[\w']+", text.lower())
    return [t for t in toks if t not in STOPWORDS and t not in TYPE_WORDS and len(t) > 1][:12]


def fts_query(tokens: list[str], prefix: bool = False) -> str | None:
    if not tokens:
        return None
    star = "*" if prefix else ""
    return " OR ".join(f'"{t.replace(chr(34), "")}"{star}' for t in tokens)


class Searcher:
    def __init__(self, db: DB, embedder: TextEmbedder, clip: ClipEmbedder, clip_enabled) -> None:
        self.db = db
        self.embedder = embedder
        self.clip = clip
        self.clip_enabled = clip_enabled  # callable -> bool
        self.chunk_index = VectorIndex(db, "chunks")
        self.image_index = VectorIndex(db, "image_vecs")

    # ---- ranked lists --------------------------------------------------------------------------

    def _semantic(self, pq: ParsedQuery, k: int) -> list[tuple[int, int, float]]:
        return self.chunk_index.search(self.embedder.embed_query(pq.text), k)

    def _fulltext(self, tokens: list[str], k: int) -> list[tuple[int, int]]:
        q = fts_query(tokens)
        if not q:
            return []
        rows = self.db.query(
            """SELECT c.id, c.file_id FROM chunks_fts f JOIN chunks c ON c.id = f.rowid
               WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?""", (q, k))
        return [(r["id"], r["file_id"]) for r in rows]

    def _names(self, tokens: list[str], k: int) -> list[int]:
        q = fts_query(tokens, prefix=True)
        if not q:
            return []
        rows = self.db.query("SELECT rowid FROM names_fts WHERE names_fts MATCH ? ORDER BY bm25(names_fts) LIMIT ?", (q, k))
        return [r["rowid"] for r in rows]

    def _clip(self, pq: ParsedQuery, k: int) -> list[tuple[int, float]]:
        if not self.clip_enabled():
            return []
        try:
            vec = self.clip.embed_query(pq.text)
        except Exception:
            return []
        return [(fid, s) for _, fid, s in self.image_index.search(vec, k) if s >= MIN_CLIP]

    # ---- public API ----------------------------------------------------------------------------

    def search(self, query: str, limit: int = 30, today=None) -> list[dict]:
        pq = parse(query, today)
        tokens = keywords(pq.text)
        hits: dict[int, Hit] = {}

        def hit(fid: int) -> Hit:
            return hits.setdefault(fid, Hit(fid))

        file_rank = 0
        for chunk_id, fid, sim in self._semantic(pq, 300):
            if sim < MIN_SEMANTIC:
                break
            h = hit(fid)
            if sim > h.semantic:
                if h.semantic == 0.0:
                    h.score += 1.0 / (RRF_K + file_rank)
                    file_rank += 1
                h.semantic = sim
            if sim > h.best_chunk_score:
                h.best_chunk, h.best_chunk_score = chunk_id, sim

        seen: set[int] = set()
        for chunk_id, fid in self._fulltext(tokens, 300):
            if fid in seen:
                continue
            seen.add(fid)
            h = hit(fid)
            h.score += 0.9 / (RRF_K + len(seen) - 1)
            h.reasons.append("Words match")
            if h.best_chunk is None or h.best_chunk_score < 0.7:
                h.best_chunk, h.best_chunk_score = chunk_id, 0.7

        for rank, fid in enumerate(self._names(tokens, 100)):
            hit(fid).score += 1.0 / (RRF_K + rank)
            hit(fid).reasons.append("Name matches")

        for rank, (fid, _) in enumerate(self._clip(pq, 100)):
            hit(fid).score += 1.0 / (RRF_K + rank)
            hit(fid).reasons.append("Looks like it")

        if not hits:
            return []
        rows = {r["id"]: r for r in self.db.query(
            f"SELECT * FROM files WHERE id IN ({','.join('?' * len(hits))})", list(hits))}
        wanted_months = months_in_range(pq.start, pq.end) if pq.has_date else set()

        best_semantic = max((h.semantic for h in hits.values()), default=0.0)
        results = []
        for fid, h in hits.items():
            f = rows.get(fid)
            if f is None:
                continue
            # Meaning-only matches must be close to the best one; otherwise every file "sort of" matches.
            if not h.reasons and h.semantic < best_semantic - SEMANTIC_BAND:
                continue
            if h.semantic:
                h.reasons.insert(0, "Similar meaning")
            score = h.score * (1.0 + max(0.0, h.semantic - MIN_SEMANTIC))
            if pq.has_date:
                if _in_range(f, pq) or wanted_months & set(f["months"].split()):
                    score *= 1.8
                    h.reasons.append(pq.date_label)
                else:
                    score *= 0.55
            if pq.kinds:
                if f["kind"] in pq.kinds:
                    score *= 1.5
                else:
                    score *= 0.5
            if pq.wants_screenshot and ("screenshot" in f["name"].lower() or "screen shot" in f["name"].lower()):
                score *= 1.4
            if f["ocr"]:
                h.reasons.append("Text read from image" if f["kind"] == "image" else "Scanned (OCR)")
            results.append((score, h, f))

        results.sort(key=lambda t: t[0], reverse=True)
        # Weak meaning-only matches far below the best hit are noise; the user wants *the* file.
        results = [r for r in results if r[0] >= RELATIVE_CUTOFF * results[0][0]]
        chunk_ids = [h.best_chunk for _, h, _ in results[:limit] if h.best_chunk is not None]
        chunks = {r["id"]: r for r in self.db.query(
            f"SELECT id, idx, page, text FROM chunks WHERE id IN ({','.join('?' * len(chunk_ids))})", chunk_ids)} if chunk_ids else {}

        out = []
        for score, h, f in results[:limit]:
            ch = chunks.get(h.best_chunk) if h.best_chunk is not None else None
            use_chunk = ch is not None and ch["idx"] >= 0
            snippet_src = ch["text"] if use_chunk else f["preview"]
            out.append({
                **file_dict(f),
                "score": round(score, 5),
                "snippet": snippet(snippet_src, tokens),
                "page": ch["page"] if use_chunk else None,
                "reasons": list(dict.fromkeys(h.reasons))[:4],
            })
        return out

    def retrieve_chunks(self, question: str, k: int = 14, per_file: int = 3, max_chars: int | None = None,
                        today=None) -> list[dict]:
        """Chunk-level retrieval for Q&A: the passages most likely to contain the answer, up to k passages
        or max_chars of text, whichever comes first (many short receipts beat a few long pages for totals)."""
        pq = parse(question, today)
        tokens = keywords(pq.text)
        scores: dict[int, float] = {}
        chunk_file: dict[int, int] = {}
        for rank, (cid, fid, sim) in enumerate(self._semantic(pq, max(80, k * 3))):
            if sim < MIN_SEMANTIC - 0.1:
                break
            scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank)
            chunk_file[cid] = fid
        for rank, (cid, fid) in enumerate(self._fulltext(tokens, 80)):
            scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank)
            chunk_file[cid] = fid
        if not scores:
            return []

        fids = set(chunk_file.values())
        files = {r["id"]: r for r in self.db.query(
            f"SELECT * FROM files WHERE id IN ({','.join('?' * len(fids))})", list(fids))}
        wanted_months = months_in_range(pq.start, pq.end) if pq.has_date else set()
        for cid, fid in chunk_file.items():
            f = files.get(fid)
            if f is None:
                scores[cid] = 0
                continue
            if pq.has_date:
                scores[cid] *= 1.6 if (_in_range(f, pq) or wanted_months & set(f["months"].split())) else 0.7
            if pq.kinds:
                scores[cid] *= 1.4 if f["kind"] in pq.kinds else 0.7

        ranked = sorted(scores, key=scores.get, reverse=True)
        rows = {r["id"]: r for r in self.db.query(
            f"SELECT id, file_id, idx, page, text FROM chunks WHERE id IN ({','.join('?' * len(ranked))})", ranked)}
        picked, per, used = [], {}, 0
        for cid in ranked:
            r = rows.get(cid)
            # File cards (idx -1) only describe name/folder/date; they're useless as evidence for an answer.
            if r is None or r["idx"] < 0 or scores[cid] <= 0 or per.get(r["file_id"], 0) >= per_file:
                continue
            if max_chars and picked and used + len(r["text"]) > max_chars:
                break
            used += len(r["text"])
            per[r["file_id"]] = per.get(r["file_id"], 0) + 1
            f = files[r["file_id"]]
            picked.append({"chunk_id": cid, "text": r["text"], "page": r["page"], **file_dict(f)})
            if len(picked) >= k:
                break
        return picked


def _in_range(f, pq: ParsedQuery) -> bool:
    stamps = [f["mtime"], f["ctime"], f["taken"]]
    start = datetime.combine(pq.start, datetime.min.time()).timestamp()
    end = datetime.combine(pq.end, datetime.min.time()).timestamp()
    return any(s and start <= s < end for s in stamps)


def file_dict(f) -> dict:
    return {
        "id": f["id"], "path": f["path"], "name": f["name"], "folder": f["folder"], "kind": f["kind"],
        "ext": f["ext"], "size": f["size"], "mtime": f["mtime"], "status": f["status"],
        "has_thumb": f["kind"] in ("image", "pdf"),
    }


def snippet(text: str, tokens: list[str], width: int = 240) -> str:
    text = " ".join((text or "").split())
    if len(text) <= width:
        return text
    low = text.lower()
    positions = [low.find(t) for t in tokens if low.find(t) >= 0]
    start = max(0, min(positions) - 60) if positions else 0
    # Snap to a word boundary.
    if start:
        space = text.find(" ", start)
        start = space + 1 if 0 <= space < start + 20 else start
    out = text[start:start + width].rstrip()
    return ("…" if start else "") + out + ("…" if start + width < len(text) else "")

