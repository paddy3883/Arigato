import os
import re
import sublime
import shutil
import tempfile

from robot_common import OutputWindow, LineAtCursor, is_robot_file

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
                
        self._search_within_folder(keyword)
        self.window.show_quick_panel(self.results_to_display, self._on_user_select, sublime.MONOSPACE_FONT)

    def _search_within_folder(self, phrase):
        for folder in self.view.window().folders():
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if is_robot_file(file):
                        self._search_within_file(root, file, phrase)

    def _search_within_file(self, root, file_name, phrase):
        file_path = os.path.join(root, file_name)
        try:
            with open(file_path, 'rb') as file:
                lines = file.readlines()
                line_number = 0
                for a_line in lines:
                    line_number = line_number + 1
                    try:
                        if phrase in str(a_line):
                            reference = ReferencedLine(a_line.strip(), str(file_name), file_path, line_number)
                            self.references.append(reference)
                            self.results_to_display.append(reference.to_display())

                    except Exception as exp:
                        print('Issue in file: ' + str(file_path) + ' line: ' + str(line_number) + ': ' + str(exp))

        except IOError as e:
            return
                
    def _on_user_select(self, index):
        if index != -1:
            new_view = self.window.open_file(self.references[index].link(), sublime.ENCODED_POSITION)
            self.window.focus_view(new_view)
            pt = new_view.text_point(self.references[index].line_number - 1, 0)
            new_view.sel().clear()
            new_view.sel().add(sublime.Region(pt))
            new_view.show(pt)

#------------------------------------------------------
# 
#------------------------------------------------------

class References1():

    def __init__(self, view, edit, plugin_dir):
        self.view = view
        self.edit = edit
        self.plugin_dir = plugin_dir

    def replace(self, file_path, pattern, subst):
        #Create temp file
        fh, abs_path = tempfile.mkstemp()
        new_file = open(abs_path,'w')
        old_file = open(file_path)
        for line in old_file:
            new_file.write(line.replace(pattern, subst))
        #close temp file
        new_file.close()
        os.close(fh)
        old_file.close()
        #Remove original file
        os.remove(file_path)
        #Move new file
        shutil.move(abs_path, file_path)

    def run(self, edit, oldKeyword, newKeyword):
                
        window = sublime.active_window()
        
        output_window = OutputWindow(window, self.plugin_dir, '*Find/Replace*')
        if output_window is not None:
            output_window.append_text('**************************************************************************************************************************\n')
            output_window.append_text('Commencing replace of \''+oldKeyword + ' with \'' +newKeyword +'\'\n')
            output_window.append_text('**************************************************************************************************************************\n\n\n')
        
        replaceCount = 0

        for folder in window.folders():
            #sublime.error_message('step2b')
            for root, dirs, files in os.walk(folder):
                #sublime.error_message('step2c')
                for f in files:
                    firstReplace = 1
                    #sublime.error_message('step2d')
                    if is_robot_file(f) and f != '__init__.txt':
                        path = os.path.join(root, f)
                        try:
                            with open(path, 'rb') as openFile:
                                lines = openFile.readlines()
                                line_number = 0 
                                for aLine in lines:
                                    line_number = line_number + 1
                                    try:
                                        if oldKeyword in str(aLine):
                                            #matchingKeyword= ReferencedLine(aLine.strip(),str(f),path, line_number)
                                            if output_window is not None:
                                                if firstReplace == 1:
                                                    output_window.append_text('In file \''+str(f) +'\'\n')
                                                    firstReplace = 0
                                                output_window.append_text('Line ' +str(line_number) + ' - Replacing ' + aLine.strip() + '\n\n')
                                                replaceCount = replaceCount+1
                                    except Exception as exp:
                                        print('Issue in file ' +str(f) + ' line number ' + str(line_number) + ': ' +exp.message)
                        except IOError as e:
                            return
                    
                        self.replace(path, oldKeyword, newKeyword)
                              
        if replaceCount>0:
            if output_window is not None:
                    output_window.append_text('\nTotal ' + str(replaceCount) + ' occurrences replaced')

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
