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

from PyQt6.QtGui import QColor
from core.buffer import Buffer
from core.utils import (eval_in_emacs, message_to_emacs,translate_text,
                        atomic_edit, get_emacs_vars, get_emacs_config_dir)
import fitz
import os
import threading

# hack: add current dir path to sys.path for relative path import other modules.
import sys
sys.path.append(os.path.dirname(__file__))

from eaf_pdf_widget import PdfViewerWidget

class SynctexInfo():
    def __init__(self, info):
        self.page_num = None
        self.pos_x = None
        self.pos_y = None

        if info.startswith("synctex_info"):
            self.parse_info(info.split("=")[1])

    def parse_info(self, content):
        synctex_info = content.split(":")
        if len(synctex_info) != 3:
            return

        self.page_num = int(synctex_info[0])
        self.pos_x = float(synctex_info[1])
        self.pos_y = float(synctex_info[2])

    def update(self, info):
        self.parse_info(info)

    def reset(self):
        self.page_num = None
        self.pos_x = None
        self.pos_y = None


class AppBuffer(Buffer):
    def __init__(self, buffer_id, url, arguments):
        Buffer.__init__(self, buffer_id, url, arguments, False)

        (buffer_background_color, self.store_history, self.pdf_dark_mode) = get_emacs_vars([
             "eaf-buffer-background-color",
             "eaf-pdf-store-history",
             "eaf-pdf-dark-mode"])

        self.delete_temp_file = arguments == "temp_pdf_file"

        self.synctex_info = SynctexInfo(arguments)
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
            from core.utils import touch

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
        sys.path.remove(os.path.dirname(__file__))

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
        if self.synctex_info.page_num == None:
            self.buffer_widget.scroll_offset = float(scroll_offset)
        self.buffer_widget.scale = float(scale)
        self.buffer_widget.read_mode = read_mode
        self.buffer_widget.rotation = int(rotation)
        self.buffer_widget.update()

    def jump_to_page(self):
        self.send_input_message("Jump to Page: ", "jump_page")

    def jump_to_page_with_num(self, num):
        self.buffer_widget.jump_to_page(int(num))

    def jump_to_page_synctex(self, info):
        self.buffer_widget.synctex_info.update(info)
        self.buffer_widget.jump_to_page(self.buffer_widget.synctex_info.page_num)
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
        import base64
        new_text = base64.b64decode(new_text).decode("utf-8")

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
        import json

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
        import json

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

    def delete_pdf_pages(self, pages):
        import re
        page_list = re.split(' +', pages)
        if len(page_list) > 1:
            start_page = int(page_list[0]) - 1
            end_page = int(page_list[1]) - 1
            if (start_page >= end_page):
                message_to_emacs(" start page must less than end page")
            elif (start_page < 0)  or (start_page > self.buffer_widget.page_total_number) :
                message_to_emacs(" start page err")
            elif (end_page < 0)  or (end_page > self.buffer_widget.page_total_number):
                message_to_emacs(" end page err")
            else:
                self.buffer_widget.delete_pdf_pages(start_page, end_page)
        else:
            page = int(page_list[0]) - 1
            if (page < 0)  or (page > self.buffer_widget.page_total_number):
                message_to_emacs("page err")
            else:
                self.buffer_widget.delete_pdf_page(page)

    def fetch_marker_callback(self):
        return list(map(lambda x: x.lower(), self.buffer_widget.jump_link_key_cache_dict.keys()))
