#!/usr/bin/env python
try:
	from sugar3.activity import bundlebuilder
	bundlebuilder.start()
except ImportError:
	print "Error: sugar.activity.Bundlebuilder not found."
