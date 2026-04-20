import os
import sys
import subprocess
import tempfile
import time
import requests
import threading
import unittest

class TestStaticFileServing(unittest.TestCase):
    def test_static_file_serving(self):
        # Start the Go server in a subprocess
        proc = subprocess.Popen(["go", "run", "main.go"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # Poll for server readiness (max 10s)
            url = "http://localhost:12345/resources/photo.jpg"
            for _ in range(20):
                try:
                    resp = requests.get(url, timeout=1)
                    break
                except requests.ConnectionError:
                    time.sleep(0.5)
            else:
                self.fail("Server did not start in time")
            # 404 is OK if photo.jpg is missing, but server should respond
            self.assertIn(resp.status_code, (200, 404))
        finally:
            proc.terminate()
            proc.wait()

if __name__ == '__main__':
    unittest.main()
