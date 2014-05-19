import os
import re
import sublime

#--------------------------------------------------------------------------
# This is the class that outputs test progress and results into a window
#--------------------------------------------------------------------------
class OutputWindow():
    def __init__(self, window, plugin_dir, name):

        self.console = window.new_file()
        self.console.set_name(name)

        self.console.set_scratch(True)
        self.console.set_read_only(True)
        self.console.set_syntax_file(os.path.join(plugin_dir, 'robot-output.tmLanguage'))

    def append_text(self, output):

        self.console.set_read_only(False)
        edit = self.console.begin_edit()
        self.console.insert(edit, self.console.size(), output)
        self.console.end_edit(edit)
        self.console.set_read_only(True)

