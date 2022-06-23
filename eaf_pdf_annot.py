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

import fitz
class AnnotAction():
    def __init__(self, page_index):
        self.page_index = page_index
        self.action_type = None
        self.annot_id = None
        self.annot_type = None
        self.annot_rect = None
        self.annot_top_left_point = None
        self.annot_title = None
        self.annot_content = None
        self.annot_rect = None
        self.annot_quads = []
        self.annot_fill_color = None
        self.annot_stroke_color = None
        self.annot_inline_text_align = None

    @staticmethod
    def create_annot_action(action, page_index, annot, quads=None):
        annot_action = AnnotAction(page_index)
        annot_action.action_type = action
        annot_action.annot_id = annot.info["id"]
        annot_action.annot_type = annot.type[0]
        annot_action.annot_title = annot.info["title"]
        annot_action.annot_content = annot.info["content"]
        annot_action.annot_rect = annot.rect
        annot_action.annot_top_left_point = annot.rect.top_left
        annot_action.annot_fill_color = annot.colors["fill"]
        annot_action.annot_stroke_color = annot.colors["stroke"]
        if ((annot_action.annot_type == fitz.PDF_ANNOT_HIGHLIGHT or
             annot_action.annot_type == fitz.PDF_ANNOT_STRIKE_OUT or
             annot_action.annot_type == fitz.PDF_ANNOT_UNDERLINE or
             annot_action.annot_type == fitz.PDF_ANNOT_SQUIGGLY)):
            for i in range(int(len(annot.vertices) / 4)):
                tl_x, tl_y = annot.vertices[i * 4]
                br_x, br_y = annot.vertices[i * 4 + 3]
                rect = fitz.Rect(tl_x, tl_y, br_x, br_y)
                annot_action.annot_quads.append(rect.quad)

        return annot_action

    @staticmethod
    def find_annot_of_annot_action(page, annot_action):
        annot = page.first_annot

        while annot:
            if (annot.info["id"] == annot_action.annot_id):
                return annot
            else:
                annot = annot.next

        return None
