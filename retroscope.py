#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2008 Gabriel Burt
# Copyright (C) 2014 Ignacio Rodríguez
#
# See COPYING for licensing information
#
# Activity web site: 
# Created: December 2008
# Author: gabriel.burt@gmail.com
# Home page: http://gburt.blogspot.com/

import gi
gi.require_version('Gst', '1.0')

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Gst

from sugar3.activity import activity
from sugar3.activity.widgets import ActivityToolbarButton, StopButton
from sugar3.graphics.toolbarbox import ToolbarBox
from gettext import gettext as _
import math
import time
import json
import os
import logging

GObject.threads_init()
Gdk.threads_init()
Gst.init([])

# Through trial and error this is about the max # of seconds
# that seems to work before we sap the XO of memory
MAX_DELAY = 10


class RetroscopeActivity(activity.Activity):

    """RetroScope activity."""
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self.max_participants = 1
        self.active = False
        self.source_id = None
        self.retroscope = None


        self.video_window = Gtk.DrawingArea()
        self.video_window.connect('realize', self.__realize_cb)

        self.delay = 3

        toolbar = self.build_toolbar()
        self.set_toolbar_box(toolbar)
        self.set_canvas(self.video_window)
        self.show_all()

    def __realize_cb(self, widget):
        Gtk.DrawingArea.do_realize(widget)
        if not self.retroscope:
            self.retroscope = Retroscope(self.video_window.get_window().get_xid())

        if not self.source_id and self.retroscope:
            self.source_id = GObject.timeout_add(1000, self.set_video_window)

    def build_toolbar(self):
        toolbar_box = ToolbarBox()
        toolbar = toolbar_box.toolbar

        activity = ActivityToolbarButton(self)
        stop = StopButton(self)
        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)

        # Allow being zero to MAX_DELAY seconds retro, default to self.delay
        retroness = Gtk.Adjustment.new(self.delay, 0, MAX_DELAY, 1, 10, 0)
        retroness.connect("value_changed", self.retroness_adjusted_cb)

        retro_bar = Gtk.HScale.new(retroness)
        retro_bar.set_digits(0)
        retro_bar.set_value_pos(Gtk.PositionType.RIGHT)
        retro_bar.set_size_request(240, 15)

        retro_tool = Gtk.ToolItem()
        retro_tool.add(retro_bar)

        label = Gtk.ToolItem()
        label.add(Gtk.Label(_("Seconds Delayed:")))

        toolbar.insert(activity, -1)
        toolbar.insert(Gtk.SeparatorToolItem(), -1)
        toolbar.insert(label, -1)
        toolbar.insert(retro_tool, -1)
        toolbar.insert(separator, -1)
        toolbar.insert(stop, -1)

        return toolbar_box

    def set_video_window(self):
        if self.video_window.get_window() == None:
            return True

        #xid = self.video_window.get_window().get_xid()
        #self.retroscope.sink.set_window_handle(xid)
        self.retroscope.set_delay(self.delay)
        self.retroscope.play()

    def can_close(self):
        self.retroscope.stop()
        return True

    def retroness_adjusted_cb(self, widget):
        self.delay = widget.get_value()
        self.retroscope.set_delay(self.delay)


class Retroscope:
    def __init__(self, window_id):
        self.window_id = window_id
        self.pipeline = Gst.Pipeline()

        self.camera = Gst.ElementFactory.make('v4l2src', None)
        self.queue = Gst.ElementFactory.make('queue', None)
        self.videoflip = Gst.ElementFactory.make('videoflip', None)
        self.colorspace = Gst.ElementFactory.make('videoconvert', None)
        self.sink = Gst.ElementFactory.make('xvimagesink', None)

        self.queue.set_property('leaky', True)
        self.sink.set_property('sync', False)
        self.sink.set_property('handle-events', True)
        self.sink.set_property('force-aspect-ratio', True)
        self.videoflip.set_property('method', 4)

        self.elements = [self.queue, self.videoflip,
            self.colorspace, self.sink]

        prev_element = None
        self.pipeline.add(self.sink)
        self.sink.link(self.camera)
        self.camera.link(self.colorspace)

        self.sink.set_property('handle-events', True)

        self.bus = self.pipeline.get_bus()
        self.bus.enable_sync_message_emission()
        self.bus.connect('sync-message', self.__sync_message)


    def set_delay(self, seconds):
        seconds = int(seconds)
        if seconds < 0 or seconds > MAX_DELAY:
            return

        mult = 4.
        self.queue.set_property('max-size-time', int((seconds + 1.0) * 1000000000.0))
        self.queue.set_property('max-size-bytes', int(mult*3225600. * (seconds + 1)))
        self.queue.set_property('max-size-buffers', int(mult*7. * (seconds + 1)))
        self.queue.set_property('min-threshold-time', int(seconds * 1000000000.0))

    def play(self):
        self.pipeline.set_state(Gst.State.PLAYING)

    def pause(self):
        self.pipeline.set_state(Gst.State.PAUSED)

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)

    def __sync_message(self, bus, message):
        try:
            if message.get_structure().get_name() == 'prepare-window-handle':
                message.src.set_window_handle(self.window_id)
                return
        except:
            pass