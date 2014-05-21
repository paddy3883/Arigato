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

    def find(self):
        view = self.view
        keyword = LineAtCursor(view).get_keyword()
        
        if not keyword:
            sublime.error_message('No keyword detected')
            return	
                
        self.window = sublime.active_window()
      
        listItems = []
        self.matchingLines = []
        for folder in view.window().folders():
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if is_robot_file(f) and f != '__init__.txt':
                        path = os.path.join(root, f)
                        try:
                            with open(path, 'rb') as openFile:
                                lines = openFile.readlines()
                                lineNumber = 0 
                                for aLine in lines:
                                    lineNumber = lineNumber + 1
                                    try:
                                        if keyword in str(aLine):
                                            matchingLine= MatchingFile(aLine.strip(),str(f),path, lineNumber)
                                            self.matchingLines.append(matchingLine)
                                            listItems.append(matchingLine.fileName + ': #' + str(matchingLine.lineNumber) + ' - '+ matchingLine.lineText)
                                    except Exception as exp:
                                        print('Issue in file ' +str(f) + ' line number ' + str(lineNumber) + ': ' +exp.message)
                        except IOError as e:
                            return
        
        def on_done(i):
            newView = self.window.open_file(self.matchingLines[i].filePath + ':' + str(self.matchingLines[i].lineNumber), sublime.ENCODED_POSITION)
            self.window.focus_view(newView)
            pt = newView.text_point(self.matchingLines[i].lineNumber-1, 0)
            newView.sel().clear()
            newView.sel().add(sublime.Region(pt))
            newView.show(pt)

        self.window.show_quick_panel(listItems, on_done, sublime.MONOSPACE_FONT)

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
                                lineNumber = 0 
                                for aLine in lines:
                                    lineNumber = lineNumber + 1
                                    try:
                                        if oldKeyword in str(aLine):
                                            #matchingKeyword= MatchingFile(aLine.strip(),str(f),path, lineNumber)
                                            if output_window is not None:
                                                if firstReplace == 1:
                                                    output_window.append_text('In file \''+str(f) +'\'\n')
                                                    firstReplace = 0
                                                output_window.append_text('Line ' +str(lineNumber) + ' - Replacing ' + aLine.strip() + '\n\n')
                                                replaceCount = replaceCount+1
                                    except Exception as exp:
                                        print('Issue in file ' +str(f) + ' line number ' + str(lineNumber) + ': ' +exp.message)
                        except IOError as e:
                            return
                    
                        self.replace(path, oldKeyword, newKeyword)
                              
        if replaceCount>0:
            if output_window is not None:
                    output_window.append_text('\nTotal ' + str(replaceCount) + ' occurrences replaced')

#------------------------------------------------------
# 
#------------------------------------------------------

class MatchingFile:
    def __init__(self, lineText, fileName, filePath, lineNumber):
        self.lineText = lineText
        self.fileName = fileName
        self.filePath = filePath
        self.lineNumber = lineNumber

