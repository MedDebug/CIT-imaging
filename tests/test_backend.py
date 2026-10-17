import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        server.DB = Path(cls.temp.name) / "cit.sqlite3"
        server.initialize()
        cls.http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.http.server_port}"
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(self.base + path, data=data,
                          headers={"Content-Type": "application/json"} if data else {})
        try:
            with urlopen(request) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_server_persists_workflow_and_rejects_invalid_changes(self):
        status, health = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["inference"], "simulated")

        status, initial = self.request("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(len(initial["cases"]), 8)

        status, created = self.request("/api/studies/demo", {})
        self.assertEqual(status, 200)
        study_id = created["changedId"]
        self.assertEqual(study_id, "CXR-0019")

        status, error = self.request(f"/api/studies/{study_id}/override",
                                     {"priority": "High", "reason": "bad"})
        self.assertEqual(status, 400)
        self.assertIn("reason", error["error"])

        status, changed = self.request(f"/api/studies/{study_id}/override",
                                       {"priority": "Medium", "reason": "Reviewer checked the study."})
        self.assertEqual(status, 200)
        study = next(case for case in changed["cases"] if case["id"] == study_id)
        self.assertEqual(study["override"]["priority"], "Medium")

        status, reviewed = self.request(f"/api/studies/{study_id}/review", {})
        self.assertEqual(status, 200)
        self.assertEqual(len(reviewed["events"]), 3)
        self.assertEqual(self.request(f"/api/studies/{study_id}/review", {})[0], 409)

        # Reopen the database rather than relying on in-memory state.
        server.initialize()
        with server.connection() as db:
            persisted = server.snapshot(db)
        study = next(case for case in persisted["cases"] if case["id"] == study_id)
        self.assertEqual(study["status"], "Reviewed")
        self.assertEqual(study["override"]["reason"], "Reviewer checked the study.")
        self.assertEqual(len(persisted["events"]), 3)

    def test_failed_image_checks_preserve_high_clinical_priority(self):
        with server.connection() as db:
            row = db.execute("SELECT * FROM studies WHERE seq=17").fetchone()
        self.assertEqual(server.suggested(row), "High")
        self.assertEqual(self.request("/api/studies/import", {
            "clinical": "Routine", "image": "data:image/png;base64,bm90IGFuIGltYWdl"
        })[0], 400)


if __name__ == "__main__":
    unittest.main()
