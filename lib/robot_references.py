import os
import re
import sublime
import shutil
import tempfile

from robot_common import OutputWindow, LineAtCursor, is_robot_file, get_keyword_at_pos

#------------------------------------------------------
# Class that is used to find/replace keyword references.
#------------------------------------------------------

class FindReferencesService():
    def __init__(self, view, edit, plugin_dir):
        self.view = view
        self.edit = edit
        self.plugin_dir = plugin_dir
        self.window = sublime.active_window()
        self.results_to_display = []
        self.references = []
      
    def find(self):
        keyword = LineAtCursor(self.view).get_keyword()
        
        if not keyword:
            sublime.error_message('No keyword detected')
            return	
                
        self._search_within_folder(keyword, self._find_callback)
        self.window.show_quick_panel(self.results_to_display, self._on_user_select, sublime.MONOSPACE_FONT)

    def replace(self, edit, old_keyword, new_keyword):
        self.output_window = OutputWindow(self.window, self.plugin_dir, '*Find/Replace References*')
        if self.output_window is None:
            sublime.error_message('Cannot open a window to display the output. The command quits. No replacings will be made.')
            return

        self.old_keyword = old_keyword
        self.new_keyword = new_keyword
        self.replacement_count = 0
        self.previous_file_path = ''

        self._display_find_and_replace_window_header(self.output_window)
        self._search_within_folder(old_keyword, self._replace_callback)

        if self.replacement_count > 0:
            self.output_window.append_text('\nTotal of ' + str(self.replacement_count) + ' occurrences replaced')
                              
    def _search_within_folder(self, phrase, callback):
        for folder in self.window.folders():
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if is_robot_file(file):
                        self._search_within_file(root, file, phrase, callback)

    def _search_within_file(self, root, file_name, phrase, callback):
        file_path = os.path.join(root, file_name)
        try:
            with open(file_path, 'rb') as file:
                lines = file.readlines()
                line_number = 0
                for a_line in lines:
                    line_number = line_number + 1
                    try:
                        if phrase in str(a_line):
                            # now we know that the phrase is inside the line, but is it really a keyword, let's see...
                            occurrance = get_keyword_at_pos(a_line, a_line.index(phrase) + 1)
                            if occurrance == phrase:
                                reference = ReferencedLine(a_line.strip(), str(file_name), file_path, line_number)
                                callback(reference)

                    except Exception as exp:
                        print('Error in file: ' + str(file_path) + '(' + str(line_number) + '): ' + str(exp))

        except IOError as e:
            return

    def _find_callback(self, reference):
        self.references.append(reference)
        self.results_to_display.append(reference.to_display())

    def _on_user_select(self, index):
        if index != -1:
            new_view = self.window.open_file(self.references[index].link(), sublime.ENCODED_POSITION)
            self.window.focus_view(new_view)
            pt = new_view.text_point(self.references[index].line_number - 1, 0)
            new_view.sel().clear()
            new_view.sel().add(sublime.Region(pt))
            new_view.show(pt)

    def _display_find_and_replace_window_header(self, window):
        title = 'Replacing "' + self.old_keyword + '" with "' + self.new_keyword +'"\n'
        window.append_text('-' * (len(title) + 8) + '\n')
        window.append_text(' ' * 4 + title)
        window.append_text('-' * (len(title) + 8) + '\n\n\n')

    def _replace_callback(self, reference):
        # if this is reference in a new file...
        if self.previous_file_path != reference.file_path:
            if self.previous_file_path != '':
                self._replace_all_references_in_file(self.previous_file_path)
            self.output_window.append_text('In file "' + str(reference.file_path) + '":\n')

        self.previous_file_path = reference.file_path
        self.output_window.append_text('  Replacing the keyword in line (' + str(reference.line_number) + '): ' + reference.line_text.strip() + '\n\n')
        self.replacement_count = self.replacement_count + 1
                
    def _replace_all_references_in_file(self, file_path):
        # create a temporary file
        fh, abs_path = tempfile.mkstemp()
        new_file = open(abs_path, 'w')
        old_file = open(file_path)
        for line in old_file:
            new_file.write(line.replace(self.old_keyword, self.new_keyword))

        # close temp file
        new_file.close()
        os.close(fh)
        old_file.close()

        # remove original file
        os.remove(file_path)

        # move new file
        shutil.move(abs_path, file_path)

#----------------------------------------------------------------
# Represents a single reference to a phrase (keyword/variable)
#----------------------------------------------------------------

class ReferencedLine:
    def __init__(self, line_text, file_name, file_path, line_number):
        self.line_text = line_text
        self.file_name = file_name
        self.file_path = file_path
        self.line_number = line_number

    def to_display(self):
        return self.file_path + '(' + str(self.line_number) + '): '+ self.line_text

    def link(self):
        return self.file_path + ':' + str(self.line_number)
