#!/usr/bin/env python

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

import sys
import os
import xml.etree.ElementTree as ET
import gtk

class gui:
	class __element:
		def __init__ (self, tag, attributes, children):
			self.tag = tag
			self.attributes = attributes
			self.children = children
		def dump (self, indent):
			ret = indent + '<' + self.tag
			for a in self.attributes.keys ():
				ret += ' ' + a + '="' + self.attributes[a].replace ('&', '&amp;').replace ('"', '&quot;') + '"'
			if len (self.children) == 0:
				return ret + '/>\n'
			ret += '>\n'
			for c in self.children:
				ret += c.dump (indent + '\t')
			return ret + indent + '</' + self.tag + '>\n'
		def __repr__ (self):
			return self.dump ('')
	def __parse (self, element):
		ret = self.__element (element.tag, element.attrib, [])
		if element.text and element.text.strip ():
			ret.children += (self.__element ('Label', {'value': ':' + element.text.strip ()}, []),)
		for c in element.getchildren ():
			ret.children += (self.__parse (c),)
			if c.tail and c.tail.strip ():
				ret.children += (self.__element ('Label', {'value': ':' + c.tail.strip ()}, []),)
		return ret
	def __init__ (self, name = None, external = {}):
		self.__event = {}
		self.__get = {}
		self.__set = {}
		self.__settings = {}
		if not name:
			name = os.path.basename (sys.argv[0])
		self.__name = name
		self.__external = external
		# TODO: search for name.gui
		tree = ET.parse (name + '.gui')
		root = tree.getroot ()
		assert not root.tail or not root.tail.strip ()
		tree = self.__parse (root)

		assert tree.tag == 'gtk'
		while tree.children[0].tag == 'Set':
			self.__settings[tree.children[0].attributes['name']] = tree.children[0].attributes['value']
			del tree.children[0]
		self.__windows = []
		assert len (tree.children) > 0
		if tree.children[0].tag != 'Window':
			tree = self.__element (tree.tag, {}, [self.__element ('Window', tree.attributes, tree.children)])
		assert tree.attributes == {}
		for w in tree.children:
			assert w.tag == 'Window'
			self.__windows += (self.__build (w),)
		for w in self.__windows:
			w.connect ('destroy', self.__destroy)
		# Reverse order, so first defined window is shown last, therefore (most likely) on top
		self.__windows.reverse ()
		if self.__external != {}:
			print 'Not all externally provided widgets were used: ' + str (self.__external)
		del self.__external
	def __getitem__ (self, key):
		return self.__settings[key]
	def __event_cb (self, object, name):
		if self.__event[name][0] != None:
			f = self.__event[name][0]
			if f.__code__.co_argcount > 0:
				f (self.__event[name][1])
			else:
				f ()
	def __add_event (self, desc, event, widget, name = None):
		if name == None:
			name = event
		if name not in desc.attributes:
			return
		value = desc.attributes[name]
		del desc.attributes[name]
		assert value not in self.__get and value not in self.__set
		if value not in self.__event:
			self.__event[value] = [None, None]
		widget.connect (event, self.__event_cb, value)
	def __add_custom_event (self, desc, name):
		if name not in desc.attributes:
			return None
		value = desc.attributes[name]
		del desc.attributes[name]
		assert value not in self.__get and value not in self.__set
		if value not in self.__event:
			self.__event[value] = [None, None]
		return value
	def __add_get (self, desc, name, cb, arg):
		if name not in desc.attributes:
			return
		value = desc.attributes[name]
		del desc.attributes[name]
		assert value not in self.__get and value not in self.__set and value not in self.__event
		self.__get[value] = (cb, arg)
	def __add_set (self, desc, name, cb, arg, default = None):
		if name not in desc.attributes:
			if default != None:
				cb (default, arg)
			return
		value = desc.attributes[name]
		del desc.attributes[name]
		pos = value.find (':')
		if pos >= 0:
			cb (value[pos + 1:], arg)
			value = value[:pos]
		else:
			if default != None:
				cb (default, arg)
		if value == '':
			return
		assert value not in self.__get and value not in self.__set and value not in self.__event
		self.__set[value] = (cb, arg)
	def __getattr__ (self, name, arg = None):
		if name not in self.__get:
			print name
		assert name in self.__get
		if self.__get[name][0] != None:
			return self.__get[name][0] (self.__get[name][1], arg)
		else:
			return self.__get[name][1]
	def __setattr__ (self, name, value):
		if name.startswith ('_'):
			self.__dict__[name] = value
			return value
		if name in self.__event:
			if type (value) == tuple or type (value) == list:
				assert len (value) == 2
				self.__event[name][0] = value[0]
				self.__event[name][1] = value[1]
			else:
				self.__event[name][0] = value
				self.__event[name][1] = None
		elif name in self.__set:
			self.__set[name][0] (value, self.__set[name][1])
		else:
			print 'Not setting ' + name + ", because it isn't defined in the gui"
	def __destroy (self, w):
		gtk.main_quit ()
	def __build_add (self, desc, parent):
		assert len (desc.children) == 1
		child = self.__build (desc.children[0])
		parent.add (child)
	def __as_bool (self, value):
		if type (value) == str:
			assert value == 'True' or value == 'False'
			return value == 'True'
		return bool (value)
	def __build_pack (self, desc, parent):
		def expand (value, widget):
			widget.set_data ('expand', self.__as_bool (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			widget.set_child_packing (parent, widget.get_data ('expand'), widget.get_data ('fill'), 0, gtk.PACK_START)
		def fill (value, widget):
			widget.set_data ('fill', self.__as_bool (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			widget.set_child_packing (parent, widget.get_data ('expand'), widget.get_data ('fill'), 0, gtk.PACK_START)
		for c in desc.children:
			x = self.__build (c, {'expand': expand, 'fill': fill})
			if x.get_data ('expand') == None:
				x.set_data ('expand', True)
			if x.get_data ('fill') == None:
				x.set_data ('fill', True)
			parent.pack_start (x, x.get_data ('expand'), x.get_data ('fill'))
	def __build_noteadd (self, desc, parent):
		def setpage (value, widget):
			parent.set_data ('page', widget)
			p = widget.get_parent ()
			if p == None:
				return
			p.set_current_page (p.page_num (widget))
		def setlabel (value, widget):
			widget.set_data ('label', value)
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.set_tab_label_text (widget, value)
		for c in desc.children:
			x = self.__build (c, {'setpage': setpage, 'set_label': setlabel})
			parent.append_page (x)
			label = x.get_data ('label')
			if label != None:
				parent.set_tab_label_text (x, label)
		page = parent.get_data ('page')
		if page != None:
			parent.set_current_page (parent.page_num (page))
	def __build_attach (self, desc, parent):
		def parse (value):
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
			assert w == []
			return v
		def xset (value, widget):
			widget.set_data ('xopts', parse (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'x-options', widget.get_data ('xopts'))
		def yset (value, widget):
			widget.set_data ('yopts', parse (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'y-options', widget.get_data ('yopts'))
		def lset (value, widget):
			widget.set_data ('left', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'left-attach', widget.get_data ('left'))
		def rset (value, widget):
			widget.set_data ('right', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'right-attach', widget.get_data ('right'))
		def tset (value, widget):
			widget.set_data ('top', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'top-attach', widget.get_data ('top'))
		def bset (value, widget):
			widget.set_data ('bottom', int (value))
			parent = widget.get_parent ()
			if parent == None:
				return
			parent.child_set_property (widget, 'bottom-attach', widget.get_data ('bottom'))
		cols = parent.get_property ('n-columns')
		current = [0, 0]
		for c in desc.children:
			x = self.__build (c, {'x-options': xset, 'y-options': yset, 'left': lset, 'right': rset, 'top': tset, 'bottom': bset})
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
	def __build (self, desc, fromparent = None):
		if desc.tag == 'Window':
			ret = gtk.Window ()
			def set_title (value, window):
				window.set_title (value)
			self.__add_set (desc, 'title', set_title, ret, self.__name)
			self.__build_add (desc, ret)
		elif desc.tag == 'VBox':
			ret = gtk.VBox ()
			self.__build_pack (desc, ret)
		elif desc.tag == 'HBox':
			ret = gtk.HBox ()
			self.__build_pack (desc, ret)
		elif desc.tag == 'Notebook':
			ret = gtk.Notebook ()
			def show_tabs (value, notebook):
				notebook.set_show_tabs (self.__as_bool (value))
			self.__add_set (desc, 'show_tabs', show_tabs, ret)
			self.__build_noteadd (desc, ret)
		elif desc.tag == 'Label':
			ret = gtk.Label ()
			def set (value, label):
				label.set_text (value)
			self.__add_set (desc, 'value', set, ret)
		elif desc.tag == 'Button':
			assert len (desc.children) == 1
			ret = gtk.Button ()
			self.__add_event (desc, 'clicked', ret)
			self.__build_add (desc, ret)
		elif desc.tag == 'CheckButton':
			assert len (desc.children) == 1
			ret = gtk.CheckButton ()
			def get (checkbutton, junk):
				return checkbutton.get_active ()
			def set (value, checkbutton):
				checkbutton.set_active (self.__as_bool (value))
			self.__add_get (desc, 'value', get, ret)
			self.__add_set (desc, 'set', set, ret)
			self.__add_event (desc, 'toggled', ret)
			self.__build_add (desc, ret)
		elif desc.tag == 'Entry':
			assert len (desc.children) == 0
			ret = gtk.Entry ()
			def set (value, entry):
				entry.set_text (value)
			def get (entry, junk):
				return entry.get_text ()
			self.__add_set (desc, 'set', set, ret)
			self.__add_get (desc, 'value', get, ret)
			self.__add_event (desc, 'activate', ret)
			self.__add_event (desc, 'changed', ret)
		elif desc.tag == 'Frame':
			assert len (desc.children) == 1
			ret = gtk.Frame ()
			def set (value, frame):
				if value == '':
					frame.set_label (None)
				else:
					frame.set_label (value)
			self.__add_set (desc, 'label', set, ret)
			self.__build_add (desc, ret)
		elif desc.tag == 'Table':
			if 'columns' in desc.attributes:
				cols = int (desc.attributes['columns'])
				del desc.attributes['columns']
			else:
				cols = 1
			ret = gtk.Table (1, cols)
			self.__build_attach (desc, ret)
		elif desc.tag == 'FileChooserButton':
			ret = gtk.FileChooserButton ('')
			def title (value, button):
				button.set_title (value)
			def get (button, junk):
				return button.get_filename ()
			self.__add_set (desc, 'title', title, ret)
			self.__add_get (desc, 'value', get, ret)
		elif desc.tag == 'SpinButton':
			ret = gtk.SpinButton ()
			def setrange (value, button):
				min, max = value.split (',')
				button.set_range (float (min), float (max))
			def get (button, junk):
				return button.get_value ()
			def set (value, button):
				return button.set_value (float (value))
			def increment (value, button):
				return button.set_increments (*[float (x) for x in value.split (',')])
			ret.set_increments (1, 10)
			self.__add_set (desc, 'range', setrange, ret)
			self.__add_set (desc, 'set', set, ret)
			self.__add_set (desc, 'increment', increment, ret)
			self.__add_get (desc, 'value', get, ret)
			self.__add_event (desc, 'value-changed', ret)
		elif desc.tag == 'ComboBoxText' or desc.tag == 'ComboBoxEntryText':
			if desc.tag == 'ComboBoxText':
				ret = gtk.combo_box_new_text ()
			else:
				ret = gtk.combo_box_entry_new_text ()
			def setcontent (value, box):
				if type (value) == str:
					l = value.split ('\n')
				else:
					l = value
				while box.get_model ().get_iter_first () != None:
					box.remove_text (0)
				for i in l:
					box.append_text (i.strip ())
			def get (box, junk):
				return box.get_active_text ()
			def set (value, box):
				def fill (model, path, iter, d):
					d += (model.get_value (iter, 0),)
					return False
				d = []
				box.get_model ().foreach (fill, d)
				if value in d:
					box.set_active (d.index (value))
				else:
					box.append_text (value)
					box.set_active (len (d))
			if len (desc.children) > 0:
				assert len (desc.children) == 1 and desc.children[0].tag == 'Label'
				setcontent (desc.children[0].attributes['value'].split (':', 1)[1], ret)
				ret.set_active (0)
			self.__add_set (desc, 'content', setcontent, ret)
			self.__add_set (desc, 'set', set, ret)
			self.__add_get (desc, 'value', get, ret)
			self.__add_event (desc, 'changed', ret)
			if desc.tag == 'ComboBoxEntryText':
				v = self.__add_custom_event (desc, 'activate')
				if v != None:
					ret.child.connect ('activate', self.__event_cb, v)
		elif desc.tag == 'HSeparator':
			ret = gtk.HSeparator ()
		elif desc.tag == 'External':
			assert len (desc.children) == 0
			ret = self.__external[desc.attributes['id']]
			del self.__external[desc.attributes['id']]
			del desc.attributes['id']
		else:
			raise AssertionError ('invalid tag ' + desc.tag)
		if fromparent != None:
			for k in fromparent:
				self.__add_set (desc, k, fromparent[k], ret)
		if desc.attributes != {}:
			raise AssertionError ('unused attributes for ' + desc.tag + ': ' + str (desc.attributes))
		return ret

	def __call__ (self):
		for w in self.__windows:
			w.show_all ()
		gtk.main ()

def quit ():
	gtk.main_quit ()
