# python-gui

Creating a gui in a toolkit-independent way.

## Using this module
This module provides a toolkit-independent way to create a gui in a program.
The idea is that the gui definition should be toolkit-specific, but the rest of
the program should not. A program using this module will not define the gui
itself, and will not directly interact with it.

Well, that's the theory.  For special features, direct interaction is still
useful (and possible).

The program interacts with the UI through an interface of several variable
types:
* get: a value which can be edited in the gui, and retreived by the program on
  request.
* set: a value which can be set to change the gui in some way.
* event: an event which can happen in the gui, which should trigger a callback.
* data: shared memory which can be used by widgets and the application.
  Built-in widgets never use this, but custom widgets can.

For example, a text entry has a get and a set property, which can get and set
the current value of the entry respectively. A button has an event property
which fires when the button is clicked. A checkbutton has all three variable
types.

It is possible for a single widget to have zero or more variables of each type.
For example, a spinbutton has a set variable for setting its value, and another
to set its range.

A gui can be defined as:
\<gtk\>
	\<Window\>
		\<VBox\>Enter something\<Entry changed='new_value'
			value='myvalue:Initial value' /\>
			\<Button clicked='stop'\>Quit!\</Button\>
		\</VBox\>
	\</Window\>
\</gtk\>

A program can use this gui as:

  import gui
  def the_value_changed ():
	print ('New value: %s' % the_gui.get_value)
	print ('+1 to that')
	# This will cause recursion death, but you get the idea.
	the_gui.myvalue += '1'
  g = gui.Gui (events = {'stop': (lambda x: g (False))})
  g.myvalue = "I'm setting a new value!"
  g ()

As you can see, get and set variables can be used when they are wanted. Event
variables must be registered. The last line runs the main loop. The same
function with False as first argument stops the main loop. Nested loops are
allowed, but only the innermost running loop may be stopped.

## Other widgets
Custom widgets can be created and passed to gui.Gui with the widgets argument;
custom objects can be passed with the gtk argument.  See the source for
details.
