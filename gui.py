#!/usr/bin/env python

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
		self.__windows = []
		assert len (tree.children) > 0
		if tree.children[0].tag != 'Window':
			tree = self.__element (tree.tag, {}, [self.__element ('Window', tree.attributes, tree.children)])
		self.__event = {}
		self.__get = {}
		self.__set = {}
		assert tree.attributes == {}
		for w in tree.children:
			assert w.tag == 'Window'
			self.__windows += (self.__build (w),)
		for w in self.__windows:
			w.connect ('destroy', self.__destroy)
		if self.__external != {}:
			print 'Not all externally provided widgets were used: ' + str (self.__external)
		del self.__external
	def __event_cb (self, object, name):
		if self.__event[name][0] != None:
			f = self.__event[name][0]
			if f.__code__.co_argcount > 0:
				f (self.__event[name][1])
			else:
				f ()
	def __add_event (self, widget, event, desc, name = None):
		if name == None:
			name = event
		if name not in desc.attributes:
			return
		value = desc.attributes[name]
		del desc.attributes[name]
		assert value not in self.__get and value not in self.__set and value not in self.__event
		self.__event[value] = [None, None]
		widget.connect (event, self.__event_cb, value)
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
	def __build_pack (self, desc, parent):
		for c in desc.children:
			parent.pack_start (self.__build (c))
	def __build (self, desc):
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
		elif desc.tag == 'Label':
			ret = gtk.Label ()
			def set (value, label):
				label.set_text (value)
			self.__add_set (desc, 'value', set, ret)
		elif desc.tag == 'Button':
			assert len (desc.children) == 1
			ret = gtk.Button ()
			self.__add_event (ret, 'clicked', desc)
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
			self.__add_event (ret, 'activate', desc)
			self.__add_event (ret, 'changed', desc)
		elif desc.tag == 'External':
			assert len (desc.children) == 0
			ret = self.__external[desc.attributes['id']]
			del self.__external[desc.attributes['id']]
			del desc.attributes['id']
		else:
			raise AssertionError ('invalid tag ' + desc.tag)
		if desc.attributes != {}:
			raise AssertionError ('unused attributes for ' + desc.tag + ': ' + str (desc.attributes))
		return ret

	def __call__ (self):
		for w in self.__windows:
			w.show_all ()
		gtk.main ()

def quit ():
	gtk.main_quit ()
