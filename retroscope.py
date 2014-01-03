#!/usr/bin/python
# coding=UTF-8

# Copyright 2008 Gabriel Burt
#
# See COPYING for licensing information
#
# Activity web site:
# Created: December 2008
# Author: gabriel.burt@gmail.com
# Home page: http://gburt.blogspot.com/

"""\
RetroScope XO activity.

TODO:
-
"""

import pygst
pygst.require('0.10')
import gst

import gtk
import gobject
from sugar.activity import activity
from sugar.activity.widgets import ActivityToolbarButton, StopButton
from sugar.graphics.toolbarbox import ToolbarBox
from gettext import gettext as _

gobject.threads_init()
gtk.gdk.threads_init()

# Through trial and error this is about the max # of seconds
# that seems to work before we sap the XO of memory
MAX_DELAY = 10


class RetroscopeActivity(activity.Activity):

    """RetroScope activity."""
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self._name = handle
        self.set_title(_("RetroScope"))
        self.max_participants = 1

        self.active = False
        self.connect("notify::active", self.activity_active_callback)

        # Create the video pipeline
        self.retroscope = Retroscope()
        self.delay = 3

        # Create the main video window
        self.video_window = gtk.DrawingArea()

        # Create the top toolbar
        toolbox = self.build_toolbar()
        self.set_toolbar_box(toolbox)

        # Show everything
        self.set_canvas(self.video_window)
        self.show_all()

        self.active = True

        gobject.idle_add(self.set_video_window)

    def build_toolbar(self):
        toolbar_box = ToolbarBox()
        toolbar = toolbar_box.toolbar

        activity = ActivityToolbarButton(self)
        stop = StopButton(self)
        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)

        retroness = gtk.Adjustment(3, 0, MAX_DELAY, 1, 10, 0)
        retroness.connect("value_changed", self.retroness_adjusted_cb)

        retro_bar = gtk.HScale(retroness)
        retro_bar.set_digits(0)
        retro_bar.set_value_pos(gtk.POS_RIGHT)
        retro_bar.set_size_request(240, 15)

        retro_tool = gtk.ToolItem()
        retro_tool.add(retro_bar)

        label = gtk.ToolItem()
        label.add(gtk.Label(_("Seconds Delayed:")))

        toolbar.insert(activity, -1)
        toolbar.insert(gtk.SeparatorToolItem(), -1)
        toolbar.insert(label, -1)
        toolbar.insert(retro_tool, -1)
        toolbar.insert(separator, -1)
        toolbar.insert(stop, -1)

        return toolbar_box

    def set_video_window(self):
        # Keep waiting for the window to not be None
        if not self.video_window.window:
            return True

        # Now we have somewhere to show the video
        self.retroscope.sink.set_xwindow_id(self.video_window.window.xid)
        self.retroscope.set_delay(self.delay)
        self.retroscope.play()

    # Abusing this can-we-close hook to tidy up
    def can_close(self):
        self.retroscope.stop()
        return True

    # Callbacks
    def retroness_adjusted_cb(self, retroness):
        self.delay = retroness.value
        print 'got retroness value changed to ', self.delay
        self.retroscope.set_delay(self.delay)

    def activity_active_callback(self, widget, pspec):
        print 'active =', self.active
        print 'props.active =', self.props.active


class Retroscope:
    def __init__(self):
        self.pipeline = gst.parse_launch(
            'v4l2src name=v4l ! video/x-raw-yuv, framerate=15/1 ! '
            'ffmpegcolorspace name=origin ! tee name=tee'
        )
        #self.pipeline.get_bus().set_sync_handler(print_bus_msg)

        # Create special pipeline elements
        self.queue = gst.element_factory_make('queue')
        self.videoflip = gst.element_factory_make('videoflip')
        self.colorspace = gst.element_factory_make('ffmpegcolorspace')
        self.sink = gst.element_factory_make('xvimagesink')

        # Set some properties on them
        self.queue.set_property('leaky', True)
        self.sink.set_property('sync', False)
        self.sink.set_property('handle-events', True)
        self.sink.set_property('force-aspect-ratio', True)
        # 0 = normal, 1 = 90 CW, 2 = 180, 3 = 90 CCW, 4 = mirrored (default)
        self.videoflip.set_property('method', 4)

        self.elements = [self.queue, self.videoflip, self.colorspace, self.sink]

        prev_element = self.pipeline.get_by_name('tee')
        for element in self.elements:
            self.pipeline.add(element)
            prev_element.link(element)
            prev_element = element

        self.sink.set_property('handle-events', True)

    def set_delay(self, seconds):
        seconds = int(seconds)
        if seconds < 0 or seconds > MAX_DELAY:
            print 'Delay must be greater than 0 and less than', \
                MAX_DELAY, 'seconds.'
            return

        mult = 4.
        self.queue.set_property('max-size-time',
            int((seconds + 1.0) * 1000000000.0))
        self.queue.set_property('max-size-bytes',
            int(mult * 3225600. * (seconds + 1)))
        self.queue.set_property('max-size-buffers',
            int(mult * 7. * (seconds + 1)))
        self.queue.set_property('min-threshold-time',
            int(seconds * 1000000000.0))

    def play(self):
        self.pipeline.set_state(gst.STATE_PLAYING)

    def pause(self):
        self.pipeline.set_state(gst.STATE_PAUSED)

    def stop(self):
        self.pipeline.set_state(gst.STATE_NULL)
