import os

from dictionary_app.localization.loader import load_strings

strings = load_strings(os.path.dirname(__file__), 'strings.json')
