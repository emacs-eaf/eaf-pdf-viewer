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
fitz.TOOLS.unset_quad_corrections(True)
from core.utils import get_emacs_vars
from eaf_pdf_utils import generate_random_key, support_hit_max
from PyQt6.QtCore import QRect, QRectF
from PyQt6.QtGui import QColor, QCursor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QToolTip


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
        self._links = None
        self._annots = None

        self._page_rawdict = self._init_page_rawdict()
        # self._page_char_rect_list = self._init_page_char_rect_list()
        self._tight_margin_rect = self._init_tight_margin()
        
        self.hierarchy = ["", "blocks", "lines", "spans", "chars"]
        
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
                d = get_page_text(self.page)("rawdict", flags=fitz.TEXT_ACCURATE_BBOXES)
                return d
            except:
                return get_page_text(self.page)("rawdict", flags=fitz.TEXT_ACCURATE_BBOXES)
        else:
            return get_page_text(self.page)("rawdict", flags=fitz.TEXT_ACCURATE_BBOXES)

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
        xx0, yy0, xx1, yy1 = self.page.cropbox
        for block in self._page_rawdict["blocks"]:
            # ignore image bbox
            if block["type"] != 0:
                continue

            x0, y0, x1, y1 = block["bbox"]
            if x0 < xx0:
                xx0 = x0
            if y0 < yy0:
                yy0 = y0
            if x1 > xx1:
                xx1 = x1
            if y1 > yy1:
                yy1 = y1
        return fitz.Rect(xx0, yy0, xx1, yy1)

    def get_tight_margin_rect(self):
        # if current page don't computer tight rect
        # return None
        if self._tight_margin_rect == self.page.mediabox:
            return None
        return self._tight_margin_rect

    def get_page_char_rect_list(self):
        return self._page_char_rect_list

    def _get_intersect_block(self, rect):
        '''Get intersect block by rect.'''
        for i, block in enumerate(self._page_rawdict["blocks"]):
            # ignore image bbox
            if block["type"] != 0:
                continue
            
            if self._is_intersects(block["bbox"], rect):
                return i, block
        return None, None

    def _get_intersect_line(self, block, rect):
        '''Get intersect line by rect.'''
        for i, line in enumerate(block["lines"]):
            if self._is_intersects(line["bbox"], rect):
                return i, line
        return None, None
    
    def _get_intersect_span(self, line, rect):
        '''Get intersect span by rect.'''
        for i, span in enumerate(line["spans"]):
            if self._is_intersects(span["bbox"], rect):
                return i, span
        return None, None
    
    def _get_intersect_char(self, span, rect):
        '''Get intersect char by rect.'''
        for i, char in enumerate(span["chars"]):
            if self._is_intersects(char["bbox"], rect):
                return i, char
        return None, None
    
    def is_char_at_point(self, x, y):
        '''return if there is a char under the x and y coordinate.'''
        if x and y is None:
            return None

        offset = 5
        rect = (x-1, y, x + offset, y + offset)
        block_index, intersected_block = self._get_intersect_block(rect)
        if intersected_block is None:
            return None
        line_index, intersected_line = self._get_intersect_line(intersected_block, rect)
        if intersected_line is None:
            return None
        span_index, intersected_span = self._get_intersect_span(intersected_line, rect)
        if intersected_span is None:
            return None
        char_index, intersected_char = self._get_intersect_char(intersected_span, rect)
        if intersected_char is None:
            return None
        return block_index, line_index, span_index, char_index
    
    def get_line_at_point(self, x, y):
        '''get the line under the x and y coordinate.'''
        index = self.is_char_at_point(x, y)
        if index is None:
            return None
        block_index, line_index, span_index, char_index = index
        intersected_block = self._page_rawdict["blocks"][block_index]
        intersected_line = intersected_block["lines"][line_index]
        line = []
        for i, span in enumerate(intersected_line["spans"]):
            for j, char in enumerate(span["chars"]):
                line.append(char["c"])
        return "".join(line)
    
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
      
    def get_page_obj_rect_index(self, x, y):
        '''According X and Y coordinate return index of char in raw_dict.'''
        return self.is_char_at_point(x, y)
       
    
    def get_obj_from_range(self, start, end):
        """
        start and end are 4-tuple (block_index, line_index, span_index, char_index)
        """
        obj_list = []
        self._get_obj_from_range(self._page_rawdict["blocks"], start, end, obj_list)
        return obj_list
     
    
    def _get_obj_from_range(self, structs, start, end, collections):      
        """
        pre-order traverse the page rawdict and get the objects in the range of start and end.
        """    
        remain_level = len(start) - 1
        child_name = self.hierarchy[-remain_level]
        
        start_idx, end_idx = start[0], end[0]
        
        if end_idx == -1:
            end_idx = len(structs) - 1
            
        if remain_level == 0:
            # collect in the first block
            collections.extend(structs[start_idx: end_idx + 1])
            return
            
        if start_idx == end_idx:
            # collect in the first block
            if child_name in structs[start_idx]:
                self._get_obj_from_range(structs[start_idx][child_name], start[1:], end[1:], collections)
            return

        if child_name in structs[start_idx]:
            self._get_obj_from_range(structs[start_idx][child_name], start[1:], [-1]*remain_level, collections)
        # collect in the middle blocks
        for blk in range(start_idx + 1, end_idx):
            collections.append(structs[blk])
            
        if child_name in structs[end_idx]:
            self._get_obj_from_range(structs[end_idx][child_name], [0] * remain_level, end[1:], collections)
    
    def parse_obj_list(self, obj_list):
        """
        obj_list is a list of objects in the page rawdict.
        """
        chars = []
        def _parse_line(line):
            res = []
            for span in line["spans"]:
                if "chars" in span:
                    res.extend([x["c"] for x in span["chars"]])
            return res
        
        def _parse_block(block):
            res = []
            for line in block["lines"]:
                res.extend(_parse_line(line))
            return res
                    
        for obj in obj_list:
            if "c" in obj:
                chars.append(obj["c"])
            elif "chars" in obj:
                chars.extend([x["c"] for x in obj["chars"]])
            elif "spans" in obj:
                chars.extend(_parse_line(obj))
            elif "lines" in obj:
                chars.extend(_parse_block(obj))
                
        return "".join(chars)
        

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

        if invert:
            # make background transparent
            sample_color = pixmap.pixel(0,0)
            if sample_color[3] == 255:
                pixmap = self.make_background_transparent(pixmap, sample_color[:3])
            elif sample_color[3] == 0:
                pixmap = self.make_background_transparent(pixmap, (255,255,255))

            pixmap_invert_irect(pixmap)(pixmap.irect)

        if not invert_image and invert:
            pixmap = self.with_invert_exclude_image(scale, pixmap)

        img = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGBA8888)
        qpixmap = QPixmap.fromImage(img)

        if self.get_annots():
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

    def can_update_annot(self, ex, ey):
        if not self.get_annots():
            return None, False

        for annot in self.get_annots():
            x0, y0, x1, y1 = annot.rect
            if ex >= x0 and ex <= x1 and ey >= y0 and ey <= y1:
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
            
    def mark_search_text(self, keyword, current_quad):
        if not self.is_pdf:
            # add_highlight_annot is only for pdf
            return []
        
        if support_hit_max:
            quads_list = self.page.searchFor(keyword, hit_max=999, quads=True)
        else:
            quads_list = self.page.search_for(keyword, quads=True)

        if quads_list:
            for quad in quads_list:
                annot = self.page.add_highlight_annot(quad)
                annot.parent = self.page
                if quad == current_quad:
                    qcolor = QColor("#f28100")
                    annot.set_colors(stroke=qcolor.getRgbF()[0:3])
                    annot.update()
                self._mark_search_annot_list.append(annot)
            return self._mark_search_annot_list
        return []

    def cleanup_search_text(self, old_annots):
        annots = set(self._mark_search_annot_list) | set(old_annots)
        for annot in annots:
            self.page.delete_annot(annot)
        self._mark_search_annot_list.clear()

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

    def get_links(self):
        if self._links is None:
            self._links = self.page.get_links()
        return self._links
    
    def get_annots(self):
        if self._annots is None:
            self._annots = list(self.page.annots())
        return self._annots
    
    def _is_intersects(self, rect1, rect2):
        x0, y0, x1, y1 = rect1
        xx0, yy0, xx1, yy1 = rect2

        # Check if there is NO overlap in the x-dimension
        if x1 <= xx0 or x0 >= xx1:
            return False

        # Check if there is NO overlap in the y-dimension
        if y1 <= yy0 or y0 >= yy1:
            return False

        # If there is overlap in both x and y dimensions, then the rectangles intersect
        return True