'''
Created on 2 Apr 2014

@author: GWallace
'''
import os
import re


list_variables = []
matching_variables = []

def load_robot_variables(currentpath):
    
    for root, dirs, files in os.walk(currentpath):
        for f in files:
            if f.endswith('.txt') and f != '__init__.txt':
                path = os.path.join(root, f) 
                search_file(path)
                         
def search_file(path):
    robotfile=open(path, 'r') 
    pattern1 = re.compile('\s*\\$\\{\w+\\}')
    pattern2 = re.compile('\s*@\\{\w+\\}')       
    for line in robotfile:
        print ('searching file line : ' + line)
        
        # search if line contains string
        m1= pattern1.match(line)
        m2= pattern2.match(line)
        if m1:
            print ('Match found: ', m1.group())
            itemfound=m1.group(0).strip()
            itemfound=remove_extra_chars(itemfound, '${}')
            if itemfound not in matching_variables:
                print ('Adding item: ' + itemfound)
                matching_variables.append(itemfound)   
        elif m2:
            print ('Match found group zero: ', m2.group(0))
            listitem=m2.group(0).strip()
            listitem=remove_extra_chars(listitem, '@{}')
            if listitem not in list_variables:
                print ('Adding item: ' + listitem)
                list_variables.append(listitem)   
                                             
def remove_extra_chars(robotvariable, charstoremove):
    for char in charstoremove:
        robotvariable=robotvariable.replace(char,'')  
    return robotvariable
                       
def write_variables(filename, robotvariablelist):
    
    myfile = open(filename, "w")
    for name in robotvariablelist:
        myfile.write(name+"\n")
    myfile.close()             
                             

def set_robot_variables(robotdir):
    print 'getting robot dir'
    if robotdir is None:
        print 'Failed to pass in robothome_path '
    else:
        print 'Failed to pass in robothome_path '
        load_robot_variables(robotdir)        
    
    write_variables('robotvariables.txt', matching_variables)
    write_variables('robotlistvariables.txt', list_variables)