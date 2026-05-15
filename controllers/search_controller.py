from utils.accent_utils import remove_accents


class SearchController:
    def __init__(self, search_engine, entry_list):
        self.engine = search_engine
        self.entry_list = entry_list
        self.current_results = []

    def search(self, text):
        text = text.strip()
        if text == "":
            results = self.engine.search("")
            self.current_results = [r for r in results if r[1] != "!SOURCES"]
        else:
            self.current_results = self.engine.search(text)
        self.entry_list.display_results(self.current_results)
        return self.current_results

    def get_all_words(self):
        results = self.engine.search("")
        return [r[1] for r in results if r[1] != "!SOURCES"]