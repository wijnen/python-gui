#!/usr/bin/env python
# vim: set foldmethod=marker :

# gui.py - use pygtk without making the code dependant on it
# Copyright 2011 Bas Wijnen
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Documentation {{{
'''This module provides a toolkit-independent way to create a gui in a program.
The idea is that the gui definition should be toolkit-specific, but the rest of
the program should not. A program using this module will not define the gui
itself, and will not directly interact with it.

The way it does interact is through an interface of several variable types:
	get: a value which can be edited in the gui, and retreived by the
		program on request.
	set: a value which can be set to change the gui in some way.
	event: an event which can happen in the gui, which should trigger a
		callback.

For example, a text entry has a get and a set property, which can get and set
the current value of the entry respectively. A button has an event property
which fires when the button is clicked. A checkbutton has all three variable
types.

It is possible for a single widget to have zero or more variables of each type.
For example, a spinbutton has a set variable for setting its value, and another
to set its range.

A gui can be defined as:
<gtk>
	<Window>
		<VBox>Enter something<Entry changed='new_value'
			value='myvalue' />
			<Button clicked='stop'>Quit!</Button>
		</VBox>
	</Window>
</gtk>

A program can use this gui as:

import gui
def the_value_changed ():
	print ('New value: %s' % the_gui.get_value)
	print ('+1 to that')
	# This will cause recursion death, but you get the idea.
	the_gui.myvalue += '1'
the_gui = gui.Gui ()
the_gui.new_value = the_value_changed
the_gui.stop = lambda x: the_gui (False)
the_gui ()

As you can see, get and set variables can be used when they are wanted. Event
variables must be registered. The last line runs the main loop. The same
function with False as first argument stops the main loop. Nested loops are
allowed, but only the innermost running loop may be stopped.
'''
# }}}

# Imports. {{{
import sys
import os
import xml.etree.ElementTree as ET
import gtk
import glib
# }}}

# Sentinel object for specifying "no argument". {{{
class NoArgClass:
	pass
NO_ARG = NoArgClass ()
# }}}

def error (message, exit = False): # {{{
	'''Print an error message and optionally quit the program.'''
	sys.stderr.write (message + '\n')
	if exit:
		sys.exit (1)
# }}}

def nice_assert (assertion, message, exit = False): # {{{
	'''Assert with a nice message if it fails, and optionally quit the program.'''
	if assertion:
		return True
	error ('Assertion failed: %s' % message, exit)
	return False
# }}}

def find_path (name, packagename): # {{{
	'''Search name from environment, in current directory, and in user configuration.'''
	d = os.getenv ('GUI_PATH_' + packagename.upper ())
	if d is not None and os.path.exists (os.path.join (d, name)):
		return d
	d = os.getenv ('GUI_PATH')
	if d is not None and os.path.exists (os.path.join (d, name)):
		return d
	path = os.path.join (glib.get_user_config_dir (), packagename, name)
	if os.path.exists (path):
		return path
	path = os.path.join (os.path.dirname (sys.argv[0]), name)
	if os.path.exists (path):
		return path
	if os.path.exists (name):
		return name
	sys.stderr.write ('gui definition not found\n')
	sys.exit (1)
# }}}

def iswindow (x): # {{{
	'''Given a tag, return if it is a top level widget.'''
	return x in ('Window', 'Dialog', 'FileChooserDialog', 'AboutDialog')
# }}}

class Gui: # {{{
	'''Main class for toolkit-independent gui module.'''
	class __element: # {{{
		'''Internal class for holding gui elements.'''
		def __init__ (self, tag, attributes, children): # {{{
			'''Initialize an element.'''
			self.tag = tag
			self.attributes = attributes
			self.children = children
		# }}}
		def dump (self, indent): # {{{
			'''Dump the element to screen, including children, for debugging.'''
			ret = indent + '<' + self.tag
			for a in self.attributes.keys ():
				ret += ' ' + a + '="' + self.attributes[a].replace ('&', '&amp;').replace ('"', '&quot;') + '"'
			if len (self.children) == 0:
				return ret + '/>\n'
			ret += '>\n'
			for c in self.children:
				ret += c.dump (indent + '\t')
			return ret + indent + '</' + self.tag + '>\n'
		# }}}
		def __repr__ (self): # {{{
			'''Use the dump function when a string representation is requested.'''
			return self.dump ('')
		# }}}
	# }}}
	def __parse (self, element): # {{{
		'''Internal function for parsing the contents of an element.'''
		ret = self.__element (element.tag, element.attrib, [])
		if element.text and element.text.strip ():
			ret.children += (self.__element ('Label', {'value': ':' + element.text.strip ()}, []),)
		for c in element.getchildren ():
			ret.children += (self.__parse (c),)
			if c.tail and c.tail.strip ():
				ret.children += (self.__element ('Label', {'value': ':' + c.tail.strip ()}, []),)
		return ret
	# }}}
	def __init__ (self, packagename = None, execname = None, gtk = {}): # {{{
		'''Initialize the gui object.
		name is the program name, which defaults to basename (sys.argv[0])
		gtk is a list of gtk-specific objects which cannot be defined otherwise.
		Note that using gtk objects binds the application to the gtk toolkit.'''
		self.__menuaction = 0
		self.__uis = []
		self.__event = {}
		self.__get = {}
		self.__set = {}
		self.__loop_return = None
		if not execname:
			execname = os.path.basename (sys.argv[0])
			e = os.extsep + 'py'
			if execname.endswith (e):
				execname = execname[:-len (e)]
		if not packagename:
			packagename = execname
		self.__packagename = packagename
		self.__execname = execname
		self.__gtk = gtk
		self.__building = True
		filename = find_path (execname + os.extsep + 'gui', packagename)
		tree = ET.parse (filename)
		root = tree.getroot ()
		nice_assert (not root.tail or not root.tail.strip (), 'unexpected data at end of gui description')
		tree = self.__parse (root)

		nice_assert (tree.tag == 'gtk', 'gui description top level element is not <gtk>')
		self.__windows = []
		nice_assert (tree.attributes == {}, 'no attributes are allowed on top level window tags')
		for w in tree.children:
			if w.tag == 'Setting':
				self.__build (w)
				continue
			if nice_assert (iswindow (w.tag), 'top level gui elements must be Windows (not %s)' % w.tag):
				self.__accel_groups = []
				self.__show_build = True
				self.__windows += (self.__build (w),)
				for ag in self.__accel_groups:
					self.__windows[-1].add_accel_group (ag)
				self.__accel_groups = None
		nice_assert (len (self.__windows) > 0, 'there are no gui elements defined', exit = True)
		for w in self.__windows:
			w.connect ('destroy', lambda x: self (False, None))
		# Reverse order, so first defined window is shown last, therefore (most likely) on top
		self.__windows.reverse ()
		nice_assert (self.__gtk == {}, 'Not all externally provided widgets were used: ' + str (self.__gtk))
		del self.__gtk
		self.__building = False
	# }}}
	def __event_cb (self, object, *args): # {{{
		'''Internal callback for gui events.'''
		if self.__event[args[-1]][0] is not None:
			f = self.__event[args[-1]][0]
			if self.__event[args[-1]][1] is not None:
				args = list (args) + [self.__event[args[-1]][1]]
			f (*args[:-1])
	# }}}
	def __add_event (self, desc, event, widget, name = None): # {{{
		'''Internal function to register a gtk event.'''
		if name == None:
			name = event
		if name not in desc.attributes:
			return
		value = desc.attributes[name]
		del desc.attributes[name]
		if nice_assert (value not in self.__get and value not in self.__set, 'gui event name is already registered as get or set property'):
			if value not in self.__event:
				self.__event[value] = [None, None]
			widget.connect (event, self.__event_cb, value)
	# }}}
	def __add_custom_event (self, desc, name): # {{{
		'''Internal function to register a non-gtk event.'''
		if name not in desc.attributes:
			return None
		value = desc.attributes.pop (name)
		if nice_assert (value not in self.__get and value not in self.__set, 'gui custom event name is already registered as get or set property'):
			if value not in self.__event:
				self.__event[value] = [None, None]
		return value
	# }}}
	def __get_value (self, desc, name, with_default): # {{{
		if name not in desc.attributes:
			return None
		value = desc.attributes[name]
		del desc.attributes[name]
		pos = value.find (':')
		nice_assert (with_default or not pos >= 0, 'value %s for %s should not have a default value' % (value, name))
		if pos >= 0:
			return value[:pos], value[pos + 1:]
		else:
			return value, NO_ARG
	# }}}
	def __add_getset (self, desc, name, getcb, setcb, arg = NO_ARG, default = NO_ARG): # {{{
		gval = self.__get_value (desc, 'get_' + name, False)
		sval = self.__get_value (desc, 'set_' + name, True)
		val = self.__get_value (desc, name, True)
		nice_assert (val is None or (gval, sval) == (None, None), 'cannot use both get_ or set_ and non-prefixed value for %s' % name, exit = True)
		if val is not None:
			gval = val
			sval = val
		if not nice_assert (gval is None or (gval[0] not in self.__get and gval[0] not in self.__set and gval[0] not in self.__event), 'gui name %s is already registered as get, set or event' % name):
			return
		if not nice_assert (sval is None or (sval[0] not in self.__get and sval[0] not in self.__set and sval[0] not in self.__event), 'gui name %s is already registered as get, set or event' % name):
			return
		if not nice_assert (not name.startswith ('get_') and not name.startswith ('set_'), 'name %s must not start with get_ or set_' % name):
			return
		# Call default set
		if sval is not None and sval[1] is not NO_ARG:
			if arg is NO_ARG:
				setcb (sval[1])
			else:
				setcb (arg, sval[1])
		elif default is not NO_ARG:
			if arg is NO_ARG:
				setcb (default)
			else:
				setcb (arg, default)
		if sval is not None and sval[0] != '':
			self.__set[sval[0]] = (setcb, arg)
		if gval is not None and gval[0] != '':
			self.__get[gval[0]] = (getcb, arg)
	# }}}
	def __getattr__ (self, name): # {{{
		'''Get the value of a get variable.'''
		if not nice_assert (name in self.__get, 'trying to get nonexistent property %s' % name):
			return None
		if self.__get[name][0] is not None:
			if self.__get[name][1] is NO_ARG:
				return self.__get[name][0] ()
			else:
				return self.__get[name][0] (self.__get[name][1])
		else:
			return self.__get[name][1]
	# }}}
	def __setattr__ (self, name, value): # {{{
		'''Set the value of a set variable.'''
		if name.startswith ('_'):
			self.__dict__[name] = value
			return value
		if name in self.__event:
			if type (value) == tuple or type (value) == list:
				if nice_assert (len (value) == 2, 'setting event to list or tuple, but length is not 2'):
					self.__event[name][0] = value[0]
					self.__event[name][1] = value[1]
			else:
				self.__event[name][0] = value
				self.__event[name][1] = None
		elif name in self.__set:
			if self.__set[name][1] is NO_ARG:
				self.__set[name][0] (value)
			else:
				self.__set[name][0] (self.__set[name][1], value)
		else:
			error ('not setting ' + name + ", because it isn't defined in the gui")
	# }}}
	def __as_bool (self, value): # {{{
		'''Internal function to create a bool from a str. Str must be 'True' or 'False'.'''
		if type (value) == str:
			nice_assert (value == 'True' or value == 'False', 'string to be interpreted as bool is not "True" or "False"')
			return value == 'True'
		return bool (value)
	# }}}
	def __build_add (self, desc, parent): # {{{
		'''Internal function to create contents of a widget which should use add.'''
		nice_assert (len (desc.children) == 1, 'trying to add more than one child to a container that cannot hold more: %s' % str (desc))
		child = self.__build (desc.children[0])
		if child is not None:
			parent.add (child)
	# }}}
	def __build_pack (self, desc, parent): # {{{
		'''Internal function to create contents of a widget which should use pack.'''
		def expand (widget, value): # {{{
			widget.set_data ('expand', self.__as_bool (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			widget.set_child_packing (parent, widget.get_data ('expand'), widget.get_data ('fill'), 0, gtk.PACK_START)
		# }}}
		def fill (widget, value): # {{{
			widget.set_data ('fill', self.__as_bool (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			widget.set_child_packing (parent, widget.get_data ('expand'), widget.get_data ('fill'), 0, gtk.PACK_START)
		# }}}
		for c in desc.children:
			x = self.__build (c, {'expand': (lambda x: x.get_data ('expand'), expand), 'fill': (lambda x: x.get_data ('fill'), fill)})
			if x is None:
				continue
			if x.get_data ('expand') == None:
				x.set_data ('expand', True)
			if x.get_data ('fill') == None:
				x.set_data ('fill', True)
			parent.pack_start (x, x.get_data ('expand'), x.get_data ('fill'))
	# }}}
	def __build_noteadd (self, desc, parent): # {{{
		'''Internal function to create contents of a notebook.'''
		def set_page (widget, value): # {{{
			parent.set_data ('page', widget)
			p = widget.get_parent ()
			if p == None:
				return
			p.set_current_page (p.page_num (widget))
		# }}}
		def set_label (widget, value): # {{{
			widget.set_data ('label', value)
			p = widget.get_parent ()
			if p == None:
				return
			p.set_tab_label_text (widget, value)
		# }}}
		for c in desc.children:
			if 'name' in c.attributes and c.tag != 'Setting':
				name = c.attributes.pop ('name')
				nice_assert (name not in self.__get, 'tab name %s is already defined as a getter' % name)
				self.__get[name] = (None, parent.get_n_pages ())
			x = self.__build (c, {'page': (None, set_page), 'label': (lambda x: x.get_data ('label'), set_label)})
			if x is None:
				continue
			parent.append_page (x)
			label = x.get_data ('label')
			if label != None:
				parent.set_tab_label_text (x, label)
		page = parent.get_data ('page')
		if page != None:
			parent.set_current_page (parent.page_num (page))
	# }}}
	def __build_attach (self, desc, parent): # {{{
		'''Internal function to create contents of a table.'''
		def parse (value): # {{{
			w = value.split (',')
			v = 0
			if '' in w:
				del w[w.index ('')]
			if 'expand' in w:
				v |= gtk.EXPAND
				del w[w.index ('expand')]
			if 'fill' in w:
				v |= gtk.FILL
				del w[w.index ('fill')]
			if 'shrink' in w:
				v |= gtk.SHRINK
				del w[w.index ('shrink')]
			nice_assert (w == [], 'invalid options for table: %s' % ', '.join (w))
			return v
		# }}}
		def xset (widget, value): # {{{
			widget.set_data ('xopts', parse (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'x-options', widget.get_data ('xopts'))
		# }}}
		def yset (widget, value): # {{{
			widget.set_data ('yopts', parse (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'y-options', widget.get_data ('yopts'))
		# }}}
		def lset (widget, value): # {{{
			widget.set_data ('left', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'left-attach', widget.get_data ('left'))
		# }}}
		def rset (widget, value): # {{{
			widget.set_data ('right', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'right-attach', widget.get_data ('right'))
		# }}}
		def tset (widget, value): # {{{
			widget.set_data ('top', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'top-attach', widget.get_data ('top'))
		# }}}
		def bset (widget, value): # {{{
			widget.set_data ('bottom', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'bottom-attach', widget.get_data ('bottom'))
		# }}}
		cols = parent.get_property ('n-columns')
		current = [0, 0]
		for c in desc.children:
			x = self.__build (c, {'x-options': (lambda x: x.get_data ('xopts'), xset), 'y-options': (lambda x: x.get_data ('yopts'), yset), 'left': (lambda x: x.get_data ('left'), lset), 'right': (lambda x: x.get_data ('right'), rset), 'top': (lambda x: x.get_data ('top'), tset), 'bottom': (lambda x: x.get_data ('bottom'), bset)})
			if x is None:
				continue
			if x.get_data ('xopts') == None:
				x.set_data ('xopts', gtk.EXPAND | gtk.FILL)
			if x.get_data ('yopts') == None:
				x.set_data ('yopts', gtk.EXPAND | gtk.FILL)
			if x.get_data ('left') == None:
				x.set_data ('left', current[0])
			if x.get_data ('right') == None:
				x.set_data ('right', x.get_data ('left') + 1)
			if x.get_data ('top') == None:
				x.set_data ('top', current[1])
			if x.get_data ('bottom') == None:
				x.set_data ('bottom', x.get_data ('top') + 1)
			current[0] = x.get_data ('right')
			current[1] = x.get_data ('top')
			if current[0] >= cols:
				current[0] = 0
				current[1] += 1
			parent.attach (x, x.get_data ('left'), x.get_data ('right'), x.get_data ('top'), x.get_data ('bottom'), x.get_data ('xopts'), x.get_data ('yopts'))
	# }}}
	def __parse_menubar (self, items): # {{{
		'''Create a menubar from the children.'''
		retdesc = ''
		retactions = []
		for c in items:
			if not nice_assert ('title' in c.attributes, 'Menu item must have a title attribute'):
				continue
			name = c.attributes.pop ('title')
			action = 'a%d' % self.__menuaction
			self.__menuaction += 1
			if c.tag == 'Menu':
				desc, actions = self.__parse_menubar (c.children)
				retdesc += '<menu name="' + action + '" action="' + action + '">' + desc + '</menu>'
				retactions.append ((action, None, name))
				retactions += actions
			elif c.tag == 'MenuItem':
				v = self.__add_custom_event (c, 'action')
				if nice_assert (v != None, 'menu item %s has no action' % name):
					retdesc += '<menuitem name="' + name + '" action="' + action + '"/>'
					# The outer lambda function is needed to get a per-call copy of v; otherwise all options in a menu get the same event.
					retactions.append ((action, None, name, None, None, (lambda x:(lambda widget: self.__event_cb (widget, x))) (v)))
			else:
				error ('invalid item in MenuBar')
		return retdesc, retactions
	# }}}
	def __build (self, desc, fromparent = None): # {{{
		'''Internal function to create a widget, including contents.'''
		if desc.tag == 'Setting':
			nice_assert (len (desc.children) == 0, 'a Setting must not have children')
			if 'type' in desc.attributes:
				t = desc.attributes.pop ('type')
			else:
				t = 'str'
			nice_assert (t in ('str', 'bool', 'int'), 'invalid type for Setting; must be str, int, or bool.')
			if nice_assert ('name' in desc.attributes, 'a Setting without name is useless') and nice_assert ('value' in desc.attributes, 'a Setting must have a value'):
				v = desc.attributes.pop ('value')
				if t == 'int':
					try:
						v = int (v)
					except:
						error ('unable to parse setting %s as integer.' % v)
				elif t == 'bool':
					v = self.__as_bool (v)
				self.__get[desc.attributes.pop ('name')] = (None, v)
			nice_assert (desc.attributes == {}, 'unused attributes on Setting')
			return None
		elif desc.tag == 'Window':
			ret = gtk.Window ()
			ret.set_data ('show', True)
			self.__add_getset (desc, 'title', ret.get_title, ret.set_title, default = self.__packagename)
			self.__build_add (desc, ret)
		elif desc.tag == 'AboutDialog':
			ret = gtk.AboutDialog ()
			ret.set_program_name (self.__execname)
			ret.connect ('response', lambda w, v: ret.hide ())
			def setup (info): # {{{
				if isinstance (info, str):
					i = {}
					for l in info.split ('|'):
						k, v = l.split (None, 1)
						i[k] = v
					info = i
				if 'name' in info:
					ret.set_name (info['name'])
				if 'program_name' in info:
					ret.set_program_name (info['program_name'])
				if 'version' in info:
					ret.set_version (info['version'])
				if 'copyright' in info:
					ret.set_copyright (info['copyright'])
				if 'comments' in info:
					ret.set_comments (info['comments'])
				if 'license' in info:
					ret.set_license (info['license'])
				if 'wrap_license' in info:
					ret.set_wrap_license (info['wrap_license'])
				if 'website' in info:
					ret.set_website (info['website'])
				if 'website_label' in info:
					ret.set_website_label (info['website_label'])
				if 'authors' in info:
					ret.set_authors (info['authors'])
				if 'documenters' in info:
					ret.set_documenters (info['documenters'])
				if 'artists' in info:
					ret.set_artists (info['artists'])
				if 'translator_credits' in info:
					ret.set_translator_credits (info['translator_credits'])
			# }}}
			self.__add_getset (desc, 'setup', None, setup)
		elif desc.tag == 'Dialog':
			ret = gtk.Dialog ()
			ret.set_modal (True)
			if 'buttons' in desc.attributes:
				buttons = int (desc.attributes['buttons'])
				del desc.attributes['buttons']
			else:
				buttons = 1
			if not nice_assert (len (desc.children) >= buttons, 'not enough buttons defined'):
				return None
			cbs = [None] * buttons
			for i in range (buttons):
				b = desc.children[i]
				if b.tag != 'Button':
					desc.children[i] = self.__element ('Button', {}, [b])
				b = desc.children[i]
				cbs[i] = self.__add_custom_event (b, 'response')
				widget = self.__build (b)
				ret.add_action_widget (widget, i)
			desc.children = desc.children[buttons:]
			def response (widget, choice):
				widget.hide ()
				if cbs[choice] is None:
					return
				self.__event_cb (ret, cbs[choice])
			self.__add_getset (desc, 'run', None, lambda x: ret.run ())
			self.__add_getset (desc, 'title', ret.get_title, ret.set_title)
			ret.connect ('response', response)
			self.__build_pack (desc, ret.vbox)
		elif desc.tag == 'VBox':
			ret = gtk.VBox ()
			self.__build_pack (desc, ret)
		elif desc.tag == 'HBox':
			ret = gtk.HBox ()
			self.__build_pack (desc, ret)
		elif desc.tag == 'Notebook':
			ret = gtk.Notebook ()
			self.__add_getset (desc, 'show_tabs', ret.get_show_tabs, lambda value: ret.set_show_tabs (self.__as_bool (value)))
			self.__add_event (desc, 'switch_page', ret)
			self.__build_noteadd (desc, ret)
		elif desc.tag == 'Label':
			nice_assert (len (desc.children) == 0, 'a Label must not have children')
			ret = gtk.Label ()
			self.__add_getset (desc, 'value', ret.get_text, ret.set_text)
		elif desc.tag == 'Button':
			nice_assert (len (desc.children) == 1, 'trying to add more or less than one child to a Button')
			ret = gtk.Button ()
			self.__add_event (desc, 'clicked', ret)
			self.__build_add (desc, ret)
		elif desc.tag == 'CheckButton':
			nice_assert (len (desc.children) == 1, 'trying to add more or less than one child to a CheckButton')
			ret = gtk.CheckButton ()
			def get (): # {{{
				if ret.get_inconsistent ():
					return None
				return ret.get_active ()
			# }}}
			def set (value): # {{{
				if value is None:
					ret.set_inconsistent (True)
				else:
					ret.set_inconsistent (False)
					ret.set_active (self.__as_bool (value))
			# }}}
			self.__add_getset (desc, 'value', get, set)
			self.__add_event (desc, 'toggled', ret)
			self.__build_add (desc, ret)
		elif desc.tag == 'Entry':
			nice_assert (len (desc.children) == 0, 'trying to add a child to an Entry')
			ret = gtk.Entry ()
			self.__add_getset (desc, 'value', ret.get_text, ret.set_text)
			self.__add_event (desc, 'activate', ret)
			self.__add_event (desc, 'changed', ret)
		elif desc.tag == 'Frame':
			nice_assert (len (desc.children) == 1, 'trying to add more than one child to a Frame')
			ret = gtk.Frame ()
			def set (value, frame): # {{{
				if value == '':
					frame.set_label (None)
				else:
					frame.set_label (value)
			# }}}
			self.__add_getset (desc, 'label', ret.get_label, lambda value: ret.set_label (None if value == '' else value))
			self.__build_add (desc, ret)
		elif desc.tag == 'Table':
			if 'columns' in desc.attributes:
				cols = int (desc.attributes['columns'])
				del desc.attributes['columns']
			else:
				cols = 1
			ret = gtk.Table (1, cols)
			self.__build_attach (desc, ret)
		elif desc.tag == 'SpinButton':
			ret = gtk.SpinButton ()
			ret.set_increments (1, 10)
			def set_range (r): # {{{
				if isinstance (r, str):
					r = r.split (',')
				r = [float (x) for x in r]
				ret.set_range (*r)
			# }}}
			def set_increments (r): # {{{
				if isinstance (r, str):
					r = r.split (',')
				r = [float (x) for x in r]
				ret.set_increments (*r)
			# }}}
			self.__add_getset (desc, 'range', ret.get_range, set_range)
			self.__add_getset (desc, 'value', ret.get_value, lambda v: ret.set_value (float (v)))
			self.__add_getset (desc, 'increment', ret.get_increments, set_increments)
			self.__add_event (desc, 'value-changed', ret)
		elif desc.tag == 'ComboBoxText' or desc.tag == 'ComboBoxEntryText':
			if desc.tag == 'ComboBoxText':
				ret = gtk.combo_box_new_text ()
			else:
				ret = gtk.combo_box_entry_new_text ()
			def setcontent (value): # {{{
				if type (value) == str:
					l = value.split ('\n')
				else:
					l = value
				ret.get_model ().clear ()
				for i in l:
					ret.append_text (i.strip ())
			# }}}
			def set (value): # {{{
				def fill (model, path, iter, d): # {{{
					d += (model.get_value (iter, 0),)
					return False
				# }}}
				d = []
				ret.get_model ().foreach (fill, d)
				if value in d:
					ret.set_active (d.index (value))
				else:
					ret.append_text (value)
					ret.set_active (len (d))
			# }}}
			if len (desc.children) > 0:
				if nice_assert (len (desc.children) == 1 and desc.children[0].tag == 'Label', 'trying to add something other than one Label to a ComboBoxText or ComboBoxEntryText'):
					setcontent (desc.children[0].attributes['value'].split (':', 1)[1])
					ret.set_active (0)
			self.__add_getset (desc, 'content', None, setcontent)
			self.__add_getset (desc, 'value', ret.get_active, ret.set_active)
			self.__add_getset (desc, 'text', ret.get_active_text, set)
			self.__add_event (desc, 'changed', ret)
			if desc.tag == 'ComboBoxEntryText':
				v = self.__add_custom_event (desc, 'activate')
				if v is not None:
					ret.child.connect ('activate', self.__event_cb, v)
		elif desc.tag in ('FileChooserButton', 'FileChooserDialog'):
			nice_assert (len (desc.children) == 0, 'trying to add a child to a FileChooserButton or FileChooserDialog')
			if desc.tag == 'FileChooserButton':
				ret = gtk.FileChooserButton ('')
			else:
				ret = gtk.FileChooserDialog ('', buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
			def set_action (value): # {{{
				if value == 'open':
					ret.set_action (gtk.FILE_CHOOSER_ACTION_OPEN)
				elif value == 'save':
					ret.set_action (gtk.FILE_CHOOSER_ACTION_SAVE)
				elif value == 'select_folder':
					ret.set_action (gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
				elif value == 'create_folder':
					ret.set_action (gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER)
				else:
					error ('invalid action type %s for FileChooserButton' % value)
			# }}}
			def get_action (): # {{{
				a = ret.get_action ()
				if a == gtk.FILE_CHOOSER_ACTION_OPEN:
					return 'open'
				if a == gtk.FILE_CHOOSER_ACTION_SAVE:
					return 'save'
				if a == gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER:
					return 'select_folder'
				if a == gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER:
					return 'create_folder'
				error ('invalid action type for FileChooserButton or FileChooserDialog')
			# }}}
			self.__add_getset (desc, 'title', ret.get_title, ret.set_title)
			self.__add_getset (desc, 'action', get_action, set_action)
			self.__add_getset (desc, 'filename', ret.get_filename, ret.set_filename)
			self.__add_getset (desc, 'overwrite_confirmation', ret.get_do_overwrite_confirmation, lambda x: ret.set_do_overwrite_confirmation (self.__as_bool (x)))
			v = self.__add_custom_event (desc, 'response')
			if v is not None:
				def response (widget, r): # {{{
					widget.hide ()
					self.__event_cb (ret, ret.get_filename () if r == gtk.RESPONSE_ACCEPT else None, v)
				# }}}
				ret.connect ('response', response)
		elif desc.tag == 'HSeparator':
			ret = gtk.HSeparator ()
		elif desc.tag == 'VSeparator':
			ret = gtk.VSeparator ()
		elif desc.tag == 'MenuBar':
			ui = gtk.UIManager ()
			self.__accel_groups.append (ui.get_accel_group ())
			actiongroup = gtk.ActionGroup ('actiongroup')
			childdesc, actions = self.__parse_menubar (desc.children)
			actiongroup.add_actions (actions)
			ui.add_ui_from_string ('<ui><menubar>' + childdesc + '</menubar></ui>')
			ui.insert_action_group (actiongroup)
			ret = ui.get_widget ('/menubar')
			self.__uis.append (ui)
		elif desc.tag == 'Statusbar':
			ret = gtk.Statusbar ()
			value = ['']
			ret.push (0, value[0])
			def set (v): # {{{
				ret.pop (0)
				value[0] = v
				ret.push (0, value[0])
			# }}}
			self.__add_getset (desc, 'text', lambda: value[0], set)
		elif desc.tag == 'External':
			nice_assert (len (desc.children) == 0, 'trying to add a child to an External element')
			ret = self.__gtk[desc.attributes['id']]
			del self.__gtk[desc.attributes['id']]
			del desc.attributes['id']
		else:
			error ('invalid tag ' + desc.tag)
		if not iswindow (desc.tag):
			ret.show ()
			self.__add_getset (desc, 'show', ret.get_visible, lambda x: self.__show (ret, x))
		else:
			self.__add_getset (desc, 'show', lambda: ret.get_data ('show'), lambda x: self.__showwin (ret, x))
		self.__add_getset (desc, 'sensitive', ret.get_sensitive, ret.set_sensitive)
		if fromparent != None:
			for k in fromparent:
				self.__add_getset (desc, k, fromparent[k][0], fromparent[k][1], ret)
		if desc.attributes != {}:
			error ('unused attributes for ' + desc.tag + ': ' + str (desc.attributes))
		return ret
	# }}}
	def __showwin (self, w, value): # {{{
		w.set_data ('show', self.__as_bool (value))
		if not self.__building:
			self.__show (w, value)
	# }}}
	def __show (self, w, value): # {{{
		if self.__as_bool (value):
			w.show ()
		else:
			w.hide ()
	# }}}
	def __call__ (self, run = True, ret = None): # {{{
		'''Run the main loop.'''
		if run:
			for w in self.__windows:
				if w.get_data ('show') == True:	# True means show, None and False mean hide.
					w.show ()
			if run is True:
				gtk.main ()
			else:
				while gtk.events_pending ():
					gtk.main_iteration (False)
			return self.__loop_return
		else:
			self.__loop_return = ret
			gtk.main_quit ()
	# }}}
# }}}
