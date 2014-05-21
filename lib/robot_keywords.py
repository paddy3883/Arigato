import os
import sublime
import threading
import stdlib_keywords

from robot_scanner import Scanner
from robot_common import is_robot_file, views_to_center

#------------------------------------------------------
# 
#------------------------------------------------------

class GoToKeywordThread(threading.Thread):
    def __init__(self, view, view_file, keyword, folders):
        self.view = view
        self.view_file = view_file
        self.keyword = keyword
        self.folders = folders
        threading.Thread.__init__(self)

    def run(self):
        scanner = Scanner(self.view)
        keywords = scanner.scan_file(self.view_file)

        for folder in self.folders:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if is_robot_file(f) and f != '__init__.txt':
                        path = os.path.join(root, f)
                        scanner.scan_without_resources(path, keywords)

        results = []
        for bdd_prefix in ['given ', 'and ', 'when ', 'then ']:
            if self.keyword.lower().startswith(bdd_prefix):
                substr = self.keyword[len(bdd_prefix):]
                results.extend(self.search_user_keywords(keywords, substr))
                results.extend(stdlib_keywords.search_keywords(substr))

        results.extend(self.search_user_keywords(keywords, self.keyword))
        results.extend(stdlib_keywords.search_keywords(self.keyword))

        sublime.set_timeout(lambda: self._select_keyword_and_go(self.view, results), 0)

    def search_user_keywords(self, keywords, name):
        lower_name = name.lower()
        if not keywords.has_key(lower_name):
            return []
        return keywords[lower_name]

    def _select_keyword_and_go(self, view, results):
        def on_done(index):
            if index == -1:
                return
            results[index].show_definition(view, views_to_center)

        if len(results) == 1 and results[0].allow_unprompted_go_to():
            results[0].show_definition(view, views_to_center)
            return

        result_strings = []
        for kw in results:
            strings = [kw.name]
            strings.extend(kw.description)
            result_strings.append(strings)
        view.window().show_quick_panel(result_strings, on_done)
