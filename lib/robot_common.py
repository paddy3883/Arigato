import os
import sublime

from robot.api import TestCaseFile
from robot.parsing.populators import FromFilePopulator

#--------------------------------------------------------------------------
# This is the class that outputs test progress and results into a window.
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

#--------------------------------------------------------------------------
# This class represents an expanded test file
#--------------------------------------------------------------------------
class RobotTestCaseFile():
    def __init__(self, view):
        # get lines from the test suite
        regions = view.split_by_newlines(sublime.Region(0, view.size()))
        lines = [view.substr(region).encode('ascii', 'replace') + '\n' for region in regions]
        self.file = TestCaseFile(source = view.file_name())
        FromStringPopulator(self.file, lines).populate(self.file.source)

#--------------------------------------------------------------------------
#
#--------------------------------------------------------------------------
class FromStringPopulator(FromFilePopulator):
    def __init__(self, datafile, lines):
        super(FromStringPopulator, self).__init__(datafile)
        self.lines = lines

    def readlines(self):
        return self.lines

    def close(self):
        pass

    def _open(self, path):
        return self

#--------------------------------------------------------------------------
# Commonly used function to check if the current file is a robot file.
#--------------------------------------------------------------------------
def is_robot_format(view):
    return view.settings().get('syntax').endswith('robot.tmLanguage')

def is_robot_file(file_name):
    return file_name.endswith('.txt')

