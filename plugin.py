#------------------------------------------------------
# Library imports and initializations
#------------------------------------------------------

# setup pythonpath to include lib directory before other imports
import os, sys

lib_path = os.path.normpath(os.path.join(os.getcwd(), 'lib'))
if lib_path not in sys.path:
    sys.path.append(lib_path)
pyd_path = os.path.dirname(sys.executable)
if pyd_path not in sys.path:
    sys.path.append(pyd_path)

# only available when the plugin is being loaded
plugin_dir = os.getcwd()

import threading
import re
import sublime
import sublime_plugin
import shutil
import tempfile

from keyword_parse import get_keyword_at_pos
from string_populator import populate_testcase_file
from robot_scanner import Scanner, detect_robot_regex
from robot_common import OutputWindow, is_robot_format
import stdlib_keywords
import robot_run
import robot_auto_completion

views_to_center = {}

stdlib_keywords.load(plugin_dir)

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
                    if f.endswith('.txt') and f != '__init__.txt':
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

        sublime.set_timeout(lambda: select_keyword_and_go(self.view, results), 0)

    def search_user_keywords(self, keywords, name):
        lower_name = name.lower()
        if not keywords.has_key(lower_name):
            return []
        return keywords[lower_name]

#------------------------------------------------------
# 
#------------------------------------------------------

def select_keyword_and_go(view, results):
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

#------------------------------------------------------
# 
#------------------------------------------------------

class MatchingFile:
    def __init__(self, lineText, fileName, filePath, lineNumber):
        self.lineText = lineText
        self.fileName = fileName
        self.filePath = filePath
        self.lineNumber = lineNumber

#------------------------------------------------------
# Find keyword references
#------------------------------------------------------

class RobotFindReferencesCommand(sublime_plugin.TextCommand):
    matchingLines = []
    window = None
        
    def run(self, edit):
        view = self.view

        if not is_robot_format(view):
            return

        sel = view.sel()[0]
        line = re.compile('\r|\n').split(view.substr(view.line(sel)))[0]
        row, col = view.rowcol(sel.begin())

        keyword = get_keyword_at_pos(line, col)
        
        if not keyword:
            sublime.error_message('No keyword detected')
            return	
                
        window = sublime.active_window()
      
        listItems = []
        matchingLines = []
        for folder in view.window().folders():
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.endswith('.txt') and f != '__init__.txt':
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
                                            matchingLines.append(matchingLine)
                                            listItems.append(matchingLine.fileName + ': #' + str(matchingLine.lineNumber) + ' - '+ matchingLine.lineText)
                                    except Exception as exp:
                                        print('Issue in file ' +str(f) + ' line number ' + str(lineNumber) + ': ' +exp.message)
                        except IOError as e:
                            return
        
        def on_done(i):
            newView = window.open_file(matchingLines[i].filePath + ':' + str(matchingLines[i].lineNumber), sublime.ENCODED_POSITION)
            window.focus_view(newView)
            pt = newView.text_point(matchingLines[i].lineNumber-1, 0)
            newView.sel().clear()
            newView.sel().add(sublime.Region(pt))
            newView.show(pt)

        window.show_quick_panel(listItems, on_done, sublime.MONOSPACE_FONT)

#------------------------------------------------------
# 
#------------------------------------------------------

class PromptRobotReplaceReferencesCommand(sublime_plugin.WindowCommand):
    currentKeyword = None 
    def run(self):
        view = sublime.active_window().active_view()

        if not is_robot_format(view):
            return

        sel = view.sel()[0]
        line = re.compile('\r|\n').split(view.substr(view.line(sel)))[0]
        row, col = view.rowcol(sel.begin())

        self.currentKeyword = get_keyword_at_pos(line, col)
        self.window.show_input_panel("Replace With:", "", self.on_done, None, None)
        pass

    def on_done(self, text):
        try:
            if self.window.active_view():
                self.window.active_view().run_command("robot_replace_references", {"oldKeyword":self.currentKeyword, "newKeyword": text} )
        except ValueError:
            pass

#------------------------------------------------------
# 
#------------------------------------------------------

class RobotReplaceReferencesCommand(sublime_plugin.TextCommand):

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
        
        output_window = OutputWindow(window, plugin_dir, '*Find/Replace*')
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
                    if f.endswith('.txt') and f != '__init__.txt':
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

class RightClickCommand(sublime_plugin.TextCommand):
	def run_(self, args):
		self.view.run_command("context_menu", args)
#self.view.run_command("move_to", {"to":"bof"})

#sel = self.view.sel()[0]
#line = re.compile('\r|\n').split(view.substr(view.line(sel)))[0]
#row, col = view.rowcol(sel.begin())

#------------------------------------------------------
# 
#------------------------------------------------------

class DragSelectCallbackCommand(sublime_plugin.TextCommand):
	def run_(self, args):                
		for c in sublime_plugin.all_callbacks.setdefault('on_pre_mouse_down',[]):
			c.on_pre_mouse_down(args)

        #We have to make a copy of the selection, otherwise we'll just have
		#a *reference* to the selection which is useless if we're trying to
		#roll back to a previous one. A RegionSet doesn't support slicing so
		#we have a comprehension instead.
		old_sel = [r for r in self.view.sel()]

		#Only send the event so we don't do an extend or subtract or
		#whatever. We want the only selection to be where they clicked.
		self.view.run_command("drag_select", {'event': args['event']})
		new_sel = self.view.sel()
		click_point = new_sel[0].a

		#Restore the old selection so when we call drag_select it will
		#behave normally.
		new_sel.clear()
		map(new_sel.add, old_sel)

		#This is the "real" drag_select that alters the selection for real.
		self.view.run_command("drag_select", args)

		for c in sublime_plugin.all_callbacks.setdefault('on_post_mouse_down',[]):
			c.on_post_mouse_down(click_point)

#------------------------------------------------------
# 
#------------------------------------------------------

class MouseEventListener(sublime_plugin.EventListener):
	#If we add the callback names to the list of all callbacks, Sublime
	#Text will automatically search for them in future imported classes.
	#You don't actually *need* to inherit from MouseEventListener, but
	#doing so forces you to import this file and therefore forces Sublime
	#to add these to its callback list.
	sublime_plugin.all_callbacks.setdefault('on_pre_mouse_down', [])
	sublime_plugin.all_callbacks.setdefault('on_post_mouse_down', [])

#------------------------------------------------------
# 
#------------------------------------------------------

class RobotGoToKeywordCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        if not is_robot_format(view):
            return

        sel = view.sel()[0]
        line = re.compile('\r|\n').split(view.substr(view.line(sel)))[0]
        row, col = view.rowcol(sel.begin())

        file_path = view.file_name()
        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return
        path, file_name = os.path.split(file_path)

        if line.strip().startswith('Resource'):
            resource = line[line.find('Resource') + 8:].strip().replace('${CURDIR}', path)
            resource_path = os.path.join(path, resource)
            view.window().open_file(resource_path)
            return

        keyword = get_keyword_at_pos(line, col)
        if not keyword:
            return

        view_file = populate_testcase_file(self.view)
        # must be run on main thread
        folders = view.window().folders()
        GoToKeywordThread(view, view_file, keyword, folders).start()

#------------------------------------------------------
# 
#------------------------------------------------------

class AutoSyntaxHighlight(sublime_plugin.EventListener):
    def autodetect(self, view):
        # file name can be None if it's a find result view that is restored on startup
        if (view.file_name() != None and view.file_name().endswith('.txt') and
            view.find(detect_robot_regex, 0, sublime.IGNORECASE) != None):

            view.set_syntax_file(os.path.join(plugin_dir, "robot.tmLanguage"))

    def on_load(self, view):
        if view.id() in views_to_center:
            view.show_at_center(view.text_point(views_to_center[view.id()], 0))
            del views_to_center[view.id()]
        self.autodetect(view)

    def on_post_save(self, view):
        self.autodetect(view)

#------------------------------------------------------
# 
#------------------------------------------------------

class AutoComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if is_robot_format(view):
            view_file = populate_testcase_file(view)
            keywords = Scanner(view).scan_file(view_file)
            lower_prefix = prefix.lower()
            user_keywords = [(kw[0].keyword.name, kw[0].keyword.name) for kw in keywords.itervalues()
                                if kw[0].keyword.name.lower().startswith(lower_prefix)]
            return user_keywords

#====================================================================================================
# Classes used for running robot tests.
#====================================================================================================

#----------------------------------------------------------
# Sublime context menu command: Run test
#----------------------------------------------------------
class RobotRunTestCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not is_robot_format(self.view):
            return

        test_case = robot_run.RobotTestCase(self.view, plugin_dir)
        test_case.execute()

#----------------------------------------------------------
# Sublime context menu command: Run test suite
#----------------------------------------------------------
class RobotRunTestSuiteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not is_robot_format(self.view):
            return

        test_suite = robot_run.RobotTestSuite(self.view, plugin_dir)
        test_suite.execute()

#----------------------------------------------------------
# Sublime context menu command: Run...
#----------------------------------------------------------
class RobotRunPanelCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not is_robot_format(self.view):
            return

        file_path = self.view.file_name()

        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return

        path, file_name = os.path.split(file_path)

        sublime.error_message('Run panel is not yet implemented')

#------------------------------------------------------------------------------------
# Sublime menu command: Preferences -> Package Settings -> Arigato -> Run options
#------------------------------------------------------------------------------------
class RobotRunOptionsCommand(sublime_plugin.WindowCommand):
    def run(self):

        current_folder = sublime.active_window().folders()[0]
        sublime.active_window().open_file(os.path.join(current_folder, 'robot.sublime-build'))

#====================================================================================================
# Classes used for auto completion.
#====================================================================================================

#----------------------------------------------------------
# Mapped key: ${{ For auto completion of variable names.
#----------------------------------------------------------

class RobotCompleteVariableCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        search = robot_auto_completion.Search(self.view, edit, plugin_dir)
        search.auto_complete_variable()

#------------------------------------------------------
# Mapped key: @{{ For auto completion of list names.
#------------------------------------------------------

class RobotCompleteListCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        search = robot_auto_completion.Search(self.view, edit, plugin_dir)
        search.auto_complete_list()

