# Minimal in-memory stand-in for the parts of MongoDB we use, so tests need no server.
import copy
from types import SimpleNamespace
from bson import ObjectId
from pymongo.errors import DuplicateKeyError


def _match(doc, q):
    for k, v in q.items():
        if k == "$or":
            if not any(_match(doc, sub) for sub in v):
                return False
        elif isinstance(v, dict):
            val = doc.get(k)
            for op, arg in v.items():
                if (op == "$lt" and not val < arg) or (op == "$gt" and not val > arg):
                    return False
        elif doc.get(k) != v:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction=1):
        self.docs.sort(key=lambda d: d[key], reverse=direction < 0)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length=None):
        return [copy.deepcopy(d) for d in self.docs]


class Col:
    def __init__(self, unique):
        self.docs, self.unique = [], unique

    def _check(self, doc):
        for fields in self.unique:
            if any(all(d.get(f) == doc.get(f) for f in fields) for d in self.docs):
                raise DuplicateKeyError("duplicate")

    @staticmethod
    def _apply(d, u):
        for op, fields in u.items():
            for k, v in fields.items():
                if op == "$set":
                    d[k] = v
                elif op == "$inc":
                    d[k] = d.get(k, 0) + v
                elif op == "$max":
                    d[k] = max(d.get(k, 0), v)

    async def find_one(self, q, projection=None):
        return next((copy.deepcopy(d) for d in self.docs if _match(d, q)), None)

    def find(self, q):
        return Cursor([d for d in self.docs if _match(d, q)])

    async def insert_one(self, doc):
        doc = copy.deepcopy(doc)
        doc["_id"] = ObjectId()
        self._check(doc)
        self.docs.append(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    async def update_one(self, q, u, upsert=False):
        for d in self.docs:
            if _match(d, q):
                return self._apply(d, u)
        if upsert:
            new = {k: v for k, v in q.items() if not isinstance(v, dict)}
            new.update(u.get("$setOnInsert", {}))
            new["_id"] = ObjectId()
            self._check(new)
            self.docs.append(new)

    async def find_one_and_update(self, q, u, return_document=None):
        for d in self.docs:
            if _match(d, q):
                self._apply(d, u)
                return copy.deepcopy(d)


class FakeDb:
    def __init__(self):
        self.conversations = Col([("pair_key",)])
        self.messages = Col([("conversation_id", "seq"), ("conversation_id", "sender_id", "client_msg_id")])
