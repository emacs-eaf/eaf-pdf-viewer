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


from PyQt6.QtCore import Qt, QRect, QRectF, QPoint, QEvent, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor
from PyQt6.QtGui import QPainter, QPalette
from PyQt6.QtWidgets import QWidget
from core.utils import (interactive, eval_in_emacs, message_to_emacs,
                        atomic_edit, get_emacs_var, get_emacs_vars,
                        get_emacs_func_result, get_emacs_config_dir,
                        get_emacs_theme_mode, get_emacs_theme_foreground,
                        get_emacs_theme_background, get_app_dark_mode)
import fitz
import time
import math

from eaf_pdf_document import PdfDocument
from eaf_pdf_utils import inverted_color, support_hit_max
from eaf_pdf_annot import AnnotAction

def set_page_crop_box(page):
    if hasattr(page, "set_cropbox"):
        return page.set_cropbox
    else:
        return page.setCropBox

class PdfViewerWidget(QWidget):

    translate_double_click_word = pyqtSignal(str)

    def __init__(self, url, background_color, buffer_id, synctex_info):
        super(PdfViewerWidget, self).__init__()

        self.url = url
        self.config_dir = get_emacs_config_dir()
        self.background_color = background_color
        self.buffer_id = buffer_id
        self.user_name = get_emacs_var("user-full-name")

        self.is_button_press = False

        self.synctex_info = synctex_info

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
        self.select_area_annot_quad_cache_dict = {}

        # text annot
        self.is_hover_annot = False
        self.hovered_annot = None
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
        # pal.setColor(QPalette.Background, self.background_color)
        pal.setColor(QPalette.ColorRole.Window, self.background_color)
        self.setAutoFillBackground(True)
        self.setPalette(pal)

        # Init font.
        self.page_annotate_padding_right = 10
        self.page_annotate_padding_bottom = 10

        self.font = QFont()
        self.font.setPointSize(24)

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
        self.inverted_mode = get_app_dark_mode("eaf-pdf-dark-mode")

        # Inverted mode exclude image. (current exclude image inner implement use PDF Only method)
        self.inverted_image_mode = not self.pdf_dark_exclude_image and self.document.isPDF

        # synctex init page
        if self.synctex_info.page_num != None:
            self.jump_to_page(self.synctex_info.page_num)

    def load_document(self, url):
        if self.page_cache_pixmap_dict:
            self.page_cache_pixmap_dict.clear()

        # Load document first.
        try:
            self.document = PdfDocument(fitz.open(url))
        except Exception:
            message_to_emacs("Failed to load PDF file!")
            return

        # recompute width, height, total number since the file might be modified
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        painter.save()

        # Draw background.
        # change color of background if inverted mode is enable
        if self.pdf_dark_mode == "follow" or self.pdf_dark_mode == "force":
            color = QColor(self.theme_background_color)
            painter.setBrush(color)
            painter.setPen(color)
        else:
            color = QColor(20, 20, 20, 255) if self.inverted_mode else Qt.GlobalColor.white
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

            if self.is_select_mode:
                qpixmap = self.mark_select_char_area(index, qpixmap)

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

            rect = QRect(int(render_x), int(render_y), int(render_width), int(render_height))

            # draw rectangle with current pen and brush color
            painter.drawRect(rect)

            painter.drawPixmap(rect, qpixmap)

            # Draw an indicator for synctex position
            if self.synctex_info.page_num == index + 1 and self.synctex_info.pos_y != None:
                indicator_pos_y = int(self.synctex_info.pos_y * self.scale)
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
        from PyQt6.QtGui import QPolygon

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
        QTimer().singleShot(5000, self.synctex_info.reset)
        painter.restore()

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
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
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
            QTimer().singleShot(self_obj.page_cache_context_delay, self_obj.build_context_cache)

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
        message_to_emacs("Reloaded PDF file!")
        self.load_document(self.url)

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
            new_annot = page.add_Freetext_Annot(annot_action.annot_rect,
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
            page.delete_annot(annot)
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

            from core.utils import open_url_in_new_tab
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
            if support_hit_max:
                quads_list = self.document.search_page_for(page_index, text, hit_max=999, quads=True)
            else:
                quads_list = self.document.search_page_for(page_index, text, quads=True)

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
        new_annot = page.add_Freetext_Annot(annot_rect, text,
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

    def update_select_char_area(self):
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

            quad_list = list(map(lambda x: x.quad, line_rect_list))

            # refresh select quad
            self.select_area_annot_quad_cache_dict[page_index] = quad_list

    def mark_select_char_area(self, page_index, pixmap):
        def quad_to_qrect(quad):
            qrect = quad.rect * self.scale * self.devicePixelRatioF()
            rect = QRect(int(qrect.x0), int(qrect.y0), int(qrect.width), int(qrect.height))
            return rect

        qp = QPainter(pixmap)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        qp.save()

        # clear old highlight
        if page_index in self.select_area_annot_quad_cache_dict:
            old_quads = self.select_area_annot_quad_cache_dict[page_index]
            for quad in old_quads:
                qp.fillRect(quad_to_qrect(quad), qp.background())

        # update select area quad list
        self.update_select_char_area()

        # draw new highlight
        if page_index in self.select_area_annot_quad_cache_dict:
            quads = self.select_area_annot_quad_cache_dict[page_index]
            for quad in quads:
                qp.fillRect(quad_to_qrect(quad), QColor(self.text_highlight_annot_color))

        qp.restore()
        return pixmap

    def delete_all_mark_select_area(self):
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

    def check_annot(self):
        ex, ey, page_index = self.get_cursor_absolute_position()
        page = self.document[page_index]

        annot, ok = page.can_update_annot(ex, ey)
        if not ok:
            return

        self.is_hover_annot = annot is not None

        self.hovered_annot = annot
        self.page_cache_pixmap_dict.pop(page_index, None)
        self.update()

    def save_annot(self):
        self.document.saveIncr()
        self.page_cache_pixmap_dict.clear()
        self.update()

    def annot_handler(self, action=None):
        if self.hovered_annot is None:
            return
        annot = self.hovered_annot
        if annot.parent:
            if action == "delete":
                annot_action = AnnotAction.create_annot_action("Delete", annot.parent.number, annot)
                self.record_new_annot_action(annot_action)
                annot.parent.delete_annot(annot)
                self.save_annot()
            elif action == "edit":
                self.edited_annot_page = (annot, annot.parent)
                if annot.type[0] == fitz.PDF_ANNOT_TEXT or \
                   annot.type[0] == fitz.PDF_ANNOT_FREE_TEXT:
                    atomic_edit(self.buffer_id, annot.info["content"].replace("\r", "\n"))
            elif action == "move":
                self.moved_annot_page = (annot, annot.parent)
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

    def delete_pdf_page (self, page):
        self.document.delete_page(page)
        self.save_annot()

    def delete_pdf_pages (self, start_page, end_page):
        self.document.delete_pages(start_page, end_page)
        self.save_annot()

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
        for link in page.get_links():
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

        set_page_crop_box(page)(page.rect)
        page_words = page.getTextWords()
        rect_words = [w for w in page_words if fitz.Rect(w[:4]).intersects(draw_rect)]
        if rect_words:
            return rect_words[0][4]

    def eventFilter(self, obj, event):
        if event.type() in [QEvent.Type.MouseButtonPress]:
            self.is_button_press = True
        elif event.type() in [QEvent.Type.MouseButtonRelease]:
            self.is_button_press = False

        if event.type() in [QEvent.Type.MouseMove, QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseButtonPress]:
            if not self.document.isPDF:
                # workaround for epub click link
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
                    self.handle_click_link()
                return False

        if event.type() == QEvent.Type.MouseMove:
            if self.hasMouseTracking():
                self.check_annot()
            else:
                self.handle_select_mode()

        elif event.type() == QEvent.Type.MouseButtonPress:
            # add this detect release mouse event
            self.grabMouse()

            # cleanup select mode on another click
            if self.is_select_mode:
                self.cleanup_select()

            if self.is_popup_text_annot_mode:
                if event.button() != Qt.MouseButton.LeftButton:
                    self.disable_popup_text_annot_mode()
            elif self.is_inline_text_annot_mode:
                if event.button() != Qt.MouseButton.LeftButton:
                    self.disable_inline_text_annot_mode()
            elif self.is_move_text_annot_mode:
                if event.button() != Qt.MouseButton.LeftButton:
                    self.disable_move_text_annot_mode()
            else:
                if event.button() == Qt.MouseButton.LeftButton:
                    # In order to catch mouse move event when drap mouse.
                    self.setMouseTracking(False)
                elif event.button() == Qt.MouseButton.RightButton:
                    self.handle_click_link()

        elif event.type() == QEvent.Type.MouseButtonRelease:
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

            import platform
            if platform.system() == "Darwin":
                eval_in_emacs('eaf-activate-emacs-window', [])

        elif event.type() == QEvent.Type.MouseButtonDblClick:
            self.disable_popup_text_annot_mode()
            self.disable_inline_text_annot_mode()
            if event.button() == Qt.MouseButton.RightButton:
                self.handle_translate_word()
            elif event.button() == Qt.MouseButton.LeftButton:
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
                self.update()

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
