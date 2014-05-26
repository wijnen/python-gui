#!/usr/bin/env python
# vim: set foldmethod=marker :

# gui.py - use pygtk without making the code dependant on it
# Copyright 2011 Bas Wijnen {{{
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
# }}}

# Imports. {{{
import sys
import os
import xml.etree.ElementTree as ET
import gtk
import glib
import gobject
import xdgbasedir
# }}}

# Global helper stuff {{{
# Sentinel object for specifying "no argument". {{{
NO_ARG = object()
# }}}

def error(message, exit = False): # {{{
	'''Print an error message and optionally quit the program.'''
	sys.stderr.write(message + '\n')
	if exit:
		sys.exit(1)
# }}}

def nice_assert(assertion, message, exit = False): # {{{
	'''Assert with a nice message if it fails, and optionally quit the program.'''
	if assertion:
		return True
	error('Assertion failed: %s' % message, exit)
	return False
# }}}

def find_path(name, packagename): # {{{
	'''Search name from environment, in current directory, and in user configuration.'''
	# Allow overriding with environment keys.
	d = os.getenv('GUI_PATH_' + packagename.upper())
	if d is not None and os.path.exists(os.path.join(d, name)):
		return d
	d = os.getenv('GUI_PATH')
	if d is not None and os.path.exists(os.path.join(d, name)):
		return d
	# Use the file in the same directory as the executable.
	path = os.path.join(os.path.dirname(sys.argv[0]), name)
	if os.path.exists(path):
		return path
	# This returns all existing matching files, in order of importance.  Use the first, if any.
	ret = xdgbasedir.data_files_read(name, packagename)
	if len(ret) > 0:
		return ret[0]
	# Use the file in the current directory.
	if os.path.exists(name):
		return name
	# Give up.
	sys.stderr.write('Warning: gui definition for %s not found\n' % name)
	return None
# }}}

def as_bool(value): # {{{
	'''Internal function to create a bool from a str. Str must be 'True' or 'False'.'''
	if isinstance(value, str):
		nice_assert(value == 'True' or value == 'False', 'string to be interpreted as bool is not "True" or "False": %s' % value)
		return value == 'True'
	return bool(value)
# }}}

def parse_nums(r): # {{{
	if isinstance(r, str):
		r = r.split(',')
	r = [float(x) for x in r]
	return r
# }}}
# }}}

class Wrapper: # {{{
	def __init__(self, gui, desc, widget, data): # {{{
		self.gui = gui
		self.desc = desc
		self.data = data
		class wrapper(widget):
			def __init__(self, parent):
				parent.widget = self
				widget.__init__(self, parent)
		wrapper(self)
	# }}}
	@classmethod	# create {{{
	def create(cls, gui, desc, widget, data):
		return cls(gui, desc, widget, data)
	# }}}
	def normalize_indices(self, start, end, target): # {{{
		if start < 0:
			start += len(self.desc.children)
		if end < 0:
			end += len(self.desc.children)
		nice_assert(0 <= start < len(self.desc.children) and 0 <= end < len(self.desc.children) and start <= end, 'invalid target range for child widgets: %d, %d' % (start, end))
		if target is None:
			target = self.widget
		return start, end, target
	# }}}
	def assert_children(self, min, max = None): # {{{
		if max is None:
			max = min
		elif max < 0:
			# Always acceptable.
			max = len(self.desc.children)
		return nice_assert(min <= len(self.desc.children) <= max, '%s needs %d-%d children, not %d' % (self.desc.tag, min, max, len(self.desc.children)))
	# }}}
	def register_attribute(self, name, getcb, setcb, arg = NO_ARG, default = NO_ARG): # {{{
		def get_value(name, with_default): # {{{
			if name not in self.desc.attributes:
				return None
			value = self.desc.attributes.pop(name)
			if value == '':
				return None
			pos = value.find(':')
			nice_assert(with_default or not pos >= 0, 'value %s for %s should not have a default value' % (value, name))
			if pos >= 0:
				return value[:pos], value[pos + 1:]
			else:
				return value, NO_ARG
		# }}}
		gval = get_value('get_' + name, False)
		sval = get_value('set_' + name, True)
		val = get_value(name, True)
		if not nice_assert(val is None or (gval, sval) == (None, None), 'cannot use both get_ or set_ and non-prefixed value for %s' % name):
			return
		if val is not None:
			gval = val
			sval = val
		if not nice_assert(gval is None or gval[0] == '' or (gval[0] not in self.gui.__get__ and gval[0] not in self.gui.__set__ and gval[0] not in self.gui.__event__), 'gui name %s is already registered as get, set or event' % (gval[0] if gval is not None else '')):
			return
		if not nice_assert(sval is None or sval[0] == '' or (sval[0] not in self.gui.__get__ and sval[0] not in self.gui.__set__ and sval[0] not in self.gui.__event__), 'gui name %s is already registered as get, set or event' % (sval[0] if sval is not None else '')):
			return
		if not nice_assert(not name.startswith('get_') and not name.startswith('set_'), 'name %s must not start with get_ or set_' % name):
			return
		if sval is not None:
			if sval[1] is not NO_ARG:
				# A set callback is set, and an initial argument is provided.
				if arg is NO_ARG:
					setcb(sval[1])
				else:
					setcb(arg, sval[1])
			elif default is not NO_ARG:
				# A set callback is set, and a default argument is provided.
				if arg is NO_ARG:
					setcb(default)
				else:
					setcb(arg, default)
			if sval[0] != '':
				# A set callback is set.
				self.gui.__set__[sval[0]] = (setcb, arg)
		if gval is not None and gval[0] != '':
			# A get callback is set.
			self.gui.__get__[gval[0]] = (getcb, arg)
	# }}}
	def register_bool_attribute(self, name, getcb, setcb): # {{{
		self.register_attribute(name, lambda: as_bool(getcb()), lambda x: setcb(as_bool(x)))
	# }}}
	def register_gtk_event(self, name, gtk_widget = None): # {{{
		'''Internal function to register a gtk event.'''
		value = self.get_attribute(name)
		if value is None:
			return
		if nice_assert(value not in self.gui.__get__ and value not in self.gui.__set__, 'gui event name is already registered as get or set property'):
			if value not in self.gui.__event__:
				self.gui.__event__[value] = [None, None]
			if gtk_widget is None:
				gtk_widget = self.widget
			gtk_widget.connect(name, self.gui.__event_cb__, value)
	# }}}
	def register_event(self, name): # {{{
		'''Internal function to register a non-gtk event.'''
		value = self.get_attribute(name)
		if value is None:
			return lambda *args, **kwargs: None
		if nice_assert(value not in self.gui.__get__ and value not in self.gui.__set__, 'gui custom event name is already registered as get or set property'):
			if value not in self.gui.__event__:
				self.gui.__event__[value] = [None, None]
		return lambda *args, **kwargs: self.gui.__event_cb__(self.widget, *(args + (value,)), **kwargs)
	# }}}
	def add(self, start = 0, end = -1, target = None): # {{{
		'''Internal function to create contents of a widget which should use add.'''
		start, end, target = self.normalize_indices(start, end, target)
		nice_assert(end == start, 'Container must have exactly one child: %s' % str(self.desc))
		child = self.gui.__build__(self.desc.children[start])
		if child is not None:
			target.add(child)
	# }}}
	def pack_add(self, start = 0, end = -1, target = None): # {{{
		'''Internal function to create contents of a widget which should use pack.'''
		start, end, target = self.normalize_indices(start, end, target)
		def expand(widget, value): # {{{
			widget.set_data('expand', as_bool(value))
			parent = widget.get_parent()
			if parent == None:
				return
			widget.set_child_packing(parent, widget.get_data('expand'), widget.get_data('fill'), 0, gtk.PACK_START)
		# }}}
		def fill(widget, value): # {{{
			widget.set_data('fill', as_bool(value))
			parent = widget.get_parent()
			if parent == None:
				return
			widget.set_child_packing(parent, widget.get_data('expand'), widget.get_data('fill'), 0, gtk.PACK_START)
		# }}}
		for c in self.desc.children[start:end + 1]:
			x = self.gui.__build__(c, {'expand': (lambda x: x.get_data('expand'), expand), 'fill': (lambda x: x.get_data('fill'), fill)})
			if x is None:
				continue
			if x.get_data('expand') == None:
				x.set_data('expand', True)
			if x.get_data('fill') == None:
				x.set_data('fill', True)
			target.pack_start(x, x.get_data('expand'), x.get_data('fill'))
	# }}}
	def notebook_add(self, start = 0, end = -1, target = None): # {{{
		'''Internal function to create contents of a notebook.'''
		start, end, target = self.normalize_indices(start, end, target)
		def set_page(widget, value): # {{{
			'''View this child in the Notebook.
			If the page isn't attached yet, record that it should be shown when it is.'''
			target.set_data('page', widget)
			p = widget.get_parent()
			if p is not None:
				p.set_current_page(p.page_num(widget))
		# }}}
		def set_label(widget, value): # {{{
			widget.set_data('label', value)
			p = widget.get_parent()
			if p is not None:
				p.set_tab_label_text(widget, value)
		# }}}
		for c in self.desc.children[start:end + 1]:
			if 'name' in c.attributes and c.tag != 'Setting':
				name = c.attributes.pop('name')
				nice_assert(name not in self.gui.__get__, 'tab name %s is already defined as a getter' % name)
				self.gui.__get__[name] = (None, self.widget.get_n_pages())
			x = self.gui.__build__(c, {'page': (None, set_page), 'label': (lambda x: x.get_data('label'), set_label)})
			if x is None:
				continue
			target.append_page(x)
			label = x.get_data('label')
			if label != None:
				target.set_tab_label_text(x, label)
		page = target.get_data('page')
		if page is not None:
			target.set_current_page(self.widget.page_num(page))
	# }}}
	def paned_add(self, start = 0, end = -1, target = None): # {{{
		'''Internal function to create contents of a paned widget.'''
		start, end, target = self.normalize_indices(start, end, target)
		nice_assert(end == start + 1, 'Paned widgets must have exactly 2 children: %s' % str(self.desc))
		child = self.gui.__build__(self.desc.children[start])
		if child is not None:
			target.add1(child)
		child = self.gui.__build__(self.desc.children[start + 1])
		if child is not None:
			target.add2(child)
	# }}}
	def table_add(self, start = 0, end = -1, target = None): # {{{
		'''Internal function to create contents of a table.'''
		start, end, target = self.normalize_indices(start, end, target)
		def parse(value): # {{{
			w = value.split(',')
			v = 0
			if '' in w:
				del w[w.index('')]
			if 'expand' in w:
				v |= gtk.EXPAND
				del w[w.index('expand')]
			if 'fill' in w:
				v |= gtk.FILL
				del w[w.index('fill')]
			if 'shrink' in w:
				v |= gtk.SHRINK
				del w[w.index('shrink')]
			nice_assert(w == [], 'invalid options for table: %s' % ', '.join(w))
			return v
		# }}}
		def xset(widget, value): # {{{
			widget.set_data('xopts', parse(value))
			parent = widget.get_parent()
			if parent is not None:
				parent.child_set_property(widget, 'x-options', widget.get_data('xopts'))
		# }}}
		def yset(widget, value): # {{{
			widget.set_data('yopts', parse(value))
			parent = widget.get_parent()
			if parent is not None:
				parent.child_set_property(widget, 'y-options', widget.get_data('yopts'))
		# }}}
		def lset(widget, value): # {{{
			widget.set_data('left', int(value))
			parent = widget.get_parent()
			if parent is not None:
				parent.child_set_property(widget, 'left-attach', widget.get_data('left'))
		# }}}
		def rset(widget, value): # {{{
			widget.set_data('right', int(value))
			parent = widget.get_parent()
			if parent is not None:
				parent.child_set_property(widget, 'right-attach', widget.get_data('right'))
		# }}}
		def tset(widget, value): # {{{
			widget.set_data('top', int(value))
			parent = widget.get_parent()
			if parent is not None:
				parent.child_set_property(widget, 'top-attach', widget.get_data('top'))
		# }}}
		def bset(widget, value): # {{{
			widget.set_data('bottom', int(value))
			parent = widget.get_parent()
			if parent is not None:
				parent.child_set_property(widget, 'bottom-attach', widget.get_data('bottom'))
		# }}}
		cols = target.get_property('n-columns')
		current = [0, 0]
		for c in self.desc.children[start:end + 1]:
			x = self.gui.__build__(c, {'x-options': (lambda x: x.get_data('xopts'), xset), 'y-options': (lambda x: x.get_data('yopts'), yset), 'left': (lambda x: x.get_data('left'), lset), 'right': (lambda x: x.get_data('right'), rset), 'top': (lambda x: x.get_data('top'), tset), 'bottom': (lambda x: x.get_data('bottom'), bset)})
			if x is None:
				continue
			if x.get_data('xopts') == None:
				x.set_data('xopts', gtk.EXPAND | gtk.FILL)
			if x.get_data('yopts') == None:
				x.set_data('yopts', gtk.EXPAND | gtk.FILL)
			if x.get_data('left') == None:
				x.set_data('left', current[0])
			if x.get_data('right') == None:
				x.set_data('right', x.get_data('left') + 1)
			if x.get_data('top') == None:
				x.set_data('top', current[1])
			if x.get_data('bottom') == None:
				x.set_data('bottom', x.get_data('top') + 1)
			current[0] = x.get_data('right')
			current[1] = x.get_data('top')
			if current[0] >= cols:
				current[0] = 0
				current[1] += 1
			target.attach(x, x.get_data('left'), x.get_data('right'), x.get_data('top'), x.get_data('bottom'), x.get_data('xopts'), x.get_data('yopts'))
	# }}}
	def action_add(self, start = 0, end = -1, target = None): # {{{
		start, end, target = self.normalize_indices(start, end, target)
		for i in range(start, end + 1):
			widget = self.gui.__build__(self.desc.children[i])
			target.add_action_widget(widget, i - start)
	# }}}
	def parse_menubar(self, items = None, start = 0, end = -1, target = None): # {{{
		'''Create a menubar from the children.'''
		if items is None:
			items = self.desc.children
		target = self.normalize_indices(start, end, target)[2]
		if start < 0:
			start += len(items)
		if end < 0:
			end += len(items)
		nice_assert(0 <= start < len(items) and 0 <= end < len(items) and start <= end, 'invalid target range for menubar items: %d, %d' % (start, end))
		retdesc = ''
		retactions = []
		for c in items:
			if not nice_assert('title' in c.attributes, 'Menu item must have a title attribute'):
				continue
			name = c.attributes.pop('title')
			if 'accel' in c.attributes:
				accel = c.attributes.pop('accel')
			else:
				accel = None
			if 'tooltip' in c.attributes:
				tooltip = c.attributes.pop('tooltip')
			else:
				tooltip = None
			action = 'a%d' % self.gui.__menuaction__
			self.gui.__menuaction__ += 1
			if c.tag == 'Menu':
				desc, actions = self.parse_menubar(c.children)
				retdesc += '<menu name="' + action + '" action="' + action + '">' + desc + '</menu>'
				retactions.append((action, None, name, accel, tooltip))
				retactions += actions
			elif c.tag == 'MenuItem':
				if not nice_assert('action' in c.attributes, 'menu item %s has no action' % name):
					continue
				value = c.attributes.pop('action')
				if value not in self.gui.__event__:
					self.gui.__event__[value] = [None, None]
				retdesc += '<menuitem name="' + name + '" action="' + action + '"/>'
				# The outer lambda function is needed to get a per-call copy of v; otherwise all options in a menu get the same event.
				retactions.append((action, None, name, accel, tooltip, (lambda v = value: (lambda *args, **kwargs: self.gui.__event_cb__(self.widget, *(args + (v,)), **kwargs))) ()))
			else:
				error('invalid item in MenuBar')
		return retdesc, retactions
	# }}}
	def get_attribute(self, name, default = None): # {{{
		if name not in self.desc.attributes:
			return default
		ret = self.desc.attributes.pop(name)
		if ret == '':
			return None
		return ret
	# }}}
# }}}

# Built-in widget classes. {{{
builtins = {}
class Setting: # {{{
	def __init__(self, gui):
		gui.assert_children(0)
		t = gui.get_attribute('type', default = 'str')
		nice_assert(t in('str', 'bool', 'int'), 'invalid type for Setting; must be str, int, or bool.')
		name = gui.get_attribute('name')
		value = gui.get_attribute('value')
		if nice_assert(name is not None, 'a Setting without name is useless') and nice_assert('value' is not None, 'a Setting must have a value'):
			if t == 'int':
				try:
					value = int(value)
				except:
					error('unable to parse setting %s as integer.' % value)
			elif t == 'bool':
				value = as_bool(value)
			nice_assert('name' not in gui.gui.__get__, 'Setting name %s is already used' % name)
			gui.gui.__get__[name] = (None, value)
		self.return_object = None
builtins['Setting'] = Setting
# }}}
class Label(gtk.Label): # {{{
	def __init__(self, gui):
		gtk.Label.__init__(self)
		gui.assert_children(0)
		gui.register_attribute('value', self.get_text, self.set_text)
builtins['Label'] = Label
#}}}
class Window(gtk.Window): # {{{
	gtk_window = True
	def __init__(self, gui):
		gtk.Window.__init__(self)
		gui.assert_children(1)
		self.set_data('show', True)
		gui.register_attribute('title', self.get_title, self.set_title, default = gui.gui.__packagename__)
		gui.add()
builtins['Window'] = Window
# }}}
class ScrolledWindow(gtk.ScrolledWindow): # {{{
	def __init__(self, gui):
		gtk.ScrolledWindow.__init__(self)
		gui.assert_children(1)
		gui.add()
builtins['ScrolledWindow'] = ScrolledWindow
#}}}
class AboutDialog(gtk.AboutDialog): # {{{
	gtk_window = True
	def __init__(self, gui):
		gtk.AboutDialog.__init__(self)
		self.set_program_name(gui.gui.__execname__)
		self.connect('response', lambda w, v: self.hide())
		def setup(info): # {{{
			if isinstance(info, str):
				i = {}
				for l in info[1:].split(info[0]):
					k, v = l.split(None, 1)
					i[k] = v
				info = i
			if 'name' in info:
				self.set_name(info['name'])
			if 'program_name' in info:
				self.set_program_name(info['program_name'])
			if 'version' in info:
				self.set_version(info['version'])
			if 'copyright' in info:
				self.set_copyright(info['copyright'])
			if 'comments' in info:
				self.set_comments(info['comments'])
			if 'license' in info:
				self.set_license(info['license'])
			if 'wrap_license' in info:
				self.set_wrap_license(as_bool(info['wrap_license']))
			if 'website' in info:
				self.set_website(info['website'])
			if 'website_label' in info:
				self.set_website_label(info['website_label'])
			if 'authors' in info:
				self.set_authors(info['authors'])
			if 'documenters' in info:
				self.set_documenters(info['documenters'])
			if 'artists' in info:
				self.set_artists(info['artists'])
			if 'translator_credits' in info:
				self.set_translator_credits(info['translator_credits'])
		# }}}
		gui.register_attribute('setup', None, setup)
builtins['AboutDialog'] = AboutDialog
# }}}
class Dialog(gtk.Dialog): # {{{
	gtk_window = True
	def __init__(self, gui):
		gtk.Dialog.__init__(self)
		self.set_modal(True)
		buttons = int(gui.get_attribute('buttons', default = 1))
		if not gui.assert_children(buttons, -1):
			raise ValueError('not enough buttons defined')
		cbs = [None] * buttons
		for i in range(buttons):
			b = gui.desc.children[i]
			if b.tag != 'Button':
				gui.desc.children[i] = gui.gui.__element__('Button', {}, [b])
			cbs[i] = gui.register_event('response')
		gui.action_add(0, buttons - 1)
		def response(widget, choice):
			widget.hide()
			if cbs[choice] is None:
				return
			cbs[choice] ()
		gui.register_attribute('run', None, lambda x: self.run())
		gui.register_attribute('title', self.get_title, self.set_title)
		self.connect('response', response)
		gui.pack_add(target = self.vbox, start = buttons)
builtins['Dialog'] = Dialog
# }}}
class VBox(gtk.VBox): # {{{
	def __init__(self, gui):
		gtk.VBox.__init__(self)
		gui.pack_add()
builtins['VBox'] = VBox
#}}}
class HBox(gtk.HBox): # {{{
	def __init__(self, gui):
		gtk.HBox.__init__(self)
		gui.pack_add()
builtins['HBox'] = HBox
#}}}
class Notebook(gtk.Notebook): # {{{
	def __init__(self, gui):
		gtk.Notebook.__init__(self)
		gui.register_bool_attribute('show_tabs', self.get_show_tabs, self.set_show_tabs)
		tab_pos = {gtk.POS_TOP: 'top', gtk.POS_BOTTOM: 'bottom', gtk.POS_LEFT: 'left', gtk.POS_RIGHT: 'right'}
		gui.register_attribute('tab_pos', lambda: tab_pos[self.get_tab_pos()], lambda x: self.set_tab_pos([t[0] for t in tab_pos.items() if t[1] == x][0]))
		def save_page():
			p = self.get_current_page()
			return lambda: self.set_current_page(p)
		gui.register_attribute('save_page', lambda: save_page, None)
		gui.register_gtk_event('switch_page')
		gui.notebook_add()
builtins['Notebook'] = Notebook
#}}}
class Button(gtk.Button): # {{{
	def __init__(self, gui):
		gtk.Button.__init__(self)
		gui.register_gtk_event('clicked')
		gui.add()
builtins['Button'] = Button
#}}}
class CheckButton(gtk.CheckButton): # {{{
	def __init__(self, gui):
		gtk.CheckButton.__init__(self)
		def get(): # {{{
			if self.get_inconsistent():
				return None
			return self.get_active()
		# }}}
		def set(value): # {{{
			if value is None:
				self.set_inconsistent(True)
			else:
				self.set_inconsistent(False)
				self.set_active(as_bool(value))
		# }}}
		gui.register_attribute('value', get, set)
		gui.register_gtk_event('toggled')
		gui.add()
builtins['CheckButton'] = CheckButton
#}}}
class RadioButton(gtk.RadioButton): # {{{
	def __init__(self, gui):
		gtk.RadioButton.__init__(self)
		self.group = ''
		if len(gui.gui.__radio_groups__[self.group]) > 0:
			self.set_group(gui.gui.__radio_groups__[self.group][0])
		gui.gui.__radio_groups__[self.group].append(self)
		def get(): # {{{
			if self.get_inconsistent():
				return None
			return self.get_active()
		# }}}
		def get_group(): # {{{
			return self.group
		# }}}
		def set(value): # {{{
			if value is None:
				self.set_inconsistent(True)
			else:
				self.set_inconsistent(False)
				self.set_active(as_bool(value))
		# }}}
		def set_group(group): # {{{
			gui.gui.__radio_groups__[self.group].remove(self)
			if self.group != '' and len(gui.gui.__radio_groups__[self.group]) == 0:
				del gui.gui.__radio_groups__[self.group]
			if group in gui.gui.__radio_groups__:
				self.set_group(gui.gui.__radio_groups__[group][0])
			else:
				self.set_group(None)
				gui.gui.__radio_groups__[group] = []
			gui.gui.__radio_groups__[group].append(self)
			self.group = group
		# }}}
		gui.register_attribute('value', get, set)
		gui.register_attribute('group', get_group, set_group)
		gui.register_gtk_event('toggled')
		gui.add()
builtins['RadioButton'] = RadioButton
#}}}
class Entry(gtk.Entry): # {{{
	def __init__(self, gui):
		gtk.Entry.__init__(self)
		gui.assert_children(0)
		gui.register_attribute('value', self.get_text, self.set_text)
		gui.register_gtk_event('activate')
		gui.register_gtk_event('changed')
builtins['Entry'] = Entry
#}}}
class Frame(gtk.Frame): # {{{
	def __init__(self, gui):
		gtk.Frame.__init__(self)
		gui.register_attribute('label', self.get_label, lambda value: self.set_label(None if value == '' else value))
		gui.add()
builtins['Frame'] = Frame
# }}}
class Table(gtk.Table): # {{{
	def __init__(self, gui):
		cols = int(gui.get_attribute('columns', default = 1))
		gtk.Table.__init__(self, 1, cols)
		gui.table_add()
builtins['Table'] = Table
#}}}
class SpinButton(gtk.SpinButton): # {{{
	def __init__(self, gui):
		gtk.SpinButton.__init__(self)
		gui.assert_children(0)
		self.set_increments(1, 10)
		gui.register_attribute('range', self.get_range, lambda r: self.set_range(*parse_nums(r)))
		gui.register_attribute('value', self.get_value, lambda v: self.set_value(float(v)))
		gui.register_attribute('increment', self.get_increments, lambda r: self.set_increments(*parse_nums(r)))
		gui.register_gtk_event('value-changed')
builtins['SpinButton'] = SpinButton
#}}}
class ComboBoxText(gtk.ComboBox): # {{{
	def __init__(self, gui):
		def setcontent(value): # {{{
			if isinstance(value, str):
				l = value.split('\n')
			else:
				l = value
			self.get_model().clear()
			for i in l:
				self.get_model().append((i.strip(),))
		# }}}
		def set(value): # {{{
			def fill(model, path, iter, d): # {{{
				d += (model.get_value(iter, 0),)
				return False
			# }}}
			d = []
			self.get_model().foreach(fill, d)
			if value in d:
				self.set_active(d.index(value))
			else:
				self.get_model().append((value,))
				self.set_active(len(d))
		# }}}
		gtk.ComboBox.__init__(self, gtk.ListStore(str))
		renderer = gtk.CellRendererText()
		self.pack_start(renderer)
		self.add_attribute(renderer, 'text', 0)
		gui.assert_children(0, 1)
		if len(gui.desc.children) > 0:
			if nice_assert(gui.desc.children[0].tag == 'Label' and gui.desc.children[0].attributes['value'].startswith(':'), 'ComboBoxText child must be a Label'):
				setcontent(gui.desc.children[0].attributes['value'][1:])
		gui.register_attribute('content', None, setcontent)
		gui.register_attribute('value', self.get_active, self.set_active)
		gui.register_attribute('text', lambda: (self.get_model().get_value(self.get_active_iter(), 0) if self.get_active_iter() is not None else ''), set)
		gui.register_gtk_event('changed')
builtins['ComboBoxText'] = ComboBoxText
#}}}
class ComboBoxEntryText(gtk.ComboBoxEntry): # {{{
	def __init__(self, gui):
		def setcontent(value): # {{{
			if isinstance(value, str):
				l = value.split('\n')
			else:
				l = value
			self.get_model().clear()
			for i in l:
				self.get_model().append((i.strip(),))
		# }}}
		def set(value): # {{{
			def fill(model, path, iter, d): # {{{
				d += (model.get_value(iter, 0),)
				return False
			# }}}
			d = []
			self.get_model().foreach(fill, d)
			if value in d:
				self.set_active(d.index(value))
			else:
				self.get_model().append((value,))
				self.set_active(len(d))
		# }}}
		gtk.ComboBoxEntry.__init__(self, gtk.ListStore(str))
		gui.assert_children(0, 1)
		if len(gui.desc.children) > 0:
			if nice_assert(gui.desc.children[0].tag == 'Label' and gui.desc.children[0].attributes['value'].startswith(':'), 'ComboBoxEntryText child must be a Label'):
				setcontent(gui.desc.children[0].attributes['value'][1:])
		gui.register_attribute('content', None, setcontent)
		gui.register_attribute('value', self.get_active, self.set_active)
		gui.register_attribute('text', self.child.get_text, set)
		gui.register_gtk_event('changed')
		gui.register_gtk_event('activate', gtk_widget = self.child)
builtins['ComboBoxEntryText'] = ComboBoxEntryText
#}}}
class FileChooser: # Base class for FileChooserButton and FileChooserDialog.{{{
	def __init__(self, gui, signal, hide):
		self.hide = hide
		gui.assert_children(0)
		def set_action(value): # {{{
			if value == 'open':
				self.set_action(gtk.FILE_CHOOSER_ACTION_OPEN)
			elif value == 'save':
				self.set_action(gtk.FILE_CHOOSER_ACTION_SAVE)
			elif value == 'select_folder':
				self.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
			elif value == 'create_folder':
				self.set_action(gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER)
			else:
				error('invalid action type %s for FileChooser' % value)
		# }}}
		def get_action(): # {{{
			a = self.get_action()
			if a == gtk.FILE_CHOOSER_ACTION_OPEN:
				return 'open'
			if a == gtk.FILE_CHOOSER_ACTION_SAVE:
				return 'save'
			if a == gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER:
				return 'select_folder'
			if a == gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER:
				return 'create_folder'
			error('invalid action type for FileChooser')
		# }}}
		gui.register_attribute('title', self.get_title, self.set_title)
		gui.register_attribute('action', get_action, set_action)
		gui.register_attribute('filename', self.get_filename, self.set_filename)
		gui.register_bool_attribute('overwrite_confirmation', self.get_do_overwrite_confirmation, self.set_do_overwrite_confirmation)
		v = gui.register_event('response')
		if v is not None:
			def response(widget, r, dummy = None): # {{{
				if self.hide:
					widget.hide()
				v(self.get_filename() if r == gtk.RESPONSE_ACCEPT else None)
			# }}}
			# A FileChooserDialog provides a response and fills the dummy argument; a FileChooserButton doesn't provide a response, puts ACCEPT there, and omits the dummy argument.
			self.connect(signal, response, gtk.RESPONSE_ACCEPT)
class FileChooserButton(FileChooser, gtk.FileChooserButton): # {{{
	def __init__(self, gui):
		gtk.FileChooserButton.__init__(self, '')
		FileChooser.__init__(self, gui, 'file-set', False)
builtins['FileChooserButton'] = FileChooserButton
# }}}
class FileChooserDialog(FileChooser, gtk.FileChooserDialog): # {{{
	gtk_window = True
	def __init__(self, gui):
		gtk.FileChooserDialog.__init__(self, '', buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		FileChooser.__init__(self, gui, 'response', True)
builtins['FileChooserDialog'] = FileChooserDialog
# }}}
# }}}
class HSeparator(gtk.HSeparator): # {{{
	def __init__(self, gui):
		gtk.HSeparator.__init__(self)
		gui.assert_children(0)
builtins['HSeparator'] = HSeparator
#}}}
class VSeparator(gtk.VSeparator): # {{{
	def __init__(self, gui):
		gtk.VSeparator.__init__(self)
		gui.assert_children(0)
builtins['VSeparator'] = VSeparator
#}}}
class VScale(gtk.VScale): # {{{
	def __init__(self, gui):
		gtk.VScale.__init__(self)
		gui.assert_children(0)
		gui.register_attribute('digits', self.get_digits, lambda v: self.set_digits(int(v)))
		gui.register_attribute('draw_value', self.get_draw_value, lambda v: self.set_draw_value(as_bool(v)))
		pos2str = {gtk.POS_LEFT: 'left', gtk.POS_RIGHT: 'right', gtk.POS_TOP: 'top', gtk.POS_BOTTOM: 'bottom'}
		str2pos = {'left': gtk.POS_LEFT, 'right': gtk.POS_RIGHT, 'top': gtk.POS_TOP, 'bottom': gtk.POS_BOTTOM}
		gui.register_attribute('value_pos', lambda: pos2str[self.get_value_pos()], lambda v: self.set_value_pos(str2pos[v]))
		# marks
		self.set_data('marks', [])
		def set_marks(marks):
			self.set_data('marks', marks)
			self.clear_marks()
			for m in marks:
				self.add_mark(m[0], str2pos[m[1]], m[2])
		gui.register_attribute('marks', lambda: self.get_data('marks'), set_marks)
		self.set_increments(1, 10)
		gui.register_attribute('range', (self.get_adjustment().get_lower(), self.get_adjustment().get_upper()), lambda r: self.set_range(*parse_nums(r)))
		gui.register_attribute('value', self.get_value, lambda v: self.set_value(float(v)))
		gui.register_attribute('increment', (self.get_adjustment().get_step_increment(), self.get_adjustment().get_page_increment()), lambda r: self.set_increments(*parse_nums(r)))
		gui.register_gtk_event('value-changed')

builtins['VScale'] = VScale
#}}}
class HScale(gtk.HScale): # {{{
	def __init__(self, gui):
		gtk.HScale.__init__(self)
		gui.assert_children(0)
		gui.register_attribute('digits', self.get_digits, lambda v: self.set_digits(int(v)))
		gui.register_attribute('draw_value', self.get_draw_value, lambda v: self.set_draw_value(as_bool(v)))
		pos2str = {gtk.POS_LEFT: 'left', gtk.POS_RIGHT: 'right', gtk.POS_TOP: 'top', gtk.POS_BOTTOM: 'bottom'}
		str2pos = {'left': gtk.POS_LEFT, 'right': gtk.POS_RIGHT, 'top': gtk.POS_TOP, 'bottom': gtk.POS_BOTTOM}
		gui.register_attribute('value_pos', lambda: pos2str[self.get_value_pos()], lambda v: self.set_value_pos(str2pos[v]))
		# marks
		self.set_data('marks', [])
		def set_marks(marks):
			self.set_data('marks', marks)
			self.clear_marks()
			for m in marks:
				self.add_mark(m[0], str2pos[m[1]], m[2])
		gui.register_attribute('marks', lambda: self.get_data('marks'), set_marks)
		self.set_increments(1, 10)
		gui.register_attribute('range', (self.get_adjustment().get_lower(), self.get_adjustment().get_upper()), lambda r: self.set_range(*parse_nums(r)))
		gui.register_attribute('value', self.get_value, lambda v: self.set_value(float(v)))
		gui.register_attribute('increment', (self.get_adjustment().get_step_increment(), self.get_adjustment().get_page_increment()), lambda r: self.set_increments(*parse_nums(r)))
		gui.register_gtk_event('value-changed')

builtins['HScale'] = HScale
#}}}
class MenuBar: # {{{
	def __init__(self, gui):
		ui = gtk.UIManager()
		gui.gui.__accel_groups__.append(ui.get_accel_group())
		actiongroup = gtk.ActionGroup('actiongroup')
		childdesc, actions = gui.parse_menubar()
		actiongroup.add_actions(actions)
		ui.add_ui_from_string('<ui><menubar>' + childdesc + '</menubar></ui>')
		ui.insert_action_group(actiongroup)
		self.return_object = ui.get_widget('/menubar')
builtins['MenuBar'] = MenuBar
#}}}
class HPaned(gtk.HPaned): # {{{
	def __init__(self, gui):
		gtk.HPaned.__init__(self)
		gui.assert_children(2)
		gui.paned_add()
builtins['HPaned'] = HPaned
#}}}
class VPaned(gtk.VPaned): # {{{
	def __init__(self, gui):
		gtk.VPaned.__init__(self)
		gui.assert_children(2)
		gui.paned_add()
builtins['VPaned'] = VPaned
#}}}
class Statusbar(gtk.Statusbar): # {{{
	def __init__(self, gui):
		gtk.Statusbar.__init__(self)
		gui.assert_children(0)
		self.value = ''
		self.push(0, self.value)
		def set(v): # {{{
			self.pop(0)
			self.value = v
			self.push(0, self.value)
		# }}}
		gui.register_attribute('text', lambda: self.value, set)
builtins['Statusbar'] = Statusbar
#}}}
class Image(gtk.Image): # {{{
	def __init__(self, gui):
		gtk.Image.__init__(self)
		gui.assert_children(0)
		gui.register_attribute('pixbuf', self.get_pixbuf, self.set_from_pixbuf)
builtins['Image'] = Image
#}}}
class TextView(gtk.TextView): # {{{
	def __init__(self, gui):
		gtk.TextView.__init__(self)
		gui.assert_children(0)
		gui.register_attribute('text', lambda: self.get_text(self.get_buffer().get_start_iter(), self.get_buffer().get_end_iter()), self.get_buffer().set_text)
		wrap_modes = {gtk.WRAP_NONE: 'none', gtk.WRAP_CHAR: 'char', gtk.WRAP_WORD: 'word', gtk.WRAP_WORD_CHAR: 'word_char'}
		gui.register_attribute('wrap_mode', lambda: wrap_modes[self.get_wrap_mode()], lambda x: self.set_wrap_mode([t[0] for t in wrap_modes.items() if t[1] == x][0]))
		gui.register_bool_attribute('editable', self.get_editable, self.set_editable)
builtins['TextView'] = TextView
#}}}
class External: # {{{
	def __init__(self, gui):
		gui.assert_children(0)
		id = gui.get_attribute('id')
		if not nice_assert(id is not None, 'id of External must be defined') or not nice_assert(id in gui.gui.__gtk__, 'Unknown external object %s defined' % id):
			self.return_object = None
			return
		self.return_object = gui.gui.__gtk__.pop(id)
builtins['External'] = External
#}}}
#}}}

class Gui: # {{{
	'''Main class for toolkit-independent gui module.'''
	__widgets__ = {}
	class __element__: # {{{
		'''Internal class for holding gui elements.'''
		def __init__(self, tag, attributes, children): # {{{
			'''Initialize an element.'''
			self.tag = tag
			self.attributes = attributes
			self.children = children
		# }}}
		def dump(self, indent): # {{{
			'''Dump the element to screen, including children, for debugging.'''
			ret = indent + '<' + self.tag
			for a in self.attributes.keys():
				ret += ' ' + a + '="' + self.attributes[a].replace('&', '&amp;').replace('"', '&quot;') + '"'
			if len(self.children) == 0:
				return ret + '/>\n'
			ret += '>\n'
			for c in self.children:
				ret += c.dump(indent + '\t')
			return ret + indent + '</' + self.tag + '>\n'
		# }}}
		def __repr__(self): # {{{
			'''Use the dump function when a string representation is requested.'''
			return self.dump('')
		# }}}
	# }}}
	def __parse__(self, element): # {{{
		'''Internal function for parsing the contents of an element.'''
		ret = self.__element__(element.tag, element.attrib, [])
		if element.text and element.text.strip():
			ret.children += (self.__element__('Label', {'value': ':' + element.text.strip()}, []),)
		for c in element.getchildren():
			ret.children += (self.__parse__(c),)
			if c.tail and c.tail.strip():
				ret.children += (self.__element__('Label', {'value': ':' + c.tail.strip()}, []),)
		return ret
	# }}}
	def __init__(self, packagename = None, execname = None, gtk = {}, widgets = (), events = {}, inputs = (), outputs = (), data = None): # {{{
		'''Initialize the gui object.
		name is the program name, which defaults to basename(sys.argv[0])
		gtk is a list of gtk-specific objects which cannot be defined otherwise.
		Note that using gtk objects binds the application to the gtk toolkit.
		events is a dict linking all possible events to their callback.
		inputs and outputs are sequences listing all input and output attributes.
		
		If the gui interface description cannot be found, a simple
		interface is constructed containing a button for each event,
		an entry for each input and a label for each output.'''
		self.__data__ = data
		if isinstance(widgets, dict):
			self.__widgets__ = [widgets, builtins]
		else:
			self.__widgets__ = list(widgets) + [builtins]
		self.__menuaction__ = 0
		self.__event__ = {}
		self.__get__ = {}
		self.__set__ = {}
		self.__defs__ = {}
		self.__radio_groups__ = {'': []}
		self.__loop_return__ = None
		if not execname:
			execname = os.path.basename(sys.argv[0])
			e = os.extsep + 'py'
			if execname.endswith(e):
				execname = execname[:-len(e)]
		if not packagename:
			packagename = execname
		self.__packagename__ = packagename
		self.__execname__ = execname
		self.__gtk__ = gtk
		self.__building__ = True
		filename = find_path(execname + os.extsep + 'gui', packagename)
		if filename is None:
			customs = []
			for g in gtk:
				customs.append(self.__element__('VBox', {}, [self.__element__('Label', {'value': ':' + g}, []), self.__element__('External', {'id': g}, [])]))
			entries = []
			for i in inputs:
				entries.append(self.__element__('HBox', {}, [self.__element__('Label', {'value': ':' + i + ':'}, []), self.__element__('Entry', {'value': i}, [])]))
			labels = []
			for o in outputs:
				labels.append(self.__element__('HBox', {}, [self.__element__('Label', {'value': ':' + o + ':'}, []), self.__element__('Label', {'value': o}, [])]))
			buttons = []
			for e in events:
				buttons.append(self.__element__('Button', {'clicked': e}, [self.__element__('Label', {'value': ':' + e}, [])]))
			columns = [self.__element__('VBox', {}, x) for x in(entries, labels, buttons) if len(x) > 0]
			content = columns if len(columns) == 1 else [self.__element__('HBox', {}, columns)]
			if len(customs) > 0:
				content = [self.__element__('VBox', {}, [self.__element__('HBox', {}, customs), content[0]])]
			tree = self.__element__('gtk', {}, [self.__element__('Window', {}, columns if len(columns) == 1 else [self.__element__('HBox', {}, columns)])])
			filename = os.getenv('GUI_SAVE_INTERFACE_FILENAME')
			if filename:
				with open(filename, 'wb') as f:
					f.write(repr(tree))
		else:
			tree = ET.parse(filename)
			root = tree.getroot()
			nice_assert(not root.tail or not root.tail.strip(), 'unexpected data at end of gui description')
			tree = self.__parse__(root)

		nice_assert(tree.tag == 'gtk', 'gui description top level element is not <gtk>')
		self.__windows__ = []
		nice_assert(tree.attributes == {}, 'no attributes are allowed on top level tag')
		# Find all defs.
		i = 0
		while i < len(tree.children):
			w = tree.children[i]
			if w.tag != 'def':
				# Apply defs.
				i += self.__apply_defs__(tree, i)
				continue
			if nice_assert('name' in w.attributes, 'def requires a name attribute'):
				self.__defs__[w.attributes['name']] = w.children
			i += 1
		# Build the interface.
		self.__accel_groups__ = []
		for w in tree.children:
			if w.tag == 'def':
				continue
			win = self.__build__(w)
			if win is None:
				continue
			if not nice_assert(hasattr(win, 'gtk_window'), 'top-level elements must be windows'):
				continue
			for ag in self.__accel_groups__:
				win.add_accel_group(ag)
			self.__windows__.append(win)
		nice_assert(len(self.__windows__) > 0, 'there are no gui elements defined', exit = True)
		for w in self.__windows__:
			w.connect('destroy', lambda x: self(False, None))
		# Reverse order, so first defined window is shown last, therefore(most likely) on top
		self.__windows__.reverse()
		nice_assert(self.__gtk__ == {}, 'Not all externally provided widgets were used: ' + str(self.__gtk__))
		del self.__gtk__
		# Check that only declared inputs, (__get__ has the same keys as __set__) and events are used.
		for name in self.__get__:
			nice_assert(name in inputs or name in outputs and name in self.__set__, 'undeclared name %s used in the gui(or output used as input)' % name)
		for name in self.__set__:
			nice_assert(name in inputs and name in self.__get__ or name in outputs, 'undeclared name %s used in the gui(or input used as output)' % name)
		for name in self.__event__:
			nice_assert(name in events, 'undeclared event name %s used in the gui' % name)
		# Check that all used names are declared.
		for i in inputs:
			for o in outputs:
				nice_assert(i != o, 'duplicate name %s used for input and output' % i)
		nice_assert(len(inputs) == len(set(inputs)), 'one or more duplicate names in inputs')
		nice_assert(len(outputs) == len(set(outputs)), 'one or more duplicate names in outputs')
		# Check that all declared names are used.
		for name in inputs:
			nice_assert(name in self.__get__, 'input name %s is not in the gui' % name)
		for name in outputs:
			nice_assert(name in self.__set__, 'output name %s is not in the gui' % name)
		# Register provided events.
		for name in events:
			if not nice_assert(name in self.__event__, 'event name %s is not in the gui' % name):
				continue
			value = events[name]
			if isinstance(value, (tuple, list)):
				if nice_assert(len(value) == 2, 'setting event to list or tuple, but length is not 2'):
					self.__event__[name][0] = value[0]
					self.__event__[name][1] = value[1]
			else:
				self.__event__[name][0] = value
				self.__event__[name][1] = None
		self.__building__ = False
	# }}}
	def __copy_def__(self, tags, attrs): # {{{
		ret = []
		for t in tags:
			rattrs = {}
			for a in t.attributes:
				val = t.attributes[a]
				if ':' in val:
					n, d = val.split(':', 1)
					if n in attrs:
						if ':' in attrs[n]:
							rattrs[a] = attrs[n]
						else:
							rattrs[a] = '%s:%s' % (attrs[n], d)
					else:
						rattrs[a] = val
				elif val in attrs:
					rattrs[a] = attrs[val]
				else:
					rattrs[a] = val
			children = self.__copy_def__(t.children, attrs)
			ret.append(self.__element__(t.tag, rattrs, children))
		return ret
	# }}}
	def __apply_defs__(self, parent, idx): # {{{
		# Recursively replace parent.children[idx] with defined stuff, if any. Return new number of elements.
		if parent.children[idx].tag in self.__defs__:
			nice_assert(len(parent.children[idx].children) == 0, 'Macros must not have child elements')
			subst = self.__copy_def__(self.__defs__[parent.children[idx].tag], parent.children[idx].attributes)
			parent.children[idx:idx + 1] = subst
			return 0
		i = 0
		while i < len(parent.children[idx].children):
			i += self.__apply_defs__(parent.children[idx], i)
		return 1
	# }}}
	def __event_cb__(self, object, *args, **kwargs): # {{{
		'''Internal callback for gui events.'''
		if self.__event__[args[-1]][0] is not None:
			f = self.__event__[args[-1]][0]
			if self.__event__[args[-1]][1] is not None:
				args = list(args) + [self.__event__[args[-1]][1]]
			f(*args[:-1], **kwargs)
	# }}}
	def __getattr__(self, name): # {{{
		'''Get the value of a get variable.'''
		if not name in self.__get__:
			raise AttributeError
		if self.__get__[name][0] is None:
			return self.__get__[name][1]
		if self.__get__[name][1] is NO_ARG:
			return self.__get__[name][0] ()
		else:
			return self.__get__[name][0] (self.__get__[name][1])
	# }}}
	def __setattr__(self, name, value): # {{{
		'''Set the value of a set variable.'''
		if name.startswith('_'):
			self.__dict__[name] = value
		elif name in self.__set__:
			if self.__set__[name][1] is NO_ARG:
				self.__set__[name][0] (value)
			else:
				self.__set__[name][0] (self.__set__[name][1], value)
		else:
			error('not setting ' + name + ", because it isn't defined in the gui")
	# }}}
	def __build__(self, desc, fromparent = None): # {{{
		'''Internal function to create a widget, including contents.'''
		def show(w, value): # {{{
			if as_bool(value):
				w.show()
			else:
				w.hide()
		# }}}
		def showwin(w, value): # {{{
			w.set_data('show', as_bool(value))
			if not self.__building__:
				show(w, value)
		# }}}
		for w in self.__widgets__:
			if desc.tag in w:
				widget = w[desc.tag]
				break
		else:
			error('no widget named %s defined' % desc.tag)
			return None
		wrap = Wrapper.create(self, desc, widget, self.__data__)
		ret = wrap.widget
		if hasattr(ret, 'return_object'):
			ret = ret.return_object
			if ret is None:
				if desc.attributes != {}:
					error('unused attributes for ' + desc.tag + ': ' + str(desc.attributes))
				return None
		if not hasattr(ret, 'gtk_window'):
			ret.show()
			wrap.register_attribute('show', ret.get_visible, lambda x: show(ret, x))
		else:
			wrap.register_attribute('show', lambda: ret.get_data('show'), lambda x: showwin(ret, x))
		wrap.register_attribute('sensitive', ret.get_sensitive, lambda x: ret.set_sensitive(as_bool(x)))
		wrap.register_attribute('can_focus', ret.get_can_focus, lambda x: ret.set_can_focus(as_bool(x)))
		if fromparent != None:
			for k in fromparent:
				wrap.register_attribute(k, fromparent[k][0], fromparent[k][1], ret)
		if desc.attributes != {}:
			error('unused attributes for ' + desc.tag + ': ' + str(desc.attributes))
		return ret
	# }}}
	def __call__(self, run = True, ret = None): # {{{
		'''Run the main loop.'''
		if run:
			for w in self.__windows__:
				if w.get_data('show') == True:	# True means show, None and False mean hide.
					w.show()
			if run is True:
				gtk.main()
			else:
				while gtk.events_pending():
					gtk.main_iteration(False)
			return self.__loop_return__
		else:
			self.__loop_return__ = ret
			gtk.main_quit()
	# }}}
# }}}
