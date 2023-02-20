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


from PyQt6.QtCore import QRect, QRectF
from PyQt6.QtGui import QColor, QPixmap, QImage, QCursor
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QToolTip
from core.utils import (message_to_emacs, get_emacs_vars)
import fitz

from eaf_pdf_utils import generate_random_key, support_hit_max

def set_page_crop_box(page):
    if hasattr(page, "set_cropbox"):
        return page.set_cropbox
    else:
        return page.setCropBox

def get_page_text(page):
    if hasattr(page, "get_text"):
        return page.get_text
    else:
        return page.getText

def set_page_rotation(page):
    if hasattr(page, "set_rotation"):
        return page.set_rotation
    else:
        return page.setRotation

def get_page_pixmap(page):
    if hasattr(page, "get_pixmap"):
        return page.get_pixmap
    else:
        return page.getPixmap

def pixmap_invert_irect(pixmap):
    if hasattr(pixmap, "invert_irect"):
        return pixmap.invert_irect
    else:
        return pixmap.invertIRect

def get_page_image_list(page):
    if hasattr(page, "get_images"):
        return page.get_images
    else:
        return page.getImageList

def get_page_image_bbox(page):
    if hasattr(page, "get_image_bbox"):
        return page.get_image_bbox
    else:
        return page.getImageBbox

class PdfPage(fitz.Page):
    def __init__(self, page, page_index, is_pdf, clip=None):
        self.page = page
        self.page_index = page_index
        self.is_pdf = is_pdf
        self.clip = clip or page.cropbox

        self._mark_link_annot_list = []
        self._mark_search_annot_list = []
        self._mark_jump_annot_list = []

        self._page_rawdict = self._init_page_rawdict()
        self._page_char_rect_list = self._init_page_char_rect_list()
        self._tight_margin_rect = self._init_tight_margin()

        self.has_annot = page.first_annot
        self.hovered_annot = None

    def __getattr__(self, attr):
        return getattr(self.page, attr)

    def _init_page_rawdict(self):
        if self.is_pdf:
            try:
                # Must set CropBox before get page rawdict , if no,
                # the rawdict bbox coordinate is wrong
                # cause the select text failed
                set_page_crop_box(self.page)(self.clip)
                d = get_page_text(self.page)("rawdict")
                # cancel the cropbox, if not, will cause the pixmap set cropbox
                # don't begin on top-left(0, 0), page display black margin
                set_page_crop_box(self.page)(fitz.Rect(self.page.mediabox.x0,0,self.page.mediabox.x1,self.page.mediabox.y1-self.page.mediabox.y0))
                return d
            except:
                return get_page_text(self.page)("rawdict")
        else:
            return get_page_text(self.page)("rawdict")

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
            return self.page.cropbox
        return r

    def get_tight_margin_rect(self):
        # if current page don't computer tight rect
        # return None
        if self._tight_margin_rect == self.page.mediabox:
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
            if fitz.Rect(char["bbox"]).intersects(rect):
                return char_index
        return None

    def set_rotation(self, rotation):
        set_page_rotation(self.page)(rotation)
        if rotation % 180 != 0:
            self.page_width = self.page.cropbox.height
            self.page_height = self.page.cropbox.width
        else:
            self.page_width = self.page.cropbox.width
            self.page_height = self.page.cropbox.height

    def get_qpixmap(self, scale, invert, invert_image=False):
        if self.is_pdf:
            try:
                set_page_crop_box(self.page)(self.clip)
            except:
                pass

        pixmap = get_page_pixmap(self.page)(matrix=fitz.Matrix(scale, scale), alpha=True)

        # make background transparent
        sample_color = pixmap.pixel(0,0)
        if sample_color[3] == 255:
            pixmap = self.make_background_transparent(pixmap, sample_color[:3])
        elif sample_color[3] == 0:
            pixmap = self.make_background_transparent(pixmap, (255,255,255))

        if invert:
            pixmap_invert_irect(pixmap)(pixmap.irect)

        if not invert_image and invert:
            pixmap = self.with_invert_exclude_image(scale, pixmap)

        img = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGBA8888)
        qpixmap = QPixmap.fromImage(img)

        if self.has_annot:
            qpixmap = self.draw_annots(qpixmap, scale)

        return qpixmap

    def draw_annots(self, pixmap, scale):
        if self.hovered_annot is None:
            return pixmap

        qp = QPainter(pixmap)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationAtop)
        annot = self.hovered_annot

        r, g, b = getattr(annot.colors, "stroke", (1.0, 0.84, 0.08))
        color = QColor(int(r) * 255, int(g) * 255, int(b) * 255, 153)

        vertices = annot.vertices
        if vertices is not None and len(vertices) % 4 == 0:
            for i in range(0, len(vertices), 4):
                # top-left and bottom-right point
                rect = fitz.Rect(vertices[i], vertices[i+3]) * scale
                qrect = QRectF(rect.x0, rect.y0, rect.width, rect.height)
                qp.fillRect(qrect, color)
        else:
            rect = annot.rect
            qrect = QRectF(rect.x0, rect.y0, rect.width, rect.height)
            qp.fillRect(qrect, color)

        if annot and annot.info["content"]:
            QToolTip.showText(QCursor.pos(), annot.info["content"], None, QRect(), 10 * 1000)
        else:
            if QToolTip.isVisible():
                QToolTip.hideText()

        return pixmap

    def can_update_annot(self, page_x, page_y):
        if not self.has_annot:
            return None, False

        point = fitz.Point(page_x, page_y)
        for annot in self.page.annots():
            if point in annot.rect:
                self.hovered_annot = annot
                return annot, True

        if self.hovered_annot is not None:
            self.hovered_annot = None
            return None, True

        return None, False

    def make_background_transparent(self, pixmap, opaque_color):
        pixalpha = fitz.Pixmap(None, pixmap)
        alpha = pixalpha.samples
        pixmap.set_alpha(alpha, 1, opaque=opaque_color)
        return pixmap

    def with_invert_exclude_image(self, scale, pixmap):
        # steps:
        # First, make page all content is invert, include image and text.
        # if exclude image is True, will find the page all image, then get
        # each image rect. Finally, again invert all image rect.

        self.page.clean_contents()
        # exclude image only support PDF document
        imagelist = None
        try:
            imagelist = get_page_image_list(self.page)(full=True)
        except Exception:
            # PyMupdf 1.14 not include argument 'full'.
            imagelist = get_page_image_list(self.page)

        page_words = self.page.get_text_words()

        image_rects = []
        for image in imagelist:
            try:
                imagerect, _ = get_page_image_bbox(self.page)(image, True)
                # Don't invert image if it is infinite, empty or intersect with words.
                if imagerect.is_infinite or imagerect.is_empty or self.image_intersect_with_words(imagerect, page_words):
                    continue

                intersects = []
                for rect in image_rects:
                    intersect = fitz.Rect(rect).intersect(imagerect)
                    if intersect.is_infinite or intersect.is_empty:
                        continue
                    intersects.append(intersect)

                image_rects.append(imagerect)
                image_rects.extend(intersects)

            except Exception:
                import traceback
                traceback.print_exc()

        for rect in image_rects:
            pixmap_invert_irect(pixmap)(rect * self.page.rotation_matrix * scale)

        return pixmap

    def image_intersect_with_words(self, imagerect, page_words):
        "If a image intersect with page words, there is a high probability that this picture is a watermark."
        for page_word in page_words:
            if fitz.Rect(page_word[:4]).intersects(imagerect):
                return True

        return False

    def add_mark_link(self):
        if self.page.first_link:
            for link in self.page.get_links():
                annot = self.page.add_underline_annot(link["from"])
                annot.parent = self.page # Must assign annot parent, else delete_annot cause parent is None problem.
                self._mark_link_annot_list.append(annot)

    def cleanup_mark_link(self):
        if self._mark_link_annot_list:
            for annot in self._mark_link_annot_list:
                self.page.delete_annot(annot)
            self._mark_link_annot_list = []

    def mark_search_text(self, keyword, current_quads):
        self.cleanup_search_text()

        if support_hit_max:
            quads_list = self.page.searchFor(keyword, hit_max=999, quads=True)
        else:
            quads_list = self.page.search_for(keyword, quads=True)

        if quads_list:
            for quads in quads_list:
                annot = self.page.add_highlight_annot(quads)
                annot.parent = self.page
                if quads == current_quads:
                    qcolor = QColor("#f28100")
                    annot.set_colors(stroke=qcolor.getRgbF()[0:3])
                    annot.update()
                self._mark_search_annot_list.append(annot)

    def cleanup_search_text(self):
        if self._mark_search_annot_list:
            # message_to_emacs("Unmarked all matched results.")
            for annot in self._mark_search_annot_list:
                self.page.delete_annot(annot)
            self._mark_search_annot_list = []

    def mark_jump_link_tips(self, letters):
        fontsize, = get_emacs_vars(["eaf-pdf-marker-fontsize"])
        cache_dict = {}
        if self.page.first_link:
            links = self.page.get_links()
            key_list = generate_random_key(len(links), letters)
            for index, link in enumerate(links):
                key = key_list[index]
                link_rect = link["from"]
                annot_rect = fitz.Rect(link_rect.top_left, link_rect.x0 + fontsize/1.2 * len(key), link_rect.y0 + fontsize)
                annot = self.page.add_freetext_annot(annot_rect, str(key), fontsize=fontsize, fontname="Helv", \
                                                     text_color=[0.0, 0.0, 0.0], fill_color=[255/255.0, 197/255.0, 36/255.0], \
                                                     align = 1)
                annot.parent = self.page
                self._mark_jump_annot_list.append(annot)
                cache_dict[key] = link
        return cache_dict

    def cleanup_jump_link_tips(self):
        for annot in self._mark_jump_annot_list:
            self.page.delete_annot(annot)
        self._mark_jump_annot_list = []
