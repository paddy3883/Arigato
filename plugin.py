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
import shlex
import subprocess
import select
import functools
import json
import webbrowser
import shutil
import tempfile

from keyword_parse import get_keyword_at_pos
from string_populator import populate_testcase_file
from robot_scanner import Scanner, detect_robot_regex
from robot_common import OutputWindow
import stdlib_keywords
import robot_run

views_to_center = {}

stdlib_keywords.load(plugin_dir)

#------------------------------------------------------
# Auto completion of variable names.
#------------------------------------------------------

class CompleteVariableCommand(sublime_plugin.TextCommand):
    
    dollar_variables = []
    def __init__(self, view):
        #initialize(view)
        return

    def initialize(self, view):
        self.view = view
        self.window = sublime.active_window()
        self.folders= self.view.window().folders()
        for folder in self.folders:
            print ('searching folders') 
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.endswith('.txt') and f != '__init__.txt':
                        path = os.path.join(root, f) 
                        self.search_variables(path)
                        print ('searching files')

    def run(self, edit):
        view = self.view
        window = sublime.active_window()
        window.show_quick_panel(self.dollar_variables, self.on_done)
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':"${"}})
        self.curPos = self.view.sel()[0].begin()

    def search_variables(self, path):        
        pattern = '\s*\\$\\{\w+\\}'
        p = re.compile(pattern)
        try:
           with open(path, 'rb') as openFile:
                lines = openFile.readlines()
                for line in lines:
                     # search if line contains string
                     m = p.match(line)
                     if m:
                        itemfound=m.group(0).strip()
                        itemfound = re.sub('[${}]', '', itemfound)
                        if itemfound not in self.dollar_variables:
                            self.dollar_variables.append(itemfound)
        except IOError as e:
           return

    def on_done(self, index):
        if index == -1:
            return           
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':self.dollar_variables[index]+"}    "}})

#------------------------------------------------------
# 
#------------------------------------------------------

class CompleteListCommand(sublime_plugin.TextCommand):
    
    list_variables = []
    def __init__(self, view):
        #initialize(view)
        return

    def initialize(self, view):
        self.view = view
        self.window = sublime.active_window()
        self.folders= self.view.window().folders()
        for folder in self.folders:
            print ('searching folders') 
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.endswith('.txt') and f != '__init__.txt':
                        path = os.path.join(root, f) 
                        self.search_list_variables(path)
                        print ('searching files')  

    def run(self, edit):
        view = self.view
        window = sublime.active_window()
        window.show_quick_panel(self.list_variables, self.on_done)
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':"@{"}})
        self.curPos = self.view.sel()[0].begin()

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
           
    def on_done(self, index):
        if index == -1:
            return           
        self.view.run_command("insert_my_text", {"args":{'startPos':self.view.sel()[0].begin(), 'text':self.list_variables[index]+"}    "}})

#------------------------------------------------------
# 
#------------------------------------------------------

class InsertMyText(sublime_plugin.TextCommand):
    def run(self, edit, args):
        self.view.insert(edit, args['startPos'], args['text'])

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

        test_case = RobotTestCase(self.view)
        test_case.execute()

#----------------------------------------------------------
# Sublime context menu command: Run test suite
#----------------------------------------------------------
class RobotRunTestSuiteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not is_robot_format(self.view):
            return

        test_suite = RobotTestSuite(self.view)
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

#----------------------------------------------------------
# This class handles running a single test suite
#----------------------------------------------------------
class RobotTestSuite(object):

    def __init__(self, view):
        self.view = view

    def execute(self):
        test = Test(self.view)

        if not test.initialized:
            return False

        test.run_test()
        return True

#----------------------------------------------------------
# This class handles running a single test case
#----------------------------------------------------------
class RobotTestCase(object):

    def __init__(self, view):
        self.view = view

    def execute(self):
        test = Test(self.view)

        if not test.initialized:
            return False

        #TODO: this returns the keyword at cursor position, but we need to get the keyword at mouse position.
        sel = self.view.sel()[0]
        test_case_name = re.compile('\r|\n').split(self.view.substr(self.view.line(sel)))[0]

        #TODO: We can do few enhancements to this....
        # 1. Make sure the selected test case actually appears under ***Test Cases*** section.
        # 2. Even if the user clicks on a keyword inside a test case, execute the test case to which it belongs.
        if (len(test_case_name) == 0) or (test_case_name[0] == ' ') or (test_case_name[0] == '\t'):
            sublime.error_message("Please place cursor on a test case")
            return

        test_case_name = test_case_name.replace(' ', '').replace('\t', '')
        print ('Test case name = ' + test_case_name)

        test.run_test('--test ' + test_case_name)

        return True

#----------------------------------------------------------
# This class is used to execute tests.
#----------------------------------------------------------
class Test():

    def __init__(self, view):
        self.initialized = False
        self.view = view;
        self.robot_root_folder = view.window().folders()[0]

        if not view.file_name():
            sublime.error_message('Please save the buffer to a file first.')
            return

        # set default values for the run parameters.
        self.outputdir = 'TestResults'
        self.testsuites = 'testsuites'
        variables = []
        tags_to_exclude = []
        tags_to_include = []

        # load settings(testsuites name, output directory, variables, tags) from settings file.
        settings_file_name = os.path.join(self.robot_root_folder, 'robot.sublime-build')
        print ('Reading the settings from: ' + settings_file_name)

        if os.path.isfile(settings_file_name):
            try:
                json_data = open(settings_file_name)
                data = json.load(json_data)
                json_data.close()

                print ('JSON loaded. Now reading the settings...')
                if len(data['testsuites']) > 0:
                    self.testsuites = data['testsuites']

                if len(data['outputdir']) > 0:
                    self.outputdir = data['outputdir']

                if len(data['variables']) > 0:
                    variables = data['variables']

                if len(data['tags_to_exclude']) > 0:
                    tags_to_exclude = data['tags_to_exclude']

                if len(data['tags_to_include']) > 0:
                    tags_to_include = data['tags_to_include']

            except:
                sublime.error_message('Error reading: ' + settings_file_name)
                return

        else:
            sublime.error_message('Test runner settings file is not found in location: ' + settings_file_name)
            return

        # make sure test suites and results folders do not contain white-spaces inside.
        whitespace_pattern = re.compile('.*\s')
        if whitespace_pattern.match(self.testsuites):
            sublime.error_message('Testsuites folder: "' + self.testsuites + '" contains white-spaces!')
            return

        if whitespace_pattern.match(self.outputdir):
            sublime.error_message('Results folder: "' + self.outputdir + '" contains white-spaces!')
            return

        # append variables together so that they can be appended to the pybot command
        self.variable_line = ''
        for variable in variables:
            if whitespace_pattern.match(variable):
                sublime.error_message('Variable: "' + variable + '" contains white-spaces and is not allowed!')
                return
            self.variable_line += '--variable ' + variable + ' '

        # append exclude tags together so that they can be appended to the pybot command
        self.exclude_tags = ''
        for exclude_tag in tags_to_exclude:
            if whitespace_pattern.match(exclude_tag):
                sublime.error_message('Tag: "' + exclude_tag + '" contains white-spaces and is not allowed!')
                return
            self.exclude_tags += '--exclude ' + exclude_tag + ' '

        # append include tags together so that they can be appended to the pybot command
        self.include_tags = ''
        for include_tag in tags_to_include:
            if whitespace_pattern.match(include_tag):
                sublime.error_message('Tag: "' + include_tag + '" contains white-spaces and is not allowed!')
                return
            self.include_tags += '--include ' + include_tag + ' '

        # change current directory to the robot root folder.
        os.chdir(self.robot_root_folder)

        # find the suite name
        test_suite_path, test_suite_file_name = os.path.split(view.file_name())
        self.test_suite_name = test_suite_file_name.rstrip('.txt')

        print ('Test suite path = ' + test_suite_path)
        print ('Test suites = ' + self.testsuites)
        test_suite_path = os.path.relpath(test_suite_path, self.testsuites).replace('\\', '.')

        if not (test_suite_path == '.'):
            self.test_suite_name = test_suite_path + '.' + self.test_suite_name

        self.test_suite_name = self.test_suite_name.replace(' ', '')
        print ('Test suite name = ' + self.test_suite_name)
        self.initialized = True

    def run_test(self, filter = ''):
        if not self.initialized:
            return

        output_window = OutputWindow(self.view.window(), plugin_dir, '*Output*')

        def _C(output):
            if output is not None:
                output_window.append_text(output)

        process('pybot --outputdir ' + self.outputdir + ' ' + 
                self.variable_line + self.exclude_tags + self.include_tags + 
                '--suite ' + self.test_suite_name + ' ' + filter + ' ' + self.testsuites, 
                _C, self.robot_root_folder, self.outputdir)

def process(command, callback, working_dir, outputdir):

    thread = threading.Thread(target=_process, kwargs={
        'command': command,
        'callback': callback,
        'working_dir': working_dir,
        'outputdir': outputdir
    })
    thread.start()

def _process(command, callback, working_dir, outputdir, **kwargs):
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

                output_file_name = outputdir + '/log.html'
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

