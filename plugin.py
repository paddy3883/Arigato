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

import sublime, sublime_plugin
import shlex
import subprocess
import select
import functools
import json

from keyword_parse import get_keyword_at_pos
from string_populator import populate_testcase_file
from robot_scanner import Scanner, detect_robot_regex
import stdlib_keywords
import webbrowser

from os.path import dirname, realpath

from tempfile import mkstemp
from shutil import move
from os import remove, close
views_to_center = {}

stdlib_keywords.load(plugin_dir)

class CompleteVariableCommand(sublime_plugin.TextCommand):
    matching_variables = []

    def run(self, edit):
        view = self.view

        # test data for demo. the list would be populated using already-written folder search function at bottom of this class which would be pre-populated on load
        self.list = ["WorkingFolderVariable", "HomeworkFolderbbc", "FileNameVariable", "HomeworkFileName", "PathToVariable", "PathToHomeworkVariable", "CountFiles", "CountHtmlLogFiles", "CountHtmlReportFiles"]

        window = sublime.active_window()
        window.show_quick_panel(self.list, self.on_done)
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':"${"}})
        self.curPos = self.view.sel()[0].begin()

    def on_done(self, index):
        if index == -1:
            return           
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':self.list[index]+"}    "}})

class CompleteListCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        # test data for demo. the list would be populated using already-written folder search function at bottom of this class which would be pre-populated on load
        self.list = ["CounterList", "PathList", "FilesList", "SearchFiles"]

        window = sublime.active_window()
        window.show_quick_panel(self.list, self.on_done)
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':"@{"}})
        self.curPos = self.view.sel()[0].begin()

    def on_done(self, index):
        if index == -1:
            return           
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':self.list[index]+"}    "}})

class InsertMyText(sublime_plugin.TextCommand):
    def run(self, edit, args):
        self.view.insert(edit, args['startPos'], args['text'])


#TODO: move this into robot_run.py
class RobotTestSuite(object):

    def __init__(self, view):
        self.view = view

    def execute(self):
        view = self.view
        file_path = self.view.file_name()

        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return
        
        test = Test(self.view)
        test.run_test_suite()

        return True

#TODO: move this into robot_run.py
class RobotTestCase(object):

    def __init__(self, view):
        self.view = view

    def execute(self):
        view = self.view
        file_path = view.file_name()

        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return

        #TODO: this returns the keyword at cursor position, but we need to get the keyword at mouse position.
        sel = view.sel()[0]
        test_case = re.compile('\r|\n').split(view.substr(view.line(sel)))[0]

        if (len(test_case) == 0) or (test_case[0] == " ") or (test_case[0] == "\t"):
            return

        test_case = test_case.replace(" ", "").replace("\t", "")

        test = Test(self.view)
        test.run_test_case(test_case)

        return True

def is_robot_format(view):
    return view.settings().get('syntax').endswith('robot.tmLanguage')

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

class RobotRunTestCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        if not is_robot_format(view):
            return

        test_case = RobotTestCase(view)
        test_case.execute()


class RobotRunTestSuiteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        if not is_robot_format(view):
            return

        test_suite = RobotTestSuite(view)
        test_suite.execute()


class RobotRunPanelCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        if not is_robot_format(view):
            return

        file_path = view.file_name()

        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return

        path, file_name = os.path.split(file_path)

        sublime.error_message('Run panel is not yet implemented')

class MatchingFile:
    def __init__(self, lineText, fileName, filePath, lineNumber):
        self.lineText = lineText
        self.fileName = fileName
        self.filePath = filePath
        self.lineNumber = lineNumber

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
            newView = window.open_file(matchingLines[i].filePath)
            window.focus_view(newView)
            pt = newView.text_point(matchingLines[i].lineNumber-1, 0)
            newView.sel().clear()
            newView.sel().add(sublime.Region(pt))
            newView.show(pt)

        window.show_quick_panel(listItems, on_done, sublime.MONOSPACE_FONT)
      


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

class RobotReplaceReferencesCommand(sublime_plugin.TextCommand):

    def replace(self, file_path, pattern, subst):
        #Create temp file
        fh, abs_path = mkstemp()
        new_file = open(abs_path,'w')
        old_file = open(file_path)
        for line in old_file:
            new_file.write(line.replace(pattern, subst))
        #close temp file
        new_file.close()
        close(fh)
        old_file.close()
        #Remove original file
        remove(file_path)
        #Move new file
        move(abs_path, file_path)

    def run(self, edit, oldKeyword, newKeyword):
                
        window = sublime.active_window()
        
        output_target = OutputTarget(window,window.folders()[0], '*Find/Replace*')
        if output_target is not None:
            output_target.append_text('**************************************************************************************************************************\n')
            output_target.append_text('Commencing replace of \''+oldKeyword + ' with \'' +newKeyword +'\'\n')
            output_target.append_text('**************************************************************************************************************************\n\n\n')
        
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
                                            if output_target is not None:
                                                if firstReplace == 1:
                                                    output_target.append_text('In file \''+str(f) +'\'\n')
                                                    firstReplace = 0
                                                output_target.append_text('Line ' +str(lineNumber) + ' - Replacing ' + aLine.strip() + '\n\n')
                                                replaceCount = replaceCount+1
                                    except Exception as exp:
                                        print('Issue in file ' +str(f) + ' line number ' + str(lineNumber) + ': ' +exp.message)
                        except IOError as e:
                            return
                    
                        self.replace(path, oldKeyword, newKeyword)
                              
        if replaceCount>0:
            if output_target is not None:
                    output_target.append_text('\nTotal ' + str(replaceCount) + ' occurrences replaced')
                                       

class RightClickCommand(sublime_plugin.TextCommand):
	def run_(self, args):
		self.view.run_command("context_menu", args)
        #self.view.run_command("move_to", {"to":"bof"})
        
        #sel = self.view.sel()[0]
        #line = re.compile('\r|\n').split(view.substr(view.line(sel)))[0]
        #row, col = view.rowcol(sel.begin())


        

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

class MouseEventListener(sublime_plugin.EventListener):
	#If we add the callback names to the list of all callbacks, Sublime
	#Text will automatically search for them in future imported classes.
	#You don't actually *need* to inherit from MouseEventListener, but
	#doing so forces you to import this file and therefore forces Sublime
	#to add these to its callback list.
	sublime_plugin.all_callbacks.setdefault('on_pre_mouse_down', [])
	sublime_plugin.all_callbacks.setdefault('on_post_mouse_down', [])



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


class AutoComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if is_robot_format(view):
            view_file = populate_testcase_file(view)
            keywords = Scanner(view).scan_file(view_file)
            lower_prefix = prefix.lower()
            user_keywords = [(kw[0].keyword.name, kw[0].keyword.name) for kw in keywords.itervalues()
                                if kw[0].keyword.name.lower().startswith(lower_prefix)]
            return user_keywords

class OutputTarget():
    def __init__(self, window, working_dir, name):

        self.console = window.new_file()
        self.console.set_name(name)

        self.console.set_scratch(True)
        self.console.set_read_only(True)
        self.console.set_syntax_file(os.path.join(plugin_dir, 'robot-output.tmLanguage'))

    def append_text(self, output):

        console = self.console

        console.set_read_only(False)
        edit = console.begin_edit()
        console.insert(edit, console.size(), output)
        console.end_edit(edit)
        console.set_read_only(True)

    def set_status(self, tag, message):

        self.console.set_status(tag, message)

def process(command, callback, working_dir, results_dir):

    thread = threading.Thread(target=_process, kwargs={
        'command': command,
        'callback': callback,
        'working_dir': working_dir,
        'results_dir': results_dir
    })
    thread.start()

def _process(command, callback, working_dir, results_dir, **kwargs):
    startupinfo = None
    test_run_failed = False
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:

        main_thread(callback, command + '\n\n')
        proc = subprocess.Popen(command,
                                stdin=subprocess.PIPE,
                                universal_newlines=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                shell=True,
                                cwd=working_dir,
                                startupinfo=startupinfo)

        return_code = None
        while return_code is None:
            return_code = proc.poll()

            if return_code is None or return_code == 0:

                output = True
                while output:
                    output = proc.stdout.readline()
                    main_thread(callback, output, **kwargs)

            if  return_code == 1:
                test_run_failed = True
                main_thread(callback, '\nTest execution is complete, but there are test failures!', **kwargs)

                output_file_name = results_dir + '/log.html'
                if os.path.isfile(output_file_name):
                    webbrowser.open_new('file://' + output_file_name)

    except subprocess.CalledProcessError as e:

        main_thread(callback, e.returncode)

    except OSError as e:

        if e.errno == 2:
            sublime.message_dialog('Command not found\n\nCommand is: %s' % command)
        else:
            raise e

    if not test_run_failed:
        main_thread(callback, '\nTest execution is complete and all tests passed!', **kwargs)

def main_thread(callback, *args, **kwargs):

    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)
    #sublime.set_timeout_async(functools.partial(callback, *args, **kwargs), 0)

class Test():

    def __init__(self, view):
        self.view = view;
        path, self.file_name = os.path.split(view.file_name())
        self.root_folder = view.window().folders()[0]
        self.suite_name = self.file_name.rstrip('.txt')

        # Default values
        self.outputdir = 'TestResults'
        self.testsuites = 'testsuites'
        self.variables = ["os_browser:gc", "environment_name:cp"]

        settings_file_name = os.path.join(self.root_folder, 'robot.sublime-build')

        if os.path.isfile(settings_file_name):
            json_data = open(settings_file_name)
            data = json.load(json_data)
            json_data.close()

            if len(data["testsuites"]) > 0:
                self.testsuites = data["testsuites"]

            if len(data["outputdir"]) > 0:
                self.outputdir = data["outputdir"]

            self.variables = data["variables"]

        self.results_dir = os.path.join(self.root_folder, self.outputdir)
        self.testsuites = os.path.join(self.root_folder, self.testsuites)
        
        self.variable_line = ' '
        for variable in self.variables:
            self.variable_line += '--variable ' + variable + ' '

    def run_test_suite(self):
        output_target = OutputTarget(self.view.window(), self.root_folder, '*Output*')

        def _C(output):
            if output is not None:
                output_target.append_text(output)

        process('pybot --outputdir ' + self.results_dir + self.variable_line + '--suite ' + self.suite_name + ' ' + self.testsuites, _C, self.root_folder, self.results_dir)

    def run_test_case(self, test_case):
        output_target = OutputTarget(self.view.window(), self.root_folder, '*Output*')

        def _C(output):
            if output is not None:
                output_target.append_text(output)

        process('pybot --outputdir ' + self.results_dir + self.variable_line + '--test ' + test_case + ' ' + self.testsuites, _C, self.root_folder, self.results_dir)

class RobotRunOptionsCommand(sublime_plugin.WindowCommand):
    def run(self):

        current_folder = sublime.active_window().folders()[0]
        sublime.active_window().open_file(os.path.join(current_folder, 'robot.sublime-build'))

#code to populate variables from folders
class RobotCompleteListVariableCommand(sublime_plugin.TextCommand):
    
    matching_list_variables = []
    

    def run(self, edit):
        view = self.view
        
        if not is_robot_format(view):
            return
        
        file_path = view.file_name()        
        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return 
        
        window = sublime.active_window()
        folders = view.window().folders()
        
        for folder in folders:
            print ('searching folders') 
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.endswith('.txt') and f != '__init__.txt':
                        path = os.path.join(root, f) 
                        self.search_list_variables(path)
                        print ('searching files')         
                    
        window.run_command("hide_overlay")
        self.matching_list_variables.append('stringitems')
        self.matching_list_variables.append('dataserviceitems')
        window.show_quick_panel(self.matching_list_variables, None)
        
                        
    def search_list_variables(self, path):
            robotfile=open(path, 'r')        
            for line in robotfile:
                print ('searching file line : ' + line)
                # search if line contains string
                pattern = '^\\@\\{\w+\\}'
                p = re.compile(pattern)
                m = p.match(line)
                if m:
                    print ('Match found: ', m.group())
                    print ('Match found group zero: ', m.group(0))
                    itemfound=m.group(0)
                    for char in '${}':
                        itemfound=itemfound.replace(char,'')  
                    self.matching_list_variables.append(itemfound)
                else:
                    print 'No match'

#code to populate variables from folders
class RobotCompleteVariableCommand(sublime_plugin.TextCommand):
    
   matching_variables = []
 
   def run(self, edit):
        view = self.view 
        if not is_robot_format(view):
            return
        
        file_path = view.file_name()        
        if not file_path:
            sublime.error_message('Please save the buffer to a file first.')
            return 

        window = sublime.active_window()
        folders = view.window().folders()
        
        for folder in folders:
            print ('searching folders') 
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.endswith('.txt') and f != '__init__.txt':
                        path = os.path.join(root, f) 
                        self.search_file(path)
                        print ('searching files')         
        
        window = sublime.active_window()
        window.run_command("hide_overlay")
        window.show_quick_panel(self.matching_variables, None)
                        
   def search_file(self, path):
            robotfile=open(path, 'r')        
            for line in robotfile:
                print ('searching file line : ' + line)
                # search if line contains string
                pattern = '^\\$\\{\w+\\}'
                p = re.compile(pattern)
                m = p.match(line)
                if m:
                    print ('Match found: ', m.group())
                    print ('Match found group zero: ', m.group(0))
                    itemfound=m.group(0)
                    for char in '${}':
                        itemfound=itemfound.replace(char,'')  
                    self.matching_variables.append(itemfound)
                else:
                    print 'No match'					
					





