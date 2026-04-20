import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import tex_watch

class TestRenderHtml(unittest.TestCase):
    def test_render_html_minimal(self):
        # Minimal data dict for rendering
        data = {
            'name': 'Test Name',
            'subtitle': 'Subtitle',
            'left': {
                'profile': 'Profile',
                'contact': [],
                'languages': [],
                'cert_sidebar': {'title': '', 'title_href': '', 'sub': '', 'sub_href': '', 'date': ''},
                'skills': [],
                'traits': []
            },
            'right': {
                'experience': [],
                'education': [],
                'cert_bullets': []
            },
            'hobbies': '',
            'nationalities': '',
            'permits': ''
        }
        html = tex_watch.render_html(data)
        self.assertIn('<html', html)
        self.assertIn('Test Name', html)
        self.assertIn('Subtitle', html)

if __name__ == '__main__':
    unittest.main()
