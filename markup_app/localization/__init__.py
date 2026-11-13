import os

from dictionary_app.localization import strings as dictionary_strings
from dictionary_app.localization.load_strings import load_strings

strings = load_strings(
    os.path.dirname(__file__), 'strings.json',
    shared={'dictionary_app': dictionary_strings},
)
