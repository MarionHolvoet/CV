import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import tex_watch

class TestTexWatchEdgeCases(unittest.TestCase):
    def test_parse_invalid_tex(self):
        # Create a minimal invalid TeX file
        tmp = Path('invalid_cv.tex')
        tmp.write_text('No document here', encoding='utf-8')
        try:
            with self.assertRaises(ValueError):
                tex_watch.parse_tex(tmp)
        finally:
            tmp.unlink()

    def test_parse_empty_sections(self):
        # Create a minimal valid TeX with empty sections
        content = r"""
        \begin{document}
        \switchcolumn
        \end{paracol}
        \end{document}
        """
        tmp = Path('empty_cv.tex')
        tmp.write_text(content, encoding='utf-8')
        try:
            data = tex_watch.parse_tex(tmp)
            self.assertIsInstance(data, dict)
        finally:
            tmp.unlink()

if __name__ == '__main__':
    unittest.main()
