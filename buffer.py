#!/usr/bin/env python3
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

from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QRect, QPoint, QEvent, QTimer, QFileSystemWatcher
from PyQt5.QtGui import QColor, QPixmap, QImage, QFont, QCursor
from PyQt5.QtGui import QPainter, QPolygon, QPalette
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QToolTip
from core.buffer import Buffer
from core.utils import touch, interactive, eval_in_emacs, message_to_emacs, open_url_in_new_tab, translate_text, atomic_edit, get_emacs_var, get_emacs_vars, get_emacs_func_result, get_emacs_config_dir, get_emacs_theme_mode, get_emacs_theme_foreground, get_emacs_theme_background
import fitz
import time
import random
import math
import os
import hashlib
import json
import platform
import threading
from collections import defaultdict

class AppBuffer(Buffer):
    def __init__(self, buffer_id, url, arguments):
        Buffer.__init__(self, buffer_id, url, arguments, False)

        (buffer_background_color, self.store_history, self.pdf_dark_mode) = get_emacs_vars([
             "eaf-buffer-background-color",
             "eaf-pdf-store-history",
             "eaf-pdf-dark-mode"])

        self.delete_temp_file = arguments == "temp_pdf_file"

        self.synctex_info = [None, None, None]
        if arguments.startswith("synctex_info"):
            synctex_info = arguments.split("=")[1].split(":")
            page_num = int(synctex_info[0])
            pos_x = float(synctex_info[1])
            pos_y = float(synctex_info[2])
            self.synctex_info = [page_num, pos_x, pos_y]

        self.add_widget(PdfViewerWidget(url, QColor(buffer_background_color), buffer_id, self.synctex_info))
        self.buffer_widget.translate_double_click_word.connect(translate_text)

        # Use thread to avoid slow down open speed.
        threading.Thread(target=self.record_open_history).start()

        self.build_all_methods(self.buffer_widget)

        # Convert title if pdf is converted from office file.
        if arguments.endswith("_office_pdf"):
            self.change_title(arguments.split("_office_pdf")[0])

    def record_open_history(self):
        if self.store_history:
            # Make sure file created.
            history_file = os.path.join(get_emacs_config_dir(), "pdf", "history", "log.txt")
            touch(history_file)

            # Read history.
            lines = []
            with open(history_file, "r") as f:
                lines = f.readlines()

            # Filter empty line and \n char that end of filename.
            lines = list(filter(lambda line: line != "\n", lines))
            lines = list(map(lambda line: line.replace("\n", ""), lines))

            # Make sure current file is at top of history file.
            if self.url in lines:
                lines.remove(self.url)
            lines.insert(0, self.url)

            # Record history.
            with open(history_file, "w") as f:
                for line in lines:
                    f.write(line)
                    f.write("\n")

    def destroy_buffer(self):
        if self.delete_temp_file:
            if os.path.exists(self.url):
                os.remove(self.url)

        super().destroy_buffer()

    def get_table_file(self):
        return self.buffer_widget.table_file_path

    def handle_input_response(self, callback_tag, result_content):
        if callback_tag == "jump_page":
            self.buffer_widget.jump_to_page(int(result_content))
        elif callback_tag == "jump_percent":
            self.buffer_widget.jump_to_percent(int(result_content))
        elif callback_tag == "jump_link":
            self.buffer_widget.jump_to_link(str(result_content))
        elif callback_tag == "search_text":
            self.buffer_widget.search_text(str(result_content))

    def cancel_input_response(self, callback_tag):
        if callback_tag == "jump_link":
            self.buffer_widget.cleanup_links()

    def scroll_other_buffer(self, scroll_direction, scroll_type):
        if scroll_type == "page":
            if scroll_direction == "up":
                self.scroll_up_page()
            else:
                self.scroll_down_page()
        else:
            if scroll_direction == "up":
                self.scroll_up()
            else:
                self.scroll_down()

    def save_session_data(self):
        return "{0}:{1}:{2}:{3}:{4}".format(self.buffer_widget.scroll_offset,
                                        self.buffer_widget.scale,
                                        self.buffer_widget.read_mode,
                                        self.buffer_widget.inverted_mode,
                                        self.buffer_widget.rotation)

    def restore_session_data(self, session_data):
        (scroll_offset, scale, read_mode, inverted_mode, rotation) = ("", "", "", "", "0")
        if session_data.count(":") == 3:
            (scroll_offset, scale, read_mode, inverted_mode) = session_data.split(":")
        else:
            (scroll_offset, scale, read_mode, inverted_mode, rotation) = session_data.split(":")
        if self.synctex_info[0] == None:
            self.buffer_widget.scroll_offset = float(scroll_offset)
        self.buffer_widget.scale = float(scale)
        self.buffer_widget.read_mode = read_mode
        self.buffer_widget.rotation = int(rotation)
        self.buffer_widget.update()

    def jump_to_page(self):
        self.send_input_message("Jump to Page: ", "jump_page")

    def jump_to_page_with_num(self, num):
        self.buffer_widget.jump_to_page(int(num))

    def jump_to_page_synctex(self, synctex_info):
        synctex_info = synctex_info.split(":")

        page_num = int(synctex_info[0])
        self.buffer_widget.synctex_page_num = page_num
        self.buffer_widget.jump_to_page(page_num)

        self.buffer_widget.synctex_pos_x = float(synctex_info[1])
        self.buffer_widget.synctex_pos_y = float(synctex_info[2])
        self.buffer_widget.update()
        return ""

    def jump_to_percent(self):
        self.send_input_message("Jump to Percent: ", "jump_percent")

    def jump_to_percent_with_num(self, percent):
        self.buffer_widget.jump_to_percent(float(percent))
        return ""

    def jump_to_link(self):
        self.buffer_widget.add_mark_jump_link_tips()
        self.send_input_message("Jump to Link: ", "jump_link", "marker")

    def action_quit(self):
        if self.buffer_widget.is_mark_search:
            self.buffer_widget.cleanup_search()
        if self.buffer_widget.is_jump_link:
            self.buffer_widget.cleanup_links()
        if self.buffer_widget.is_select_mode:
            self.buffer_widget.cleanup_select()

    def search_text_forward(self):
        if self.buffer_widget.is_mark_search:
            self.buffer_widget.jump_next_match()
        else:
            self.send_input_message("Search Text: ", "search_text")

    def search_text_backward(self):
        if self.buffer_widget.is_mark_search:
            self.buffer_widget.jump_last_match()
        else:
            self.send_input_message("Search Text: ", "search_text")

    def copy_select(self):
        if self.buffer_widget.is_select_mode:
            content = self.buffer_widget.parse_select_char_list()
            eval_in_emacs('kill-new', [content])
            message_to_emacs(content)
            self.buffer_widget.cleanup_select()

    def get_select(self):
        if self.buffer_widget.is_select_mode:
            content = self.buffer_widget.parse_select_char_list()
            self.buffer_widget.cleanup_select()
            return content
        else:
            return ""

    def page_total_number(self):
        return str(self.buffer_widget.page_total_number)

    def current_page(self):
        return str(self.buffer_widget.start_page_index + 1)

    def current_percent(self):
        return str(self.buffer_widget.current_percent())

    def add_annot_highlight(self):
        if self.buffer_widget.is_select_mode:
            self.buffer_widget.annot_select_char_area("highlight")

    def add_annot_strikeout_or_delete_annot(self):
        if self.buffer_widget.is_select_mode:
            self.buffer_widget.annot_select_char_area("strikeout")
        elif self.buffer_widget.is_hover_annot:
            self.buffer_widget.annot_handler("delete")

    def add_annot_underline(self):
        if self.buffer_widget.is_select_mode:
            self.buffer_widget.annot_select_char_area("underline")

    def add_annot_squiggly(self):
        if self.buffer_widget.is_select_mode:
            self.buffer_widget.annot_select_char_area("squiggly")

    def add_annot_popup_text(self):
        self.buffer_widget.enable_popup_text_annot_mode()

    def add_annot_inline_text(self):
        self.buffer_widget.enable_inline_text_annot_mode()

    def edit_annot_text(self):
        if self.buffer_widget.is_select_mode:
            atomic_edit(self.buffer_id, "")
        elif self.buffer_widget.is_hover_annot:
            self.buffer_widget.annot_handler("edit")

    def move_annot_text(self):
        if self.buffer_widget.is_select_mode:
            atomic_edit(self.buffer_id, "")
        elif self.buffer_widget.is_hover_annot:
            message_to_emacs("Move text annot: left-click mouse to choose a target position.")
            self.buffer_widget.annot_handler("move")

    def set_focus_text(self, new_text):
        if self.buffer_widget.is_select_mode:
            self.buffer_widget.annot_select_char_area("text", new_text)
        elif self.buffer_widget.is_hover_annot:
            if self.buffer_widget.edited_annot_page[0] != None:
                self.buffer_widget.edit_annot_text(new_text)
        elif self.buffer_widget.is_popup_text_annot_mode:
            self.buffer_widget.annot_popup_text_annot(new_text)
        elif self.buffer_widget.is_inline_text_annot_mode:
            self.buffer_widget.annot_inline_text_annot(new_text)

    def get_toc(self):
        result = ""
        toc = self.buffer_widget.document.getToC()
        for line in toc:
            result += "{0}{1} {2}\n".format("".join("    " * (line[0] - 1)), line[1], line[2])
        return result

    def get_page_annots(self, page_index):
        '''
        Return a list of annotations on page_index of types.
        '''
        if self.buffer_widget.document[page_index].firstAnnot is None:
            return None

        # Notes: annots need the pymupdf above 1.16.4 version.
        annots = self.buffer_widget.get_annots(int(page_index))
        result = {}
        for annot in annots:
            id = annot.info["id"]
            rect = annot.rect
            type = annot.type
            if len(type) != 2:
                continue
            result[id] = {
                "info": annot.info,
                "page": page_index,
                "type_int": type[0],
                "type_name": type[1],
                "rect": "%s:%s:%s:%s" %(rect.x0, rect.y0, rect.x1, rect.y1),
                "text": annot.parent.get_textbox(rect),
            }
        return json.dumps(result)

    def get_document_annots(self):
        annots = {}
        for page_index in range(self.buffer_widget.page_total_number):
            annot = self.get_page_annots(page_index)
            if annot:
                annots[page_index] = annot
        return json.dumps(annots)

    def jump_to_rect(self, page_index, rect):
        arr = rect.split(":")
        if len(arr) != 4:
            return ""
        rect = fitz.Rect(float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3]))
        self.buffer_widget.jump_to_rect(int(page_index), rect)
        return ""

    def fetch_marker_callback(self):
        return list(map(lambda x: x.lower(), self.buffer_widget.jump_link_key_cache_dict.keys()))

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
        annot = page.firstAnnot

        while annot:
            if (annot.info["id"] == annot_action.annot_id):
                return annot
            else:
                annot = annot.next

        return None

class PdfDocument(fitz.Document):
    def __init__(self, document):
        self.document = document
        self._is_trim_margin = False
        self._page_cache_dict = {}
        self._document_page_clip = None
        self._document_page_change = lambda rect: None

    def __getattr__(self, attr):
        return getattr(self.document, attr)

    def __getitem__(self, index):
        if index in self._page_cache_dict:
            page = self._page_cache_dict[index]
            if not self._is_trim_margin:
                return page

            if page.CropBox == self._document_page_clip:
                return page

        page = PdfPage(self.document[index], index, self.document.isPDF)

        # udpate the page clip
        new_rect_clip = self.computer_page_clip(page.get_tight_margin_rect(), self._document_page_clip)
        if new_rect_clip != self._document_page_clip:
            self._document_page_clip = new_rect_clip
            if self._is_trim_margin:
                self._document_page_change(new_rect_clip)

        if self._is_trim_margin:
            return PdfPage(self.document[index], index, self.document.isPDF, self._document_page_clip)

        return page

    def computer_page_clip(self, *args):
        '''Update the bestest max page clip.'''
        dr = None
        for r in args:
            if r is None:
                continue
            if dr is None:
                dr = r
                continue
            x0 = min(r.x0, dr.x0)
            y0 = min(r.y0, dr.y0)
            x1 = max(r.x1, dr.x1)
            y1 = max(r.y1, dr.y1)
            dr = fitz.Rect(x0, y0, x1, y1)
        return dr

    def reload_document(self, url):
        self._page_cache_dict = {}
        try:
            self.document = fitz.open(url)
        except Exception:
            message_to_emacs("Failed to reload PDF file!")


    def cache_page(self, index, page):
        self._page_cache_dict[index] = page

    def watch_file(self, path, callback):
        '''
        Refresh content with PDF file changed.
        '''
        self.watch_callback = callback
        self.file_changed_wacher = QFileSystemWatcher()
        self.file_changed_wacher.addPath(path)
        self.file_changed_wacher.fileChanged.connect(self.handle_file_changed)

    def handle_file_changed(self, path):
        '''
        Use the QFileSystemWatcher watch file changed. If the watch file have been remove or rename,
        this watch will auto remove.
        '''
        if path in self.file_changed_wacher.files():
            try:
                # Some program will generate `middle` file, but file already changed, fitz try to
                # open the `middle` file caused error.
                time.sleep(0.5)
                self.reload_document(path)
            except:
                return

            notify, = get_emacs_vars(["eaf-pdf-notify-file-changed"])
            if notify:
                message_to_emacs("Detected that %s has been changed. Refreshing buffer..." %path)

            try:
                self.watch_callback(path)
            except Exception:
                print("Failed to watch callback")


    def toggle_trim_margin(self):
        self._is_trim_margin = not self._is_trim_margin

    def get_page_width(self):
        if self.isPDF:
            if self._is_trim_margin:
                return self._document_page_clip.width
            return self.document.pageCropBox(0).width
        else:
            return self[0].clip.width

    def get_page_height(self):
        if self.isPDF:
            if self._is_trim_margin:
                return self._document_page_clip.height
            return self.document.pageCropBox(0).height
        else:
            return self[0].clip.height

    def watch_page_size_change(self, callback):
        self._document_page_change = callback

class PdfPage(fitz.Page):
    def __init__(self, page, page_index, isPDF, clip=None):
        self.page = page
        self.page_index = page_index
        self.isPDF = isPDF
        self.clip = clip or page.CropBox

        self._mark_link_annot_list = []
        self._mark_search_annot_list = []
        self._mark_jump_annot_list = []

        self._page_rawdict = self._init_page_rawdict()
        self._page_char_rect_list = self._init_page_char_rect_list()
        self._tight_margin_rect = self._init_tight_margin()

    def __getattr__(self, attr):
        return getattr(self.page, attr)

    def _init_page_rawdict(self):
        if self.isPDF:
            # Must set CropBox before get page rawdict , if no,
            # the rawdict bbox coordinate is wrong
            # cause the select text failed
            self.page.setCropBox(self.clip)
            d = self.page.getText("rawdict")
            # cancel the cropbox, if not, will cause the pixmap set cropbox
            # don't begin on top-left(0, 0), page display black margin
            self.page.setCropBox(self.page.MediaBox)
            return d
        else:
            return self.page.getText("rawdict")

    def _init_page_char_rect_list(self):
        '''Collection page char rect list when page init'''
        lines_list = []
        spans_list = []
        chars_list = []

        for block in self._page_rawdict["blocks"]:
            if "lines" in block:
                lines_list += block["lines"]

        for line in lines_list:
            if "spans" in line:
                spans_list += line["spans"]

        for span in spans_list:
            if "chars" in span:
                chars_list += span["chars"]

        return chars_list

    def _init_tight_margin(self):
        r = None
        for block in self._page_rawdict["blocks"]:
            # ignore image bbox
            if block["type"] != 0:
                continue

            x0, y0, x1, y1 = block["bbox"]
            if r is None:
                r = fitz.Rect(x0, y0, x1, y1)
                continue
            x0 = min(x0, r.x0)
            y0 = min(y0, r.y0)
            x1 = max(x1, r.x1)
            y1 = max(y1, r.y1)
            r = fitz.Rect(x0, y0, x1, y1)
        if r is None:
            return self.page.CropBox
        return r

    def get_tight_margin_rect(self):
        # if current page don't computer tight rect
        # return None
        if self._tight_margin_rect == self.page.MediaBox:
            return None
        return self._tight_margin_rect

    def get_page_char_rect_list(self):
        return self._page_char_rect_list

    def get_page_char_rect_index(self, x, y):
        '''According X and Y coordinate return index of char in char rect list.'''
        if x and y is None:
            return None

        offset = 15
        rect = fitz.Rect(x, y, x + offset, y + offset)
        for char_index, char in enumerate(self._page_char_rect_list):
            if fitz.Rect(char["bbox"]).intersect(rect):
                return char_index
        return None

    def set_rotation(self, rotation):
        self.page.setRotation(rotation)
        if rotation % 180 != 0:
            self.page_width = self.page.CropBox.height
            self.page_height = self.page.CropBox.width
        else:
            self.page_width = self.page.CropBox.width
            self.page_height = self.page.CropBox.height

    def get_qpixmap(self, scale, invert, invert_image=False):
        if self.isPDF:
            self.page.setCropBox(self.clip)
        pixmap = self.page.getPixmap(matrix=fitz.Matrix(scale, scale), alpha=True)

        if invert:
            pixmap.invertIRect(pixmap.irect)

        if not invert_image and invert:
            pixmap = self.with_invert_exclude_image(scale, pixmap)

        img = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format_RGBA8888)
        qpixmap = QPixmap.fromImage(img)
        return qpixmap

    def with_invert_exclude_image(self, scale, pixmap):
        # steps:
        # First, make page all content is invert, include image and text.
        # if exclude image is True, will find the page all image, then get
        # each image rect. Finally, again invert all image rect.

        # exclude image only support PDF document
        imagelist = None
        try:
            imagelist = self.page.getImageList(full=True)
        except Exception:
            # PyMupdf 1.14 not include argument 'full'.
            imagelist = self.page.getImageList()

        imagebboxlist = []
        for image in imagelist:
            try:
                imagerect = self.page.getImageBbox(image)
                if imagerect.isInfinite or imagerect.isEmpty:
                    continue
                else:
                    imagebboxlist.append(imagerect)
            except Exception:
                pass

        for bbox in imagebboxlist:
            pixmap.invertIRect(bbox * self.page.rotationMatrix * scale)

        return pixmap


    def add_mark_link(self):
        if self.page.firstLink:
            for link in self.page.getLinks():
                annot = self.page.addUnderlineAnnot(link["from"])
                annot.parent = self.page # Must assign annot parent, else deleteAnnot cause parent is None problem.
                self._mark_link_annot_list.append(annot)

    def cleanup_mark_link(self):
        if self._mark_link_annot_list:
            for annot in self._mark_link_annot_list:
                self.page.deleteAnnot(annot)
            self._mark_link_annot_list = []

    def mark_search_text(self, keyword):
        quads_list = self.page.searchFor(keyword, hit_max=999, quads=True)
        if quads_list:
            for quads in quads_list:
                annot = self.page.addHighlightAnnot(quads)
                annot.parent = self.page
                self._mark_search_annot_list.append(annot)

    def cleanup_search_text(self):
        if self._mark_search_annot_list:
            message_to_emacs("Unmarked all matched results.")
            for annot in self._mark_search_annot_list:
                self.page.deleteAnnot(annot)
            self._mark_search_annot_list = []

    def mark_jump_link_tips(self, letters):
        fontsize, = get_emacs_vars(["eaf-pdf-marker-fontsize"])
        cache_dict = {}
        if self.page.firstLink:
            links = self.page.getLinks()
            key_list = generate_random_key(len(links), letters)
            for index, link in enumerate(links):
                key = key_list[index]
                link_rect = link["from"]
                annot_rect = fitz.Rect(link_rect.top_left, link_rect.x0 + fontsize/1.2 * len(key), link_rect.y0 + fontsize)
                annot = self.page.addFreetextAnnot(annot_rect, str(key), fontsize=fontsize, fontname="Helv", \
                                                   text_color=[0.0, 0.0, 0.0], fill_color=[255/255.0, 197/255.0, 36/255.0], \
                                                   align = 1)
                annot.parent = self.page
                self._mark_jump_annot_list.append(annot)
                cache_dict[key] = link
        return cache_dict

    def cleanup_jump_link_tips(self):
        for annot in self._mark_jump_annot_list:
            self.page.deleteAnnot(annot)
        self._mark_jump_annot_list = []


class PdfViewerWidget(QWidget):

    translate_double_click_word = QtCore.pyqtSignal(str)

    def __init__(self, url, background_color, buffer_id, synctex_info):
        super(PdfViewerWidget, self).__init__()

        self.url = url
        self.config_dir = get_emacs_config_dir()
        self.background_color = background_color
        self.buffer_id = buffer_id
        self.user_name = get_emacs_var("user-full-name")

        self.synctex_page_num = synctex_info[0]
        self.synctex_pos_x = synctex_info[1]
        self.synctex_pos_y = synctex_info[2]

        self.installEventFilter(self)
        self.setMouseTracking(True)

        (self.marker_letters,
         self.pdf_dark_mode,
         self.pdf_dark_exclude_image,
         self.pdf_default_zoom,
         self.pdf_zoom_step,
         self.pdf_scroll_ratio,
         self.text_highlight_annot_color,
         self.text_underline_annot_color,
         self.inline_text_annot_color,
         self.inline_text_annot_fontsize) = get_emacs_vars([
             "eaf-marker-letters",
             "eaf-pdf-dark-mode",
             "eaf-pdf-dark-exclude-image",
             "eaf-pdf-default-zoom",
             "eaf-pdf-zoom-step",
             "eaf-pdf-scroll-ratio",
             "eaf-pdf-text-highlight-annot-color",
             "eaf-pdf-text-underline-annot-color",
             "eaf-pdf-inline-text-annot-color",
             "eaf-pdf-inline-text-annot-fontsize"])

        self.theme_mode = get_emacs_theme_mode()
        self.theme_foreground_color = get_emacs_theme_foreground()
        self.theme_background_color = get_emacs_theme_background()

        # Init scale and scale mode.
        self.scale = 1.0
        self.read_mode = "fit_to_width"

        self.rotation = 0

        # Simple string comparation.
        if (self.pdf_default_zoom != 1.0):
            self.read_mode = "fit_to_customize"
            self.scale = self.pdf_default_zoom
        self.horizontal_offset = 0

        # Undo/redo annot actions
        self.annot_action_sequence = []
        self.annot_action_index = -1

        # mark link
        self.is_mark_link = False

        #jump link
        self.is_jump_link = False
        self.jump_link_key_cache_dict = {}

        #global search text
        self.is_mark_search = False
        self.search_text_offset_list = []

        # select text
        self.is_select_mode = False
        self.start_char_rect_index = None
        self.start_char_page_index = None
        self.last_char_rect_index = None
        self.last_char_page_index = None
        self.select_area_annot_cache_dict = defaultdict(lambda: None)
        self.select_area_annot_quad_cache_dict = {}

        # text annot
        self.is_hover_annot = False
        self.edited_annot_page = (None, None)
        self.moved_annot_page = (None, None)
        # popup text annot
        self.popup_text_annot_timer = QTimer()
        self.popup_text_annot_timer.setInterval(300)
        self.popup_text_annot_timer.setSingleShot(True)
        self.popup_text_annot_timer.timeout.connect(self.handle_popup_text_annot_mode)
        self.is_popup_text_annot_mode = False
        self.is_popup_text_annot_handler_waiting = False
        self.popup_text_annot_pos = (None, None)
        # inline text annot
        self.inline_text_annot_timer = QTimer()
        self.inline_text_annot_timer.setInterval(300)
        self.inline_text_annot_timer.setSingleShot(True)
        self.inline_text_annot_timer.timeout.connect(self.handle_inline_text_annot_mode)
        self.is_inline_text_annot_mode = False
        self.is_inline_text_annot_handler_waiting = False
        self.inline_text_annot_pos = (None, None)
        # move text annot
        self.move_text_annot_timer = QTimer()
        self.move_text_annot_timer.setInterval(300)
        self.move_text_annot_timer.setSingleShot(True)
        self.move_text_annot_timer.timeout.connect(self.handle_move_text_annot_mode)
        self.is_move_text_annot_mode = False
        self.is_move_text_annot_handler_waiting = False
        self.move_text_annot_pos = (None, None)

        # Init scroll attributes.
        self.scroll_offset = 0
        self.scroll_ratio = 0.05
        self.scroll_wheel_lasttime = time.time()
        if self.pdf_scroll_ratio != 0.05:
            self.scroll_ratio = self.pdf_scroll_ratio

        # Default presentation mode
        self.presentation_mode = False

        # Padding between pages.
        self.page_padding = 10

        # Fill app background color
        pal = self.palette()
        pal.setColor(QPalette.Background, self.background_color)
        self.setAutoFillBackground(True)
        self.setPalette(pal)

        # Init font.
        self.page_annotate_padding_right = 10
        self.page_annotate_padding_bottom = 10

        self.font = QFont()
        self.font.setPointSize(12)

        # Page cache.
        self.page_cache_pixmap_dict = {}
        self.page_cache_scale = self.scale
        self.page_cache_trans = None
        self.page_cache_context_delay = 1000

        self.last_action_time = 0

        self.is_page_just_changed = False

        self.remember_offset = None

        self.last_hover_annot_id = None

        self.start_page_index = 0
        self.last_page_index = 0

        self.load_document(url)

        # Inverted mode.
        self.inverted_mode = False
        if self.pdf_dark_mode == "follow" or self.pdf_dark_mode == "force":
            self.inverted_mode = True

        # Inverted mode exclude image. (current exclude image inner implement use PDF Only method)
        self.inverted_image_mode = not self.pdf_dark_exclude_image and self.document.isPDF

        # synctex init page
        if self.synctex_page_num != None:
            self.jump_to_page(self.synctex_page_num)

    def load_document(self, url):
        if self.page_cache_pixmap_dict:
            self.page_cache_pixmap_dict.clear()

        # Load document first.
        try:
            self.document = PdfDocument(fitz.open(url))
        except Exception:
            message_to_emacs("Failed to load PDF file!")
            return

        # Get document's page information.
        self.document.watch_page_size_change(self.update_page_size)
        self.page_width = self.document.get_page_width()
        self.page_height = self.document.get_page_height()
        self.page_total_number = self.document.pageCount

        # Register file watcher, when document is change, re-calling this function.
        self.document.watch_file(url, self.load_document)

        self.update()

    def is_buffer_focused(self):
        # This check is slow, use only when necessary
        try:
            return get_emacs_func_result("eaf-get-path-or-url", []) == self.url
        except Exception:
            return False

    @interactive
    def toggle_presentation_mode(self):
        '''
        Toggle presentation mode.
        '''
        self.presentation_mode = not self.presentation_mode
        if self.presentation_mode:
            # Make current page fill the view.
            self.zoom_reset("fit_to_height")
            self.jump_to_page(self.start_page_index + 1)

            message_to_emacs("Presentation Mode.")
        else:
            message_to_emacs("Continuous Mode.")

    @property
    def scroll_step_vertical(self):
        if self.presentation_mode:
            return self.rect().height()
        else:
            return self.rect().size().height() * self.scroll_ratio

    @property
    def scroll_step_horizontal(self):
        if self.presentation_mode:
            return self.rect().width()
        else:
            return self.rect().size().width() * self.scroll_ratio

    @interactive
    def save_current_pos(self):
        self.remember_offset = self.scroll_offset
        message_to_emacs("Saved current position.")

    @interactive
    def jump_to_saved_pos(self):
        if self.remember_offset is None:
            message_to_emacs("Cannot jump from this position.")
        else:
            current_scroll_offset = self.scroll_offset
            self.scroll_offset = self.remember_offset
            self.update()
            self.remember_offset = current_scroll_offset
            message_to_emacs("Jumped to saved position.")

    def get_page_pixmap(self, index, scale, rotation=0):
        # Just return cache pixmap when found match index and scale in cache dict.
        if self.page_cache_scale == scale:
            if index in self.page_cache_pixmap_dict.keys():
                return self.page_cache_pixmap_dict[index]
        # Clear dict if page scale changed.
        else:
            self.page_cache_pixmap_dict.clear()
            self.page_cache_scale = scale

        page = self.document[index]
        if self.document.isPDF:
            page.set_rotation(rotation)

        if self.is_mark_link:
            page.add_mark_link()
        else:
            page.cleanup_mark_link()

        # follow page search text
        if self.is_mark_search:
            page.mark_search_text(self.search_term)
        else:
            page.cleanup_search_text()

        if self.is_jump_link:
            self.jump_link_key_cache_dict.update(page.mark_jump_link_tips(self.marker_letters))
        else:
            page.cleanup_jump_link_tips()
            self.jump_link_key_cache_dict.clear()

        qpixmap = page.get_qpixmap(scale, self.inverted_mode, self.inverted_image_mode)

        self.page_cache_pixmap_dict[index] = qpixmap
        self.document.cache_page(index, page)

        return qpixmap

    def clean_unused_page_cache_pixmap(self):
        # We need expand render index bound that avoid clean cache around current index.
        index_list = list(range(self.start_page_index, self.last_page_index))

        # Try to clean unused cache.
        cache_index_list = list(self.page_cache_pixmap_dict.keys())

        for cache_index in cache_index_list:
            if cache_index not in index_list:
                self.page_cache_pixmap_dict.pop(cache_index)

    def resizeEvent(self, event):
        # Update scale attributes after widget resize.
        self.update_scale()

        QWidget.resizeEvent(self, event)

    def paintEvent(self, event):
        # update page base information
        self.update_page_index()

        # Init painter.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        painter.save()

        # Draw background.
        # change color of background if inverted mode is enable
        if self.pdf_dark_mode == "follow" or self.pdf_dark_mode == "force":
            color = QColor(self.theme_background_color)
            painter.setBrush(color)
            painter.setPen(color)
        else:
            color = QColor(20, 20, 20, 255) if self.inverted_mode else Qt.white
            painter.setBrush(color)
            painter.setPen(color)

        if self.scroll_offset > self.max_scroll_offset():
            self.update_vertical_offset(self.max_scroll_offset())

        # Translate painter at y coordinate.
        translate_y = (self.start_page_index * self.scale * self.page_height) - self.scroll_offset
        painter.translate(0, translate_y)

        # Render pages in visible area.
        (render_x, render_y, render_width, render_height) = 0, 0, 0, 0
        for index in list(range(self.start_page_index, self.last_page_index)):
            # Get page image.
            hidpi_scale_factor = self.devicePixelRatioF()
            qpixmap = self.get_page_pixmap(index, self.scale * hidpi_scale_factor, self.rotation)

            # Init render rect.
            render_width = qpixmap.width() / hidpi_scale_factor
            render_height = qpixmap.height() / hidpi_scale_factor
            render_x = (self.rect().width() - render_width) / 2

            # Add padding between pages.
            if (index - self.start_page_index) > 0:
                painter.translate(0, self.page_padding)

            # Draw page image.
            if self.read_mode == "fit_to_customize" and render_width >= self.rect().width():
                # limit the visiable area size
                render_x = max(min(render_x + self.horizontal_offset, 0), self.rect().width() - render_width)

            rect = QRect(render_x, render_y, render_width, render_height)

            # draw rectangle with current pen and brush color
            painter.drawRect(rect)

            painter.drawPixmap(rect, qpixmap)

            # Draw an indicator for synctex position
            if self.synctex_page_num == index + 1 and self.synctex_pos_y != None:
                indicator_pos_y = self.synctex_pos_y * self.scale
                self.draw_synctex_indicator(painter, 15, indicator_pos_y)

            render_y += render_height

        # Clean unused pixmap cache that avoid use too much memory.
        self.clean_unused_page_cache_pixmap()
        painter.restore()

        # Render current page.
        painter.setFont(self.font)

        if self.rect().width() <= render_width and not self.inverted_mode:
            painter.setPen(inverted_color((self.theme_foreground_color), True))
        else:
            painter.setPen(inverted_color((self.theme_foreground_color)))

        # Update page progress
        self.update_page_progress(painter)

    def draw_synctex_indicator(self, painter, x, y):
        painter.save()
        arrow = QPolygon([QPoint(x, y), QPoint(x+26, y), QPoint(x+26, y-5),
                          QPoint(x+35, y+5),
                          QPoint(x+26, y+15), QPoint(x+26, y+10), QPoint(x, y+10),
                          QPoint(x, y)])
        fill_color = QColor(236, 96, 31, 255)
        border_color = QColor(255, 91, 15, 255)
        painter.setBrush(fill_color)
        painter.setPen(border_color)
        painter.drawPolygon(arrow)
        QtCore.QTimer().singleShot(5000, self.clear_synctex_info)
        painter.restore()

    def clear_synctex_info(self):
        self.synctex_page = None
        self.synctex_pos_x = None
        self.synctex_pos_y = None

    def update_page_progress(self, painter):
        # Show in mode-line-position
        current_page = math.floor((self.start_page_index +
                                   self.last_page_index + 1) / 2)

        eval_in_emacs("eaf--pdf-update-position", [self.buffer_id,
                                                   current_page,
                                                   self.page_total_number])

        # Draw progress on page.
        show_progress_on_page, = get_emacs_vars(["eaf-pdf-show-progress-on-page"])
        if show_progress_on_page:
            progress_percent = int(current_page * 100 / self.page_total_number)
            painter.drawText(QRect(self.rect().x(),
                                   self.rect().y(),
                                   self.rect().width() - self.page_annotate_padding_right,
                                   self.rect().height() - self.page_annotate_padding_bottom),
                             Qt.AlignRight | Qt.AlignBottom,
                             "{0}% ({1}/{2})".format(progress_percent, current_page, self.page_total_number))

    def build_context_wrap(f):
        def wrapper(*args):
            # Get self instance object.
            self_obj = args[0]

            # Record page before action.
            page_before_action = self_obj.start_page_index

            # Do action.
            ret = f(*args)

            # Record page after action.
            page_after_action = self_obj.start_page_index
            self_obj.is_page_just_changed = (page_before_action != page_after_action)

            # Start build context timer.
            self_obj.last_action_time = time.time()
            QtCore.QTimer().singleShot(self_obj.page_cache_context_delay, self_obj.build_context_cache)

            return ret

        return wrapper

    @build_context_wrap
    def wheelEvent(self, event):
        if not event.accept():
            if event.angleDelta().y():
                numSteps = event.angleDelta().y()
                if self.presentation_mode:
                    # page scrolling
                    curtime = time.time()
                    if curtime - self.scroll_wheel_lasttime > 0.1:
                        numSteps = 1 if numSteps > 0 else -1
                        self.scroll_wheel_lasttime = curtime
                    else:
                        numSteps = 0
                else:
                    # fixed pixel scrolling
                    numSteps = numSteps / 120
                new_pos = self.scroll_offset - numSteps * self.scroll_step_vertical
                max_pos = self.max_scroll_offset()
                self.update_vertical_offset(max(min(new_pos, max_pos), 0))

            if event.angleDelta().x():
                new_pos = (self.horizontal_offset + event.angleDelta().x() / 120 * self.scroll_step_horizontal)
                max_pos = (self.page_width * self.scale - self.rect().width())
                self.update_horizontal_offset(max(min(new_pos , max_pos), -max_pos))

    def update_page_index(self):
        self.start_page_index = min(int(self.scroll_offset * 1.0 / self.scale / self.page_height),
                                    self.page_total_number - 1)
        self.last_page_index = min(int((self.scroll_offset + self.rect().height()) * 1.0 / self.scale / self.page_height) + 1,
                                   self.page_total_number)

    def update_page_size(self, rect):
        current_page_index = self.start_page_index
        self.page_width = rect.width
        self.page_height = rect.height
        self.jump_to_page(current_page_index)

    def build_context_cache(self):
        # Just build context cache when action duration longer than delay
        # Don't build contexnt cache when is_page_just_changed is True, avoid flickr when user change page.
        last_action_duration = (time.time() - self.last_action_time) * 1000
        if last_action_duration > self.page_cache_context_delay and not self.is_page_just_changed:
            for index in list(range(self.start_page_index, self.last_page_index)):
                self.get_page_pixmap(index, self.scale, self.rotation)

    def scale_to(self, new_scale):
        self.scroll_offset = new_scale * 1.0 / self.scale * self.scroll_offset
        self.scale = new_scale

    def scale_to_width(self):
        self.scale_to(self.rect().width() * 1.0 / self.page_width)

    def scale_to_height(self):
        self.scale_to(self.rect().size().height() * 1.0 / self.page_height)

    def update_scale(self):
        if self.read_mode == "fit_to_width":
            self.scale_to_width()
        elif self.read_mode == "fit_to_height":
            self.scale_to_height()

    def max_scroll_offset(self):
        return self.scale * self.page_height * self.page_total_number - self.rect().height()

    @interactive
    def reload_document(self):
        try:
            self.document = PdfDocument(fitz.open(self.url))
            # recompute width, height, total number since the file might be modified
            self.page_width = self.document.get_page_width()
            self.page_height = self.document.get_page_height()
            self.page_total_number = self.document.pageCount
            message_to_emacs("Reloaded PDF file!")
        except Exception:
            message_to_emacs("Failed to reload PDF file!")

    @interactive
    def toggle_read_mode(self):
        if self.read_mode == "fit_to_customize":
            self.read_mode = "fit_to_width"
        elif self.read_mode == "fit_to_width":
            self.read_mode = "fit_to_height"
        elif self.read_mode == "fit_to_height":
            self.read_mode = "fit_to_width"

        self.update_scale()
        self.update()

    @interactive
    def scroll_up(self):
        self.update_vertical_offset(min(self.scroll_offset + self.scroll_step_vertical, self.max_scroll_offset()))

    @interactive
    def scroll_down(self):
        self.update_vertical_offset(max(self.scroll_offset - self.scroll_step_vertical, 0))

    @interactive
    def scroll_right(self):
        self.update_horizontal_offset(max(self.horizontal_offset - self.scroll_step_horizontal, (self.rect().width() - self.page_width * self.scale) / 2))

    @interactive
    def scroll_left(self):
        self.update_horizontal_offset(min(self.horizontal_offset + self.scroll_step_horizontal, (self.page_width * self.scale - self.rect().width()) / 2))

    @interactive
    def scroll_center_horizontal(self):
        self.update_horizontal_offset(0)

    @interactive
    def scroll_up_page(self):
        # Adjust scroll step to make users continue reading fluently.
        self.update_vertical_offset(min(self.scroll_offset + self.rect().height() - self.scroll_step_vertical, self.max_scroll_offset()))

    @interactive
    def scroll_down_page(self):
        # Adjust scroll step to make users continue reading fluently.
        self.update_vertical_offset(max(self.scroll_offset - self.rect().height() + self.scroll_step_vertical, 0))

    @interactive
    def scroll_to_begin(self):
        self.update_vertical_offset(0)

    @interactive
    def scroll_to_end(self):
        self.update_vertical_offset(self.max_scroll_offset())

    @interactive
    def zoom_in(self):
        self.read_mode = "fit_to_customize"
        self.scale_to(min(10, self.scale + self.pdf_zoom_step))
        self.update()

    @interactive
    def zoom_out(self):
        self.read_mode = "fit_to_customize"
        self.scale_to(max(1, self.scale - self.pdf_zoom_step))
        self.update()

    @interactive
    def zoom_fit_text_width(self):
        self.read_mode = "fit_to_customize"
        page_index = self.start_page_index
        text_width = self.document._document_page_clip.width
        self.scale_to(self.rect().width() * 0.99 / text_width)
        self.scroll_center_horizontal()
        self.update()

    @interactive
    def zoom_reset(self, read_mode="fit_to_width"):
        if self.is_mark_search:
            self.cleanup_search()
        self.read_mode = read_mode
        self.update_scale()
        self.update()

    @interactive
    def toggle_trim_white_margin(self):
        current_page_index = self.start_page_index
        self.document.toggle_trim_margin()
        self.page_cache_pixmap_dict.clear()
        self.update()
        self.jump_to_page(current_page_index)

    @interactive
    def toggle_inverted_mode(self):
        # Need clear page cache first, otherwise current page will not inverted until next page.
        self.page_cache_pixmap_dict.clear()

        self.inverted_mode = not self.inverted_mode
        self.update()
        return

    @interactive
    def toggle_inverted_image_mode(self):
        # Toggle inverted image status.
        if not self.document.isPDF:
            message_to_emacs("Only support PDF!")
            return

        self.page_cache_pixmap_dict.clear()
        self.inverted_image_mode = not self.inverted_image_mode

        # Re-render page.
        self.update()

    @interactive
    def toggle_mark_link(self): #  mark_link will add underline mark on link, using prompt link position.
        self.is_mark_link = not self.is_mark_link and self.document.isPDF
        self.page_cache_pixmap_dict.clear()
        self.update()

    def update_rotate(self, rotate):
        if self.document.isPDF:
            current_page_index = self.start_page_index
            self.rotation = rotate
            self.page_width, self.page_height = self.page_height, self.page_width

            # Need clear page cache first, otherwise current page will not inverted until next page.
            self.page_cache_pixmap_dict.clear()
            self.update_scale()
            self.update()
            self.jump_to_page(current_page_index)
        else:
            message_to_emacs("Only support PDF!")

    @interactive
    def rotate_clockwise(self):
        self.update_rotate((self.rotation + 90) % 360)

    def add_annot_of_action(self, annot_action):
        new_annot = None
        page = self.document[annot_action.page_index]
        quads = annot_action.annot_quads
        if (annot_action.annot_type == fitz.PDF_ANNOT_HIGHLIGHT):
            new_annot = page.addHighlightAnnot(quads)
            new_annot.setColors(stroke=annot_action.annot_stroke_color)
            new_annot.update()
        elif (annot_action.annot_type == fitz.PDF_ANNOT_STRIKE_OUT):
            new_annot = page.addStrikeoutAnnot(quads)
        elif (annot_action.annot_type == fitz.PDF_ANNOT_UNDERLINE):
            new_annot = page.addUnderlineAnnot(quads)
            new_annot.setColors(stroke=annot_action.annot_stroke_color)
            new_annot.update()
        elif (annot_action.annot_type == fitz.PDF_ANNOT_SQUIGGLY):
            new_annot = page.addSquigglyAnnot(quads)
        elif (annot_action.annot_type == fitz.PDF_ANNOT_TEXT):
            new_annot = page.addTextAnnot(annot_action.annot_top_left_point,
                                          annot_action.annot_content, icon="Note")
        elif (annot_action.annot_type == fitz.PDF_ANNOT_FREE_TEXT):
            color = QColor(self.inline_text_annot_color)
            color_r, color_g, color_b = color.redF(), color.greenF(), color.blueF()
            text_color = [color_r, color_g, color_b]
            new_annot = page.addFreetextAnnot(annot_action.annot_rect,
                                              annot_action.annot_content,
                                              fontsize=self.inline_text_annot_fontsize,
                                              fontname="Arial",
                                              text_color=text_color, align=0)

        if new_annot:
            new_annot.setInfo(title=annot_action.annot_title)
            new_annot.parent = page
            self.save_annot()

    def delete_annot_of_action(self, annot_action):
        page = self.document[annot_action.page_index]
        annot = AnnotAction.find_annot_of_annot_action(page, annot_action)
        if annot:
            page.deleteAnnot(annot)
            self.save_annot()

    @interactive
    def rotate_counterclockwise(self):
        self.update_rotate((self.rotation - 90) % 360)

    @interactive
    def undo_annot_action(self):
        if (self.annot_action_index < 0):
            message_to_emacs("No further undo action!")
        else:
            annot_action = self.annot_action_sequence[self.annot_action_index]
            self.annot_action_index = self.annot_action_index - 1
            if annot_action:
                self.jump_to_page(annot_action.page_index + 1)
                if annot_action.action_type == "Add":
                    self.delete_annot_of_action(annot_action)
                elif annot_action.action_type == "Delete":
                    self.add_annot_of_action(annot_action)
                message_to_emacs("Undo last action!")
            else:
                message_to_emacs("Invalid annot action.")

    @interactive
    def redo_annot_action(self):
        if (self.annot_action_index + 1 >= len(self.annot_action_sequence)):
            message_to_emacs("No further redo action!")
        else:
            self.annot_action_index = self.annot_action_index + 1
            annot_action = self.annot_action_sequence[self.annot_action_index]
            self.jump_to_page(annot_action.page_index + 1)

            if annot_action.action_type == "Add":
                self.add_annot_of_action(annot_action)
            elif annot_action.action_type == "Delete":
                self.delete_annot_of_action(annot_action)

            message_to_emacs("Redo last action!")


    def add_mark_jump_link_tips(self):
        self.is_jump_link = True and self.document.isPDF
        self.page_cache_pixmap_dict.clear()
        self.update()

    def jump_to_link(self, key):
        key = key.upper()
        if key in self.jump_link_key_cache_dict:
            self.handle_jump_to_link(self.jump_link_key_cache_dict[key])
        self.cleanup_links()

    def handle_jump_to_link(self, link):
        if "page" in link:
            self.cleanup_links()

            self.save_current_pos()
            self.jump_to_page(link["page"] + 1)

            message_to_emacs("Landed on Page " + str(link["page"] + 1))
        elif "uri" in link:
            self.cleanup_links()

            open_url_in_new_tab(link["uri"])
            message_to_emacs("Open " + link["uri"])

    def cleanup_links(self):
        self.is_jump_link = False
        self.page_cache_pixmap_dict.clear()
        self.update()

    def search_text(self, text):
        self.is_mark_search = True
        self.search_term = text

        self.search_text_index = 0
        for page_index in range(self.page_total_number):
            quads_list = self.document.searchPageFor(page_index, text, hit_max=999, quads=True)
            if quads_list:
                for index, quad in enumerate(quads_list):
                    search_text_offset = (page_index * self.page_height + quad.ul.y) * self.scale

                    self.search_text_offset_list.append(search_text_offset)
                    if search_text_offset > self.scroll_offset and search_text_offset < (self.scroll_offset + self.rect().height()):
                        self.search_text_index = index

        if(len(self.search_text_offset_list) == 0):
            message_to_emacs("No results found with \"" + text + "\".")
            self.is_mark_search = False
        else:
            self.page_cache_pixmap_dict.clear()
            self.update()
            self.update_vertical_offset(self.search_text_offset_list[self.search_text_index])
            message_to_emacs("Found " + str(len(self.search_text_offset_list)) + " results with \"" + text + "\".")

    def jump_next_match(self):
        if len(self.search_text_offset_list) > 0:
            self.search_text_index = (self.search_text_index + 1) % len(self.search_text_offset_list)
            self.update_vertical_offset(self.search_text_offset_list[self.search_text_index])
            message_to_emacs("Match " + str(self.search_text_index + 1) + "/" + str(len(self.search_text_offset_list)))

    def jump_last_match(self):
        if len(self.search_text_offset_list) > 0:
            self.search_text_index = (self.search_text_index - 1) % len(self.search_text_offset_list)
            self.update_vertical_offset(self.search_text_offset_list[self.search_text_index])
            message_to_emacs("Match " + str(self.search_text_index + 1) + "/" + str(len(self.search_text_offset_list)))

    def cleanup_search(self):
        self.is_mark_search = False
        self.search_term = None
        self.page_cache_pixmap_dict.clear()
        self.search_text_offset_list.clear()
        self.update()

    def get_select_char_list(self):
        page_dict = {}
        if self.start_char_rect_index and self.last_char_rect_index:
            # start and last page
            sp_index = min(self.start_char_page_index, self.last_char_page_index)
            lp_index = max(self.start_char_page_index, self.last_char_page_index)
            for page_index in range(sp_index, lp_index + 1):
                page_char_list = self.document[page_index].get_page_char_rect_list()

                if page_char_list:
                # handle forward select and backward select on multi page.
                # backward select on multi page.
                    if self.start_char_page_index > self.last_char_page_index:
                        sc = self.last_char_rect_index if page_index == sp_index else 0
                        lc = self.start_char_rect_index if page_index == lp_index else len(page_char_list)
                    else:
                        # forward select on multi page.
                        sc = self.start_char_rect_index if page_index == sp_index else 0
                        lc = self.last_char_rect_index if page_index == lp_index else len(page_char_list)

                    # handle forward select and backward select on same page.
                    sc_index = min(sc, lc)
                    lc_index = max(sc, lc)

                    page_dict[page_index] = page_char_list[sc_index : lc_index + 1]

        return page_dict

    def parse_select_char_list(self):
        string = ""
        page_dict = self.get_select_char_list()
        for index, chars_list in enumerate(page_dict.values()):
            if chars_list:
                string += "".join(list(map(lambda x: x["c"], chars_list)))

                if index != 0:
                    string += "\n\n"    # add new line on page end.
        return string

    def record_new_annot_action(self, annot_action):
        num_action_removed = len(self.annot_action_sequence) - (self.annot_action_index + 1)
        if num_action_removed > 0:
            del self.annot_action_sequence[-num_action_removed:]
        self.annot_action_sequence.append(annot_action)
        self.annot_action_index += 1

    def annot_select_char_area(self, annot_type="highlight", text=None):
        self.cleanup_select()   # needs first cleanup select highlight mark.
        for page_index, quads in self.select_area_annot_quad_cache_dict.items():
            page = self.document[page_index]

            if annot_type == "highlight":
                new_annot = page.addHighlightAnnot(quads)
                qcolor = QColor(self.text_highlight_annot_color)
                new_annot.setColors(stroke=qcolor.getRgbF()[0:3])
                new_annot.update()
            elif annot_type == "strikeout":
                new_annot = page.addStrikeoutAnnot(quads)
            elif annot_type == "underline":
                new_annot = page.addUnderlineAnnot(quads)
                qcolor = QColor(self.text_underline_annot_color)
                new_annot.setColors(stroke=qcolor.getRgbF()[0:3])
                new_annot.update()
            elif annot_type == "squiggly":
                new_annot = page.addSquigglyAnnot(quads)
            elif annot_type == "text":
                point = quads[-1].lr # lower right point
                new_annot = page.addTextAnnot(point, text, icon="Note")

            new_annot.setInfo(title=self.user_name)
            new_annot.parent = page

            annot_action = AnnotAction.create_annot_action("Add", page_index, new_annot)
            self.record_new_annot_action(annot_action)

        self.document.saveIncr()
        self.select_area_annot_quad_cache_dict.clear()

    def annot_popup_text_annot(self, text=None):
        (point, page_index) = self.popup_text_annot_pos
        if point == None or page_index == None:
            return

        page = self.document[page_index]
        new_annot = page.addTextAnnot(point, text, icon="Note")
        new_annot.setInfo(title=self.user_name)
        new_annot.parent = page

        annot_action = AnnotAction.create_annot_action("Add", page_index, new_annot)
        self.record_new_annot_action(annot_action)

        self.save_annot()
        self.disable_popup_text_annot_mode()

    def compute_annot_rect_inline_text(self, point, fontsize, text=None):
        text_lines = text.splitlines()
        longest_line = max(text_lines, key=len)
        annot_rect = fitz.Rect(point,
                               point.x + (fontsize / 1.5) * len(longest_line),
                               point.y + (fontsize * 1.3) * len(text_lines))
        return annot_rect


    def annot_inline_text_annot(self, text=None):
        (point, page_index) = self.inline_text_annot_pos
        if point == None or page_index == None:
            return

        page = self.document[page_index]
        fontname = "Arial"
        fontsize = self.inline_text_annot_fontsize
        annot_rect = self.compute_annot_rect_inline_text(point, fontsize, text)
        color = QColor(self.inline_text_annot_color)
        color_r, color_g, color_b = color.redF(), color.greenF(), color.blueF()
        text_color = [color_r, color_g, color_b]
        new_annot = page.addFreetextAnnot(annot_rect, text,
                                          fontsize=fontsize, fontname=fontname,
                                          text_color=text_color, align = 0)
        new_annot.setInfo(title=self.user_name)
        new_annot.parent = page

        annot_action = AnnotAction.create_annot_action("Add", page_index, new_annot)
        self.record_new_annot_action(annot_action)

        self.save_annot()
        self.disable_inline_text_annot_mode()

    def cleanup_select(self):
        self.is_select_mode = False
        self.delete_all_mark_select_area()
        self.page_cache_pixmap_dict.clear()
        self.update()

    def mark_select_char_area(self):
        page_dict = self.get_select_char_list()
        for page_index, chars_list in page_dict.items():
            # Using multi line rect make of abnormity select area.
            line_rect_list = []
            if chars_list:
                # every char has bbox property store char rect.
                bbox_list = list(map(lambda x: x["bbox"], chars_list))

                # With char order is left to right, if the after char x-axis more than before
                # char x-axis, will determine have "\n" between on both.
                if len(bbox_list) >= 2:
                    tl_x, tl_y = 0, 0 # top left point
                    for index, bbox in enumerate(bbox_list[:-1]):
                        if (tl_x == 0) or (tl_y == 0):
                            tl_x, tl_y = bbox[:2]
                        if bbox[0] > bbox_list[index + 1][2]:
                            br_x, br_y = bbox[2:] # bottom right
                            line_rect_list.append((tl_x, tl_y, br_x, br_y))
                            tl_x, tl_y = 0, 0

                    lc = bbox_list[-1]  # The last char
                    line_rect_list.append((tl_x, tl_y, lc[2], lc[3]))
                else:
                    # if only one char selected.
                    line_rect_list.append(bbox_list[0])

            def check_rect(rect):
                tl_x, tl_y, br_x, br_y = rect
                if tl_x <= br_x and tl_y <= br_y:
                    return fitz.Rect(rect)
                # discard the illegal rect. return a micro rect
                return fitz.Rect(tl_x, tl_y, tl_x+1, tl_y+1)

            line_rect_list = list(map(check_rect, line_rect_list))

            page = self.document[page_index]
            old_annot = self.select_area_annot_cache_dict[page_index]
            if old_annot:
                page.deleteAnnot(old_annot)

            quad_list = list(map(lambda x: x.quad, line_rect_list))
            annot = page.addHighlightAnnot(quad_list)
            annot.parent = page

            # refresh annot
            self.select_area_annot_cache_dict[page_index] = annot
            self.select_area_annot_quad_cache_dict[page_index] = quad_list

        self.page_cache_pixmap_dict.clear()
        self.update()

    def delete_all_mark_select_area(self):
        if self.select_area_annot_cache_dict:
            for page_index, annot in self.select_area_annot_cache_dict.items():
                if annot and annot.parent:
                        annot.parent.deleteAnnot(annot)
                self.select_area_annot_cache_dict[page_index] = None # restore cache
        self.last_char_page_index = None
        self.last_char_rect_index = None
        self.start_char_page_index = None
        self.start_char_rect_index = None

    def get_annots(self, page_index, types=None):
        '''
        Return a list of annotations on page_index of types.
        '''
        # Notes: annots need the pymupdf above 1.16.4 version.
        page = self.document[page_index]
        return page.annots(types)

    def find_annot_by_id(self, page, annot_id):
        annot = page.firstAnnot
        if not annot:
            return None

        while annot:
            if annot.info["id"] == annot_id:
                return annot
            annot = annot.next

        return None

    def hover_annot(self, print_msg):
        try:
            if self.is_move_text_annot_mode:
                return None, None

            ex, ey, page_index = self.get_cursor_absolute_position()
            page = self.document[page_index]
            annot = page.firstAnnot
            if not annot:
                return None, None

            annots = []
            while annot:
                annots.append(annot)
                annot = annot.next

            is_hover_annot = False
            is_hover_tex_annot = False
            current_annot = None

            for annot in annots:
                if annot.info["title"] and fitz.Point(ex, ey) in annot.rect:
                    is_hover_annot = True
                    current_annot = annot
                    opacity = 0.5
                    if current_annot.type[0] == fitz.PDF_ANNOT_TEXT or \
                       current_annot.type[0] == fitz.PDF_ANNOT_FREE_TEXT:
                        is_hover_tex_annot = True
                else:
                    opacity = 1.0
                if opacity != annot.opacity:
                    annot.setOpacity(opacity)
                    annot.update()

            # update and print message only if changed
            if is_hover_annot != self.is_hover_annot:
                if print_msg and self.is_buffer_focused():
                    if not is_hover_annot:
                        eval_in_emacs("eaf--clear-message", [])
                    elif is_hover_tex_annot:
                        message_to_emacs("[M-d]Delete annot [M-e]Edit text annot [M-r]Move text annot")
                    else:
                        message_to_emacs("[M-d]Delete annot")
                self.is_hover_annot = is_hover_annot
                self.page_cache_pixmap_dict.clear()
                self.update()

            if current_annot and current_annot.info["content"]:
                if current_annot.info["id"] != self.last_hover_annot_id or not QToolTip.isVisible():
                    QToolTip.showText(QCursor.pos(), current_annot.info["content"], None, QRect(), 10 * 1000)
                self.last_hover_annot_id = current_annot.info["id"]
            else:
                if QToolTip.isVisible():
                    QToolTip.hideText()

            return page, current_annot
        except Exception as e:
            print("Hove Annot: ", e)
            return None, None

    def save_annot(self):
        self.document.saveIncr()
        self.page_cache_pixmap_dict.clear()
        self.update()

    def annot_handler(self, action=None):
        page, annot = self.hover_annot(False)
        if annot.parent:
            if action == "delete":
                annot_action = AnnotAction.create_annot_action("Delete", page.page_index, annot)
                self.record_new_annot_action(annot_action)
                page.deleteAnnot(annot)
                self.save_annot()
            elif action == "edit":
                self.edited_annot_page = (annot, page)
                if annot.type[0] == fitz.PDF_ANNOT_TEXT or \
                   annot.type[0] == fitz.PDF_ANNOT_FREE_TEXT:
                    atomic_edit(self.buffer_id, annot.info["content"].replace("\r", "\n"))
            elif action == "move":
                self.moved_annot_page = (annot, page)
                if annot.type[0] == fitz.PDF_ANNOT_TEXT or \
                   annot.type[0] == fitz.PDF_ANNOT_FREE_TEXT:
                    self.enable_move_text_annot_mode()

    def edit_annot_text(self, annot_text):
        annot, page = self.edited_annot_page
        if annot.parent:
            if annot.type[0] == fitz.PDF_ANNOT_TEXT:
                annot.setInfo(content=annot_text)
                message_to_emacs("Updated popup text annot!")
            elif annot.type[0] == fitz.PDF_ANNOT_FREE_TEXT:
                annot.setInfo(content=annot_text)
                point = annot.rect.top_left
                fontsize = self.inline_text_annot_fontsize
                rect = self.compute_annot_rect_inline_text(point, fontsize, annot_text)
                annot.setRect(rect)
                message_to_emacs("Updated inline text annot!")
            annot.update()
            self.save_annot()
        self.edited_annot_page = (None, None)

    def move_annot_text(self):
        annot, page = self.moved_annot_page
        if annot.parent:
            if annot.type[0] == fitz.PDF_ANNOT_TEXT or \
               annot.type[0] == fitz.PDF_ANNOT_FREE_TEXT:
                (point, page_index) = self.move_text_annot_pos
                rect = annot.rect
                new_rect = fitz.Rect(point, point.x + rect.width, point.y + rect.height)
                annot.setRect(new_rect)
                annot.update()
                self.save_annot()
        self.moved_annot_page = (None, None)
        self.disable_move_text_annot_mode()

    def jump_to_page(self, page_num):
        self.update_vertical_offset(min(max(self.scale * (int(page_num) - 1) * self.page_height, 0), self.max_scroll_offset()))

    def jump_to_percent(self, percent):
        self.update_vertical_offset(min(max(self.scale * (self.page_total_number * self.page_height * percent / 100.0), 0), self.max_scroll_offset()))

    def jump_to_rect(self, page_index, rect):
        quad = rect.quad
        self.update_vertical_offset((page_index * self.page_height + quad.ul.y) * self.scale)

    def current_percent(self):
        return 100.0 * self.scroll_offset / (self.max_scroll_offset() + self.rect().height())

    def update_vertical_offset(self, new_offset):
        eval_in_emacs("eaf--clear-message", [])
        if self.scroll_offset != new_offset:
            self.scroll_offset = new_offset
            self.update()

            current_page = math.floor((self.start_page_index + self.last_page_index + 1) / 2)
            eval_in_emacs("eaf--pdf-update-position", [self.buffer_id,
                                                       current_page,
                                                       self.page_total_number])

    def update_horizontal_offset(self, new_offset):
        eval_in_emacs("eaf--clear-message", [])
        if self.horizontal_offset != new_offset:
            self.horizontal_offset = new_offset
            self.update()

    def get_cursor_absolute_position(self):
        pos = self.mapFromGlobal(QCursor.pos()) # map global coordinate to widget coordinate.
        ex, ey = pos.x(), pos.y()

        # set page coordinate
        render_width = self.page_width * self.scale
        render_x = int((self.rect().width() - render_width) / 2)
        if self.read_mode == "fit_to_customize" and render_width >= self.rect().width():
            render_x = max(min(render_x + self.horizontal_offset, 0), self.rect().width() - render_width)

        # computer absolute coordinate of page
        x = (ex - render_x) * 1.0 / self.scale
        if ey + self.scroll_offset < (self.start_page_index + 1) * self.scale * self.page_height:
            page_offset = self.scroll_offset - self.start_page_index * self.scale * self.page_height
            page_index = self.start_page_index
        else:
            # if display two pages, pos.y() will add page_padding
            page_offset = self.scroll_offset - (self.start_page_index + 1) * self.scale * self.page_height - self.page_padding
            page_index = self.start_page_index + 1
        y = (ey + page_offset) * 1.0 / self.scale

        temp = x
        if self.rotation == 90:
            x = y
            y = self.page_width - temp
        elif self.rotation == 180:
            x = self.page_width - x
            y = self.page_height - y
        elif self.rotation == 270:
            x = self.page_height - y
            y = temp

        return x, y, page_index

    def get_event_link(self):
        ex, ey, page_index = self.get_cursor_absolute_position()
        if page_index is None:
            return None

        page = self.document[page_index]
        for link in page.getLinks():
            rect = link["from"]
            if ex >= rect.x0 and ex <= rect.x1 and ey >= rect.y0 and ey <= rect.y1:
                return link

        return None

    def get_double_click_word(self):
        ex, ey, page_index = self.get_cursor_absolute_position()
        if page_index is None:
            return None
        page = self.document[page_index]
        word_offset = 10 # 10 pixel is enough for word intersect operation
        draw_rect = fitz.Rect(ex, ey, ex + word_offset, ey + word_offset)

        page.setCropBox(page.rect)
        page_words = page.getTextWords()
        rect_words = [w for w in page_words if fitz.Rect(w[:4]).intersect(draw_rect)]
        if rect_words:
            return rect_words[0][4]

    def eventFilter(self, obj, event):
        if event.type() in [QEvent.MouseMove, QEvent.MouseButtonDblClick, QEvent.MouseButtonPress]:
            if not self.document.isPDF:
                return False

        if event.type() == QEvent.MouseMove:
            if self.hasMouseTracking():
                self.hover_annot(True)
            else:
                self.handle_select_mode()

        elif event.type() == QEvent.MouseButtonPress:
            # add this detect release mouse event
            self.grabMouse()

            # cleanup select mode on another click
            if self.is_select_mode:
                self.cleanup_select()

            if self.is_popup_text_annot_mode:
                if event.button() != Qt.LeftButton:
                    self.disable_popup_text_annot_mode()
            elif self.is_inline_text_annot_mode:
                if event.button() != Qt.LeftButton:
                    self.disable_inline_text_annot_mode()
            elif self.is_move_text_annot_mode:
                if event.button() != Qt.LeftButton:
                    self.disable_move_text_annot_mode()
            else:
                if event.button() == Qt.LeftButton:
                    # In order to catch mouse move event when drap mouse.
                    self.setMouseTracking(False)
                elif event.button() == Qt.RightButton:
                    self.handle_click_link()

        elif event.type() == QEvent.MouseButtonRelease:
            # Capture move event, event without holding down the mouse.
            self.setMouseTracking(True)
            self.releaseMouse()
            if not self.popup_text_annot_timer.isActive() and \
               self.is_popup_text_annot_handler_waiting:
                self.popup_text_annot_timer.start()

            if not self.inline_text_annot_timer.isActive() and \
               self.is_inline_text_annot_handler_waiting:
                self.inline_text_annot_timer.start()

            if not self.move_text_annot_timer.isActive() and \
               self.is_move_text_annot_handler_waiting:
                self.move_text_annot_timer.start()

            if platform.system() == "Darwin":
                eval_in_emacs('eaf-activate-emacs-window', [])

        elif event.type() == QEvent.MouseButtonDblClick:
            self.disable_popup_text_annot_mode()
            self.disable_inline_text_annot_mode()
            if event.button() == Qt.RightButton:
                self.handle_translate_word()
            elif event.button() == Qt.LeftButton:
                self.handle_synctex_backward_edit()
                return True

        return False

    def enable_popup_text_annot_mode(self):
        self.is_popup_text_annot_mode = True
        self.is_popup_text_annot_handler_waiting = True
        self.popup_text_annot_pos = (None, None)

    def disable_popup_text_annot_mode(self):
        self.is_popup_text_annot_mode = False
        self.is_popup_text_annot_handler_waiting = False

    def handle_popup_text_annot_mode(self):
        if self.is_popup_text_annot_mode:
            self.is_popup_text_annot_handler_waiting = False
            ex, ey, page_index = self.get_cursor_absolute_position()
            self.popup_text_annot_pos = (fitz.Point(ex, ey), page_index)

            atomic_edit(self.buffer_id, "")

    def enable_inline_text_annot_mode(self):
        self.is_inline_text_annot_mode = True
        self.is_inline_text_annot_handler_waiting = True
        self.inline_text_annot_pos = (None, None)

    def disable_inline_text_annot_mode(self):
        self.is_inline_text_annot_mode = False
        self.is_inline_text_annot_handler_waiting = False

    def handle_inline_text_annot_mode(self):
        if self.is_inline_text_annot_mode:
            self.is_inline_text_annot_handler_waiting = False
            ex, ey, page_index = self.get_cursor_absolute_position()
            self.inline_text_annot_pos = (fitz.Point(ex, ey), page_index)

            atomic_edit(self.buffer_id, "")

    def enable_move_text_annot_mode(self):
        self.is_move_text_annot_mode = True
        self.is_move_text_annot_handler_waiting = True
        self.move_text_annot_pos = (None, None)

    def disable_move_text_annot_mode(self):
        self.is_move_text_annot_mode = False
        self.is_move_text_annot_handler_waiting = False

    def handle_move_text_annot_mode(self):
        if self.is_move_text_annot_mode:
            self.is_move_text_annot_handler_waiting = False
            ex, ey, page_index = self.get_cursor_absolute_position()
            self.move_text_annot_pos = (fitz.Point(ex, ey), page_index)
            self.move_annot_text()

    def handle_select_mode(self):
        self.is_select_mode = True
        ex, ey, page_index = self.get_cursor_absolute_position()
        rect_index = self.document[page_index].get_page_char_rect_index(ex, ey)
        if rect_index and page_index is not None:
            if self.start_char_rect_index is None or self.start_char_page_index is None:
                self.start_char_rect_index, self.start_char_page_index = rect_index, page_index
            else:
                self.last_char_rect_index, self.last_char_page_index = rect_index, page_index
                self.mark_select_char_area()

    def handle_click_link(self):
        event_link = self.get_event_link()
        if event_link:
            self.handle_jump_to_link(event_link)

    def handle_translate_word(self):
        double_click_word = self.get_double_click_word()
        if double_click_word:
            self.translate_double_click_word.emit(double_click_word)

    def handle_synctex_backward_edit(self):
        ex, ey, page_index = self.get_cursor_absolute_position()
        if page_index is not None:
            eval_in_emacs("eaf-pdf-synctex-backward-edit", [self.url, page_index + 1, ex, ey])


# utils function
def inverted_color(color, inverted=False):
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
    key_list = []
    key_len = 1 if count == 1 else math.ceil(math.log(count) / math.log(len(letters)))
    while count > 0:
        key = ''.join(random.choices(letters, k=key_len))
        if key not in key_list:
            key_list.append(key)
            count -= 1
    return key_list
