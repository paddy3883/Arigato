import os
import re
import sublime
import threading
import subprocess
import functools
import json
import webbrowser

from robot_common import OutputWindow

#----------------------------------------------------------
# This class handles running a single test suite
#----------------------------------------------------------
class RobotTestSuite(object):

    def __init__(self, view, plugin_dir):
        self.view = view
        self.plugin_dir = plugin_dir

    def execute(self):
        test = Test(self.view, self.plugin_dir)

        if not test.initialized:
            return False

        test.run_test()
        return True

#----------------------------------------------------------
# This class handles running a single test case
#----------------------------------------------------------
class RobotTestCase(object):

    def __init__(self, view, plugin_dir):
        self.view = view
        self.plugin_dir = plugin_dir

    def execute(self):
        test = Test(self.view, self.plugin_dir)

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

    def __init__(self, view, plugin_dir):
        self.initialized = False
        self.view = view
        self.plugin_dir = plugin_dir
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

        # find the suite name
        test_suite_path, test_suite_file_name = os.path.split(view.file_name())
        self.test_suite_name = os.path.splitext(test_suite_file_name)[0]

        print ('Test suite path = ' + test_suite_path)
        print ('Test suites = ' + self.testsuites)
        test_suite_path = os.path.relpath(test_suite_path, os.path.join(self.robot_root_folder, self.testsuites)).replace('\\', '.')

        if not (test_suite_path == '.'):
            self.test_suite_name = test_suite_path + '.' + self.test_suite_name

        self.test_suite_name = self.test_suite_name.replace(' ', '')
        print ('Test suite name = ' + self.test_suite_name)
        self.initialized = True

    def run_test(self, filter = ''):
        if not self.initialized:
            return

        output_window = OutputWindow(self.view.window(), self.plugin_dir, '*Output*')

        def _display_text_in_output_window(output):
            if output is not None:
                output_window.append_text(output)

        self._open_thread_to_execute_pybot(
            'pybot --outputdir ' + self.outputdir + ' ' + 
            self.variable_line + self.exclude_tags + self.include_tags +
            '--suite ' + self.test_suite_name + ' ' + 
            filter + ' ' + self.testsuites, 
            _display_text_in_output_window, 
            self.robot_root_folder, 
            self.outputdir
            )

    def _open_thread_to_execute_pybot(self, command, callback, working_dir, outputdir):

        thread = threading.Thread(
                    target = self._execute_pybot, 
                    kwargs = {
                        'command': command,
                        'callback': callback,
                        'working_dir': working_dir,
                        'outputdir': outputdir
                        }
                    )

        thread.start()

    def _execute_pybot(self, command, callback, working_dir, outputdir, **kwargs):
        startupinfo = None
        return_code = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:

            # display the pybot command that we execute
            main_thread(callback, command + '\n\n')

            # start pybot command
            proc = subprocess.Popen(
                    command,
                    stdin = subprocess.PIPE,
                    universal_newlines = True,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.STDOUT,
                    shell = True,
                    cwd = working_dir,
                    startupinfo = startupinfo
                    )

            # collect input while the pybot command is in progress
            while return_code is None:
                return_code = proc.poll()

                if return_code is None or return_code == 0:
                    output = True
                    while output:
                        output = proc.stdout.readline()
                        main_thread(callback, output, **kwargs)

        except subprocess.CalledProcessError as e:

            main_thread(callback, e.returncode)

        except OSError as e:

            if e.errno == 2:
                sublime.message_dialog('Command not found\n\nCommand is: %s' % command)
            else:
                raise e

        if return_code == 0:
            main_thread(callback, '\nTest execution is complete and all tests passed!', **kwargs)
        else:
            main_thread(callback, '\nTest execution is complete, but there are test failures!', **kwargs)

            output_file_name = os.path.join(working_dir, outputdir, 'log.html')
            print "output file: " + output_file_name

            if os.path.isfile(output_file_name):
                webbrowser.open_new('file://' + output_file_name)

#-------------------------------------------------------------------------
# A function that executes a callback function on the main thread.
#-------------------------------------------------------------------------
def main_thread(callback, *args, **kwargs):
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)
