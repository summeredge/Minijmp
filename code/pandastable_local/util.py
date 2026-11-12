#!/usr/bin/env python
"""
    Implements the utility methods for pandastable classes.
    Created August 2015
    Copyright (C) Damien Farrell

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 3
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

from __future__ import absolute_import, division, print_function
try:
    from tkinter import *
    from tkinter.ttk import *
except:
    from Tkinter import *
    from ttk import *
import math, time
import os, types
import string, copy
import numpy as np
import pandas as pd
import tempfile
import re
from contextlib import contextmanager

SCRATCH = None
FORMULA_TEXT = re.compile(r"[ \t\r\n]*[=+\-@]")


def _risky(value):
    return isinstance(value, str) and FORMULA_TEXT.match(value) is not None


def escape_text(value):
    """Mark text a spreadsheet could run as a formula with Excel's literal quote."""
    # "=1+1", "  =SUM(A1)", "+1+1", "@x" and "-2^2" run as formulas; "-12.5" stays text.
    if _risky(value):
        return "'" + value
    return value


def _textual(dtype):
    return dtype == object or isinstance(dtype, (pd.StringDtype, pd.CategoricalDtype))


def text_columns(frame):
    """Positions of text columns holding a grid formula trigger."""
    return [position for position, dtype in enumerate(frame.dtypes)
            if _textual(dtype) and any(map(_risky, frame.iloc[:, position]))]


def _written_as_formula(frame, index):
    """True when the frame holds text openpyxl would store as a formula cell."""
    labels = []
    for axis in ([frame.columns, frame.index] if index else [frame.columns]):
        labels.extend(axis.names)
        if isinstance(axis, pd.MultiIndex):
            labels.extend(value for label in axis for value in label)
        else:
            labels.extend(axis)
    if any(isinstance(value, str) and value.startswith("=") for value in labels):
        return True
    return any(isinstance(value, str) and value.startswith("=")
               for position, dtype in enumerate(frame.dtypes) if _textual(dtype)
               for value in frame.iloc[:, position])


def protected_frame(frame, index=False):
    """Copy for CSV/TSV output; only risky text is prefixed, numbers and NA stay as they are."""
    result = frame.copy()
    for position in text_columns(result):
        result.isetitem(position, result.iloc[:, position].map(escape_text))
    for attribute in (['columns', 'index'] if index else ['columns']):
        axis = getattr(result, attribute)
        if isinstance(axis, pd.MultiIndex):
            axis = pd.MultiIndex.from_arrays([
                values.map(escape_text) if any(map(_risky, values)) else values
                for values in (axis.get_level_values(level) for level in range(axis.nlevels))
            ], names=[escape_text(name) for name in axis.names])
        else:
            if any(map(_risky, axis)):
                axis = axis.map(escape_text)
            axis = axis.rename(escape_text(axis.name))
        setattr(result, attribute, axis)
    return result


def save_frame(frame, filename, *, index=False, encoding="utf-8-sig"):
    """Write a user table to CSV or Excel without formula-injecting its text."""
    if os.path.splitext(filename)[1].lower() == ".csv":
        protected_frame(frame, index).to_csv(filename, index=index, encoding=encoding)
        return
    frame.to_excel(filename, index=index)
    if not _written_as_formula(frame, index):
        return
    # Reopen and rewrite only the formula cells openpyxl produced; nothing else moves.
    from openpyxl import load_workbook
    book = load_workbook(filename)
    for row in book.active.iter_rows():
        for cell in row:
            if cell.data_type == 'f':
                cell.data_type = 's'
    book.save(filename)
    book.close()


@contextmanager
def atomic_output(filename):
    """Serialize beside the destination; publish only a complete file."""
    destination = os.path.abspath(os.fspath(filename))
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(destination),
                                     suffix=os.path.splitext(destination)[1].lower())
    os.close(fd)  # Windows writers must reopen a closed temporary file.
    try:
        yield temporary
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def getTextLength(text, w, font=None):
    """Get correct canvas text size (chars) that will fit in \
    a given canvas width"""

    global SCRATCH
    if SCRATCH is None:
        SCRATCH = Canvas()
    scratch = SCRATCH
    length = len(text)
    t = scratch.create_text((0,0), text=text, font=font)
    b = scratch.bbox(t)
    scratch.delete(t)
    twidth = b[2]-b[0]
    ratio = length/twidth
    length = math.floor(w*ratio)
    return twidth,length

def check_multiindex(index):
    """Check if index is a multiindex"""

    #if isinstance(index, pd.core.index.MultiIndex):
    if isinstance(index, pd.core.indexes.multi.MultiIndex):
        return 1
    else:
        return 0

def getAttributes(obj):
    """Get non hidden and built-in type object attributes that can be persisted"""

    d={}
    allowed = [str,int,float,list,tuple,bool]
    for key in obj.__dict__:
        if key.startswith('_'):
            continue
        item = obj.__dict__[key]
        if type(item) in allowed:
            d[key] = item
        elif type(item) is dict:
            if checkDict(item) == 1:
                d[key] = item
    return d

def setAttributes(obj, data):
    """Set attributes from a dict. Used for restoring settings in tables"""

    for key in data:
        try:
            obj.__dict__[key] = data[key]
        except Exception as e:
            print (e)
    return

def checkDict(d):
    """Check a dict recursively for non serializable types"""

    allowed = [str,int,float,list,tuple,bool]
    for k, v in d.items():
        if isinstance(v, dict):
            checkDict(v)
        else:
            if type(v) not in allowed:
                return 0
    return 1

def getFonts():
     """Get the current list of system fonts"""

     import matplotlib.font_manager
     #l = matplotlib.font_manager.get_fontconfig_fonts()
     l = matplotlib.font_manager.findSystemFonts()
     fonts = []
     for fname in l:
        try: fonts.append(matplotlib.font_manager.FontProperties(fname=fname).get_name())
        except RuntimeError: pass
     fonts = list(set(fonts))
     fonts.sort()
     #f = matplotlib.font_manager.FontProperties(family='monospace')
     #print (matplotlib.font_manager.findfont(f))
     return fonts

def adjustColorMap(cmap, minval=0.0, maxval=1.0, n=100):
    """Adjust colormap to avoid using white in plots"""

    from matplotlib import colors
    new_cmap = colors.LinearSegmentedColormap.from_list(
        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=minval, b=maxval),
        cmap(np.linspace(minval, maxval, n)))
    return new_cmap

def colorScale(hex_color, brightness_offset=1):
    """Takes a hex color and produces a lighter or darker variant.
    Returns:
        new color in hex format
    """

    #if not hex_color.startswith('#'):
        #import matplotlib
        #hex_color = matplotlib.colors.cnames[hex_color].lower()
    if len(hex_color) != 7:
        raise Exception("Passed %s into color_variant(), needs to be in #87c95f format." % hex_color)
    rgb_hex = [hex_color[x:x+2] for x in [1, 3, 5]]
    new_rgb_int = [max(0, int(hex_value, 16) + brightness_offset) for hex_value in rgb_hex]
    r,g,b = [min([255, max([1, i])]) for i in new_rgb_int]
    # hex() produces "0x88", we want just "88"
    return "#{0:02x}{1:02x}{2:02x}".format(r, g, b)

def checkOS():
    """Check the OS we are in"""

    from sys import platform as _platform
    if _platform == "linux" or _platform == "linux2":
        return 'linux'
    elif _platform == "darwin":
        return 'darwin'
    if "win" in _platform:
        return 'windows'


def trace_write(var, callback):
    """Register a write trace on a tkinter Variable (Python 3.8+ and legacy)."""

    if hasattr(var, 'trace_add'):
        var.trace_add('write', callback)
    else:
        var.trace('w', callback)
    return
