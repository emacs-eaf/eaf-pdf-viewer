# -*- coding: utf-8 -*-

# Copyright (C) 2018 Andy Stewart
#
# Author:     Andy Stewart <lazycat.manatee@gmail.com>
# Maintainer: Andy Stewart <lazycat.manatee@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# utils function
def convert_hex_to_qcolor(color, inverted=False):
    from PyQt6.QtGui import QColor

    color = QColor(color)
    if not inverted:
        return color

    r = 1.0 - float(color.redF())
    g = 1.0 - float(color.greenF())
    b = 1.0 - float(color.blueF())

    col = QColor()
    col.setRgbF(r, g, b)
    return col

def generate_random_key(count, letters):
    import random
    import math

    key_list = []
    key_len = 1 if count == 1 else math.ceil(math.log(count) / math.log(len(letters)))
    while count > 0:
        key = ''.join(random.choices(letters, k=key_len))
        if key not in key_list:
            key_list.append(key)
            count -= 1
    return key_list

def is_old_version(v, v_bound='1.18.2'):
    from packaging import version
    return version.parse(v) < version.parse(v_bound)

def is_doc_new_name(v, v_bound='1.19.0'):
    from packaging import version
    return version.parse(v) >= version.parse(v_bound)

import fitz

support_hit_max = is_old_version(fitz.VersionBind)
use_new_doc_name = is_doc_new_name(fitz.VersionBind)
