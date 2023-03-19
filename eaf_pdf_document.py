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

from core.utils import (message_to_emacs, get_emacs_vars)
import fitz
import functools

from eaf_pdf_page import PdfPage

def get_page_crop_box(page):
    if hasattr(page, "page_cropbox"):
        return page.page_cropbox
    else:
        return page.page_cropbox

def set_page_crop_box(page):
    if hasattr(page, "set_cropbox"):
        return page.set_cropbox
    else:
        return page.set_cropbox

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

            if page.cropbox == self._document_page_clip:
                return page

        page = PdfPage(self.document[index], index, self.document.is_pdf)

        # udpate the page clip
        new_rect_clip = self.computer_page_clip(page.get_tight_margin_rect(), self._document_page_clip)
        if new_rect_clip != self._document_page_clip:
            self._document_page_clip = new_rect_clip
            if self._is_trim_margin:
                self._document_page_change(new_rect_clip)

        if self._is_trim_margin:
            return PdfPage(self.document[index], index, self.document.is_pdf, self._document_page_clip)

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

            if self.watch_callback is not None:
                self.watch_callback(url)
            self.file_changed_timer.stop()
        except Exception:
            self.file_changed_timer.start()
            message_to_emacs("Failed to reload PDF file!")


    def cache_page(self, index, page):
        self._page_cache_dict[index] = page

    def remove_cache(self, index):
        self._page_cache_dict.pop(index)

    def reset_cache(self):
        self._page_cache_dict.clear()

    def watch_file(self, path, callback):
        '''
        Refresh content with PDF file changed.
        '''
        from PyQt6.QtCore import QFileSystemWatcher

        self.watch_callback = callback
        self.file_changed_wacher = QFileSystemWatcher()
        self.file_changed_wacher.addPath(path)
        self.file_changed_wacher.fileChanged.connect(self.handle_file_changed)

    def handle_file_changed(self, path):
        '''
        Use the QFileSystemWatcher watch file changed. If the watch file have been remove or rename,
        this watch will auto remove.
        '''
        from PyQt6.QtCore import QTimer
        if path in self.file_changed_wacher.files():
            self.file_changed_timer = QTimer()
            self.file_changed_timer.setInterval(500)
            self.file_changed_timer.setSingleShot(True)
            reload_callback = functools.partial(self.reload_document, path)
            self.file_changed_timer.timeout.connect(reload_callback)
            self.file_changed_timer.start()

            notify, = get_emacs_vars(["eaf-pdf-notify-file-changed"])
            if notify:
                message_to_emacs("Detected that {} has been changed. Refreshing buffer...".format(path))

    def toggle_trim_margin(self):
        self._is_trim_margin = not self._is_trim_margin

    def get_page_width(self):
        if self.is_pdf:
            if self._is_trim_margin:
                return self._document_page_clip.width
            return get_page_crop_box(self.document)(0).width
        else:
            return self[0].clip.width

    def get_page_height(self):
        if self.is_pdf:
            if self._is_trim_margin:
                return self._document_page_clip.height
            return get_page_crop_box(self.document)(0).height
        else:
            return self[0].clip.height

    def watch_page_size_change(self, callback):
        self._document_page_change = callback
