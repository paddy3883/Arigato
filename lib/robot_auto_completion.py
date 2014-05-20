import os
import sublime

#-------------------------------------------------------------------------
# Global lists containing all known variable names and list names
#-------------------------------------------------------------------------

known_variables = []
known_lists = []

#-------------------------------------------------------------------------
# Class to handle auto completion of variable names and list names.
#-------------------------------------------------------------------------

class Search(object):
    def __init__(self, view, edit, plugin_dir):
        self.view = view
        self.edit = edit
        self.plugin_dir = plugin_dir
        self.window = sublime.active_window()
        self._search_within_folders(view.window().folders())

    def _search_within_folders(self, folders):
        for folder in folders:
            print 'searching folder for variables: ' + folder
            for root, dirs, files in os.walk(folder):
                for file_name in files:
                    if file_name.endswith('.txt'):
                        file_path = os.path.join(root, file_name)
                        print 'searching file for variables: ' + file_path
                        self._search_within_file(file_path)

    def _search_within_file(self, file_path):
        known_variables.append(file_path)
        return
        pattern = re.compile('\s*\\$\\{\w+\\}')
        try:
           with open(file_path, 'rb') as openFile:
                lines = openFile.readlines()
                for line in lines:
                     # search if line contains string
                     m = pattern.match(line)
                     if m:
                        itemfound=m.group(0).strip()
                        itemfound = re.sub('[${}]', '', itemfound)
                        if itemfound not in self.dollar_variables:
                            self.dollar_variables.append(itemfound)
        except IOError as e:
           return

    def auto_complete_variable(self):
        # display a panel containing a list of known variables and let the user chose.
        self.window.show_quick_panel(known_variables, self._on_user_selection_of_variable)

        # replace the user typed ${{ with just ${
        self._insert_text("${")
        self.curPos = self.view.sel()[0].begin()

    def auto_complete_list(self):
        # display a panel containing a list of known lists and let the user chose.
        self.window.show_quick_panel(known_lists, self._on_user_selection_of_list)

        # replace the user typed @{{ with just @{
        self._insert_text("@{")
        self.curPos = self.view.sel()[0].begin()

    def _on_user_selection_of_variable(self, index):
        if index != -1:
            self._insert_text(known_variables[index] + "}    ")

    def _on_user_selection_of_list(self, index):
        if index != -1:
            self._insert_text(known_lists[index] + "}    ")

    def _insert_text(self, text):
        self.view.insert(self.edit, self.view.sel()[0].begin(), text)

#------------------------------------------------------
# Class to handle auto completing list names.
#------------------------------------------------------

class CompleteList(object):
    def search_list_variables(self, path):
        pattern = '\s*@\\{\w+\\}'
        p = re.compile(pattern)
        try:
           with open(path, 'rb') as openFile:
             lines = openFile.readlines()
             for line in lines:
                 # search if line contains string
                 m = p.match(line)
                 if m:
                     itemfound=m.group(0).strip()
                     itemfound = re.sub('[@{}]', '', itemfound)
                     if itemfound not in self.list_variables:
                        self.list_variables.append(itemfound)
        except IOError as e:
           return        
           
