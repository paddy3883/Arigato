import os
import re
import sublime

from robot.api import TestCaseFile
from robot.parsing.populators import FromFilePopulator

views_to_center = {}

#-------------------------------------------------------------------------------------------
# This is a generic class that can be used to open a new window and display text in it.
#-------------------------------------------------------------------------------------------
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

#--------------------------------------------------------------------------
# The line of text at the current cursor position in the active window.
#--------------------------------------------------------------------------

class LineAtCursor():
    def __init__(self, view):
        self.view = view
        sel = view.sel()[0]
        self.line = re.compile('\r|\n').split(view.substr(view.line(sel)))[0]
        self.row, self.col = view.rowcol(sel.begin())

    # gets the keyword from the line
    def get_keyword(self):
        return get_keyword_at_pos(self.line, self.col)

def get_keyword_at_pos(line, col):
    length = len(line)

    if length == 0:
        return None

    # between spaces
    if ((col >= length or line[col] == ' ' or line[col] == '\t')
    and (col == 0 or line[col-1] == ' ' or line[col-1] == '\t')):
        return None

    # first look back until we find 2 spaces in a row, or reach the beginning
    i = col - 1
    while i >= 0:
        if line[i] == '\t' or ((line[i - 1] == ' ' or line[i - 1] == '|') and line[i] == ' '):
            break
        i -= 1
    begin = i + 1

    # now look forward or until the end
    i = col # previous included line[col]
    while i < length:
        if line[i] == '\t' or (line[i] == ' ' and len(line) > i and (line[i + 1] == ' ' or line[i + 1] == '|')):
            break
        i += 1
    end = i

    return line[begin:end]
