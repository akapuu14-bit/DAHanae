"""ReadOnlyGuard（α-Rの安全装置）の動作確認。実DB・偽repoには依存しない（スタブclientだけ）。"""

import unittest

from sxx_common import ReadOnlyGuard


class _Query:
    def __init__(self, log, table):
        self.log, self.table = log, table

    def select(self, *a, **k):
        self.log.append((self.table, "select"))
        return self

    def insert(self, *a, **k):
        self.log.append((self.table, "REAL-insert"))
        return self

    def update(self, *a, **k):
        self.log.append((self.table, "REAL-update"))
        return self

    def delete(self, *a, **k):
        self.log.append((self.table, "REAL-delete"))
        return self

    def upsert(self, *a, **k):
        self.log.append((self.table, "REAL-upsert"))
        return self

    def eq(self, *a):
        return self

    def execute(self):
        class R:
            data = [{"id": 1}]
            count = None

        return R()


class _Client:
    def __init__(self):
        self.log = []

    def table(self, name):
        return _Query(self.log, name)

    def rpc(self, *a, **k):
        self.log.append(("rpc", "REAL"))


class GuardTest(unittest.TestCase):
    def test_reads_pass_through_and_writes_never_reach_the_client(self):
        client = _Client()
        guard = ReadOnlyGuard(client)
        guard.install()
        self.addCleanup(guard.uninstall)
        self.assertEqual(client.table("employees").select("*").eq("id", 1).execute().data, [{"id": 1}])
        for op in ("insert", "update", "delete", "upsert"):
            result = getattr(client.table("action_logs"), op)({"x": 1}).eq("id", 1).execute()
            self.assertEqual(result.data, [])
        self.assertEqual(client.log, [("employees", "select")])  # 書込は1件も client に届いていない
        self.assertEqual([op for _, op in guard.attempts], ["insert", "update", "delete", "upsert"])
        with self.assertRaises(AssertionError):
            client.rpc("anything")

    def test_not_chain_on_blocked_write_is_safe(self):
        client = _Client()
        guard = ReadOnlyGuard(client)
        guard.install()
        self.addCleanup(guard.uninstall)
        client.table("t").delete().not_.in_("a", [1]).execute()
        self.assertEqual(client.log, [])

    def test_uninstall_restores_client(self):
        client = _Client()
        original = client.table
        guard = ReadOnlyGuard(client)
        guard.install()
        guard.uninstall()
        self.assertEqual(client.table.__func__, original.__func__)
        self.assertTrue(hasattr(client, "rpc"))


if __name__ == "__main__":
    unittest.main()
