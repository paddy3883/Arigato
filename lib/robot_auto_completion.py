import os
import re
import sublime
from robot_common import is_robot_file 

#-------------------------------------------------------------------------
# Class to handle auto completion of variable names and list names.
#-------------------------------------------------------------------------

class Search(object):
    def __init__(self, view, edit, plugin_dir):
        self.view = view
        self.edit = edit
        self.plugin_dir = plugin_dir
        self.window = sublime.active_window()
        self.variable_pattern = re.compile('\s*\\$\\{\w+\\}')
        self.list_pattern = re.compile('\s*@\\{\w+\\}')
        self.known_variables = []
        self.known_lists = []

        self._search_within_folders(view.window().folders())

    def _search_within_folders(self, folders):
        for folder in folders:
            #print 'searching folder for variables: ' + folder
            for root, dirs, files in os.walk(folder):
                for file_name in files:
                    if is_robot_file(file_name):
                        file_path = os.path.join(root, file_name)
                        #print 'searching file for variables: ' + file_path
                        self._search_within_file(file_path)

    def _search_within_file(self, file_path):

        try:
           with open(file_path, 'rb') as openFile:

                lines = openFile.readlines()
                inside_variable_block = False

                for line in lines:
                    # Any line that starts with '***' marks start of a new code block in Robot.
                    if line.startswith('***'):
                        # we know that all variables must follow *** Variables ***
                        inside_variable_block = line.startswith('*** Variables ***')
                        continue

                    if inside_variable_block:
                        self._search_within_line(line)

        except IOError as e:
           return

    def _search_within_line(self, line):
        match = self.variable_pattern.match(line)
        if match:
            variable_name = re.sub('[${}]', '', match.group(0).strip())
            if variable_name not in self.known_variables:
                self.known_variables.append(variable_name)

        match = self.list_pattern.match(line)
        if match:
            list_name = re.sub('[@{}]', '', match.group(0).strip())
            if list_name not in self.known_lists:
                self.known_lists.append(list_name)

    def auto_complete_variable(self):
        # display a panel containing a list of known variables and let the user chose.
        self.window.show_quick_panel(self.known_variables, self._on_user_selection_of_variable)

        # replace the user typed ${{ with just ${
        self._insert_text('${')
        self.curPos = self.view.sel()[0].begin()

    def auto_complete_list(self):
        # display a panel containing a list of known lists and let the user chose.
        self.window.show_quick_panel(self.known_lists, self._on_user_selection_of_list)

        # replace the user typed @{{ with just @{
        self._insert_text('@{')
        self.curPos = self.view.sel()[0].begin()

    def _on_user_selection_of_variable(self, index):
        if index != -1:
            self._insert_text(self.known_variables[index] + '}    ')

    def _on_user_selection_of_list(self, index):
        if index != -1:
            self._insert_text(self.known_lists[index] + '}    ')

    def _insert_text(self, text):
        self.view.insert(self.edit, self.view.sel()[0].begin(), text)

