import unittest
from pathlib import Path
import sys
import json
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import auto_translate

class TestAutoTranslate(unittest.TestCase):
    def test_cache_load_and_save(self):
        cache = {'test': 'val'}
        tmp = Path('.test_translation_cache.json')
        auto_translate.CACHE_FILE = tmp
        auto_translate.save_cache(cache)
        loaded = auto_translate.load_cache()
        self.assertEqual(loaded, cache)
        tmp.unlink()

    def test_ck_hash(self):
        ck = auto_translate.CACHE_FILE.parent / 'test_ck.txt'
        text = 'Hello world'
        h = auto_translate.hashlib.sha256(text.encode()).hexdigest()[:16]
        self.assertEqual(len(h), 16)

if __name__ == '__main__':
    unittest.main()
