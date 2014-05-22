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

import re
import sublime
import sublime_plugin

from robot_scanner import Scanner, detect_robot_regex
from robot_common import OutputWindow, RobotTestCaseFile, LineAtCursor, is_robot_format, is_robot_file, views_to_center
from robot_definitions import GoToKeywordThread
from robot_references import FindReferencesService

import robot_run
import robot_auto_completion
import stdlib_keywords

stdlib_keywords.load(plugin_dir)

#====================================================================================================
# Classes used for finding the definition of a keyword.
#   Note: See lib/robot_definitions.py for detailed implementation.
#====================================================================================================
#------------------------------------------------------
# Sublime context menu command: Go to definition
#------------------------------------------------------

class RobotGoToKeywordCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        if not is_robot_format(view):
            return

        file_path = view.file_name()
        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return
        path, file_name = os.path.split(file_path)

        line_at_cursor = LineAtCursor(view)
        keyword = line_at_cursor.get_keyword()
        line = line_at_cursor.line

        if not keyword:
            return

        if line.strip().startswith('Resource'):
            resource = line[line.find('Resource') + 8:].strip().replace('${CURDIR}', path)
            resource_path = os.path.join(path, resource)
            view.window().open_file(resource_path)
            return

        view_file = RobotTestCaseFile(self.view).file

        # must be run on main thread
        folders = view.window().folders()
        GoToKeywordThread(view, view_file, keyword, folders).start()

#====================================================================================================
# Classes used for running robot tests.
#   Note: See lib/robot_run.py for detailed implementation.
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
#   Note: See lib/robot_auto_completion.py for detailed implementation.
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

#====================================================================================================
# Event listeners
#====================================================================================================

#------------------------------------------------------
# Highlight robot framework syntax.
#------------------------------------------------------

class AutoSyntaxHighlight(sublime_plugin.EventListener):
    def on_load(self, view):
        if view.id() in views_to_center:
            view.show_at_center(view.text_point(views_to_center[view.id()], 0))
            del views_to_center[view.id()]
        self._autodetect(view)

    def on_post_save(self, view):
        self._autodetect(view)

    def _autodetect(self, view):
        # file name can be None if it's a find result view that is restored on startup
        if (view.file_name() != None and is_robot_file(view.file_name()) and
            view.find(detect_robot_regex, 0, sublime.IGNORECASE) != None):

            view.set_syntax_file(os.path.join(plugin_dir, 'robot.tmLanguage'))

#------------------------------------------------------
# Auto completion of keywords.
#------------------------------------------------------

class AutoComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if is_robot_format(view):
            view_file = RobotTestCaseFile(view).file
            keywords = Scanner(view).scan_file(view_file)
            lower_prefix = prefix.lower()
            user_keywords = [(kw[0].keyword.name, kw[0].keyword.name) for kw in keywords.itervalues()
                                if kw[0].keyword.name.lower().startswith(lower_prefix)]
            return user_keywords

#------------------------------------------------------
# Right click command.
#------------------------------------------------------

class RightClickCommand(sublime_plugin.TextCommand):
	def run_(self, args):
		self.view.run_command("context_menu", args)

#====================================================================================================
# Classes used for find/replace references.
#   Note: See lib/robot_references.py for detailed implementation.
#====================================================================================================

#------------------------------------------------------
# # Sublime context menu command: Find references
#------------------------------------------------------

class RobotFindReferencesCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not is_robot_format(self.view):
            return

        references = FindReferencesService(self.view, edit, plugin_dir)
        references.find()

#-----------------------------------------------------------
# Sublime context menu command: Prompt Replace references
#-----------------------------------------------------------

class PromptRobotReplaceReferencesCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = sublime.active_window().active_view()

        if not is_robot_format(view):
            return

        self.currentKeyword = LineAtCursor(view).get_keyword()
        self.window.show_input_panel('Replace "' + self.currentKeyword + '" with: ', self.currentKeyword, self._on_done, None, None)
        pass

    def _on_done(self, text):
        try:
            if self.window.active_view():
                self.window.active_view().run_command('robot_replace_references', {'old_keyword': self.currentKeyword, 'new_keyword': text} )
        except ValueError:
            pass

#------------------------------------------------------
# Sublime context menu command: Replace references
#------------------------------------------------------

class RobotReplaceReferencesCommand(sublime_plugin.TextCommand):
    def run(self, edit, old_keyword, new_keyword):
        references = FindReferencesService(self.view, edit, plugin_dir)
        references.replace(edit, old_keyword, new_keyword)

#====================================================================================================
# Experimental Stuff...
#====================================================================================================

#-------------------------------------------------------------------------------
# TODO: (POC) Add mouse event listener to capture the mouse cursor position. 
#-------------------------------------------------------------------------------

class MouseEventListener(sublime_plugin.EventListener):
	#If we add the callback names to the list of all callbacks, Sublime
	#Text will automatically search for them in future imported classes.
	#You don't actually *need* to inherit from MouseEventListener, but
	#doing so forces you to import this file and therefore forces Sublime
	#to add these to its callback list.
	sublime_plugin.all_callbacks.setdefault('on_pre_mouse_down', [])
	sublime_plugin.all_callbacks.setdefault('on_post_mouse_down', [])

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
		self.view.run_command('drag_select', {'event': args['event']})
		new_sel = self.view.sel()
		click_point = new_sel[0].a

		#Restore the old selection so when we call drag_select it will
		#behave normally.
		new_sel.clear()
		map(new_sel.add, old_sel)

		#This is the 'real' drag_select that alters the selection for real.
		self.view.run_command('drag_select', args)

		for c in sublime_plugin.all_callbacks.setdefault('on_post_mouse_down',[]):
			c.on_post_mouse_down(click_point)

