import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import tex_watch

class TestTexWatch(unittest.TestCase):
    def test_tex_to_html_inline(self):
        tex = r"\textbf{Bold} and \textit{Italic} and \emph{Emph}"  # basic markup
        html = tex_watch.tex_to_html_inline(tex)
        self.assertIn('<b>Bold</b>', html)
        self.assertIn('<i>Italic</i>', html)
        self.assertIn('<i>Emph</i>', html)

    def test_strip_tex(self):
        tex = r"Some \textbf{bold} text"
        plain = tex_watch.strip_tex(tex)
        self.assertIn('bold', plain)
        self.assertNotIn('\\textbf', plain)

    def test_parse_tex(self):
        # Only check that parsing does not throw and returns a dict
        data = tex_watch.parse_tex(tex_watch.TEX_FILE)
        self.assertIsInstance(data, dict)
        self.assertIn('name', data)
        self.assertIn('left', data)
        self.assertIn('right', data)

if __name__ == '__main__':
    unittest.main()
