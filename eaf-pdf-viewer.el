;;; eaf-pdf-viewer.el --- PDF Viewer -*- lexical-binding: t; -*-

;; Filename: eaf-pdf-viewer.el
;; Description: PDF Viewer
;; Author: Andy Stewart <lazycat.manatee@gmail.com>
;; Maintainer: Andy Stewart <lazycat.manatee@gmail.com>
;; Copyright (C) 2021, Andy Stewart, all rights reserved.
;; Created: 2021-07-20 22:16:40
;; Version: 0.1
;; Last-Updated: Fri Jul 30 00:48:38 2021 (-0400)
;;           By: Mingde (Matthew) Zeng
;; URL: http://www.emacswiki.org/emacs/download/eaf-pdf-viewer.el
;; Keywords:
;; Compatibility: GNU Emacs 28.0.50
;;
;; Features that might be required by this library:
;;
;;
;;

;;; This file is NOT part of GNU Emacs

;;; License
;;
;; This program is free software; you can redistribute it and/or modify
;; it under the terms of the GNU General Public License as published by
;; the Free Software Foundation; either version 3, or (at your option)
;; any later version.

;; This program is distributed in the hope that it will be useful,
;; but WITHOUT ANY WARRANTY; without even the implied warranty of
;; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
;; GNU General Public License for more details.

;; You should have received a copy of the GNU General Public License
;; along with this program; see the file COPYING.  If not, write to
;; the Free Software Foundation, Inc., 51 Franklin Street, Fifth
;; Floor, Boston, MA 02110-1301, USA.

;;; Commentary:
;;
;; PDF Viewer
;;

;;; Installation:
;;
;; Put eaf-pdf-viewer.el to your load-path.
;; The load-path is usually ~/elisp/.
;; It's set in your ~/.emacs like this:
;; (add-to-list 'load-path (expand-file-name "~/elisp"))
;;
;; And the following to your ~/.emacs startup file.
;;
;; (require 'eaf-pdf-viewer)
;;
;; No need more.

;;; Customize:

(defgroup eaf-pdf-viewer nil
  "The PDF viewer application of Emacs application framework."
  :group 'eaf)

(defcustom eaf-pdf-extension-list
  '("pdf" "xps" "oxps" "cbz" "epub" "fb2" "fbz")
  "The extension list of pdf application."
  :type 'list
  :group 'eaf-pdf-viewer)

(defcustom eaf-office-extension-list
  '("docx" "doc" "ppt" "pptx" "xlsx" "xls")
  "The extension list of office application."
  :type 'list
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-store-history t
  "If it is t, the pdf file path will be stored in eaf-config-location/pdf/history/log.txt for eaf-open-pdf-from-history to use"
  :type 'boolean
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-notify-file-changed t
  "If it is t, pdf-viewer will notify that the displayed pdf file is changed. Otherwise the pdf-viewer buffer will be refreshed silently."
  :type 'boolean
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-show-progress-on-page t
  "If it is t, pdf-viewer will show progress (in percentage) and page number directly on the document."
  :type 'boolean
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-dark-mode "ignore"
  "Whether to enable inverted color rendering when starting the pdf-viewer app.

Possible values are
   - \"follow\" Follow the background color of the theme of user.
   - \"force\" Force inverted color rendering on start-up.
   - \"ignore\" Don't do inverted rendering."
  :type '(choice (string :tag "Force inverted color rendering." "force")
                 (string :tag "Follow the background color of user's theme." "follow")
                 (other :tag "Do normal rendering." "ignore"))
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-default-zoom 1.0
  "The default zooming percentage when starting the pdf-viewer app."
  :type 'float
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-zoom-step 0.2
  "The ratio step of the current page size to perform zoom in, zoom out."
  :type 'float
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-scroll-ratio 0.05
  "The ratio of the page in each step when scrolling."
  :type 'float
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-dark-exclude-image t
  "Don't invert images when toggling inverted color rendering.

Nil means also invert images.
Non-nil means don't invert images."
  :type 'boolean
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-marker-fontsize 8
  "The font size used by pdf marker."
  :type 'integer
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-inline-text-annot-fontsize 8
  "The font size used by pdf inline text annot."
  :type 'integer
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-inline-text-annot-color "#ec3f00"
  "The color used by pdf inline text annot."
  :type 'string
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-text-highlight-annot-color "#ffd815"
  "The color used by pdf text highlighting annot."
  :type 'string
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-text-underline-annot-color "#11e32a"
  "The color used by pdf text underlining annot."
  :type 'string
  :group 'eaf-pdf-viewer)

(defcustom eaf-pdf-viewer-keybinding
  '(("j" . "scroll_up")
    ("<down>" . "scroll_up")
    ("C-n" . "scroll_up")
    ("k" . "scroll_down")
    ("<up>" . "scroll_down")
    ("C-p" . "scroll_down")
    ("h" . "scroll_left")
    ("<left>" . "scroll_left")
    ("C-b" . "scroll_left")
    ("l" . "scroll_right")
    ("<right>" . "scroll_right")
    ("C-f" . "scroll_right")
    ("SPC" . "scroll_up_page")
    ("b" . "scroll_down_page")
    ("C-v" . "scroll_up_page")
    ("M-v" . "scroll_down_page")
    ("c" . "scroll_center_horizontal")
    ("t" . "toggle_read_mode")
    ("0" . "zoom_reset")
    ("=" . "zoom_in")
    ("-" . "zoom_out")
    ("w" . "zoom_fit_text_width")
    ("W" . "zoom_close_to_text_width")
    ("g" . "scroll_to_begin")
    ("G" . "scroll_to_end")
    ("p" . "jump_to_page")
    ("P" . "jump_to_percent")
    ("[" . "save_current_pos")
    ("]" . "jump_to_saved_pos")
    ("i" . "toggle_inverted_mode")
    ("C-i" . "toggle_inverted_image_mode")
    ("m" . "toggle_mark_link")
    ("f" . "jump_to_link")
    ("M-w" . "copy_select")
    ("C-s" . "search_text_forward")
    ("C-r" . "search_text_backward")
    ("C-/" . "undo_annot_action")
    ("C-?" . "redo_annot_action")
    ("x" . "close_buffer")
    ("z" . "eaf-ocr-buffer")
    ("r" . "reload_document")
    ("C-<right>" . "rotate_clockwise")
    ("C-<left>" . "rotate_counterclockwise")
    ("M-h" . "add_annot_highlight")
    ("M-u" . "add_annot_underline")
    ("M-s" . "add_annot_squiggly")
    ("M-d" . "add_annot_strikeout_or_delete_annot")
    ("M-t" . "add_annot_popup_text")
    ("M-T" . "add_annot_inline_text")
    ("M-e" . "edit_annot_text")
    ("M-r" . "move_annot_text")
    ("M-p" . "toggle_presentation_mode")
    ("<escape>" . "quit_presentation_mode")
    ("J" . "select_left_tab")
    ("K" . "select_right_tab")
    ("o" . "eaf-pdf-outline")
    ("O" . "eaf-pdf-outline-edit")
    ("T" . "toggle_trim_white_margin"))
  "The keybinding of EAF PDF Viewer."
  :type '(alist :key-type (string :tag "Key bindings (e.g. \"C-n\", \"<f4>\", etc.)")
                :value-type (string :tag "Function name"))
  :group 'eaf-pdf-viewer)

;;
;; All of the above can customize by:
;;      M-x customize-group RET eaf-pdf-viewer RET
;;

;;; Change log:
;;
;; 2021/07/20
;;      * First released.
;; 2021/08/16
;;      * More elaborate defcustoms
;;      * Divide code via outline-mode
;;

;;; Acknowledgements:
;;
;;
;;

;;; TODO
;;
;;
;;

;;; Require
(require 'outline)

;;; Code:
;;;; Outline buffer & Imenu

(defcustom eaf-pdf-outline-buffer-indent 4
  "The level of indent in the Outline buffer."
  :type 'integer
  :group 'eaf-pdf-viewer)

(defvar-local eaf-pdf-outline-pdf-document nil
  "The PDF filename or buffer corresponding to this outline
  buffer.")

(defvar-local eaf-pdf--outline-window-configuration nil
  "Save window configure before popup outline buffer.")

(defvar eaf-pdf-outline-mode-map
  (let ((map (make-sparse-keymap)))
    (dotimes (i 10)
      (define-key map (vector (+ i ?0)) 'digit-argument))
    (define-key map "-" 'negative-argument)
    ;; Navigation
    (define-key map (kbd "p") 'previous-line)
    (define-key map (kbd "P") 'eaf-pdf-outline-view-prev)
    (define-key map (kbd "n") 'next-line)
    (define-key map (kbd "N") 'eaf-pdf-outline-view-next)
    (define-key map (kbd "SPC") 'eaf-pdf-outline-view-next)
    (define-key map (kbd "RET") 'eaf-pdf-outline-jump)
    (define-key map (kbd "o") 'eaf-pdf-outline-view)
    (define-key map (kbd "v") 'eaf-pdf-outline-view)

    ;; Outline-mode stuffs
    (define-key map (kbd "b") 'outline-backward-same-level)
    (define-key map (kbd "d") 'outline-hide-subtree)
    (define-key map (kbd "a") 'outline-show-all)
    (define-key map (kbd "s") 'outline-show-subtree)
    (define-key map (kbd "f") 'outline-forward-same-level)
    (define-key map (kbd "Q") 'outline-hide-sublevels)
    (define-key map (kbd "RET") 'eaf-pdf-outline-jump)
    (define-key map (kbd "Q") 'hide-sublevels)
    map)
  "Keymap used in `eaf-pdf-outline-mode'.")

(defvar eaf-pdf-outline-edit-mode-map
  (let ((map (make-sparse-keymap)))
    (define-key map [remap org-insert-heading-respect-content] #'eaf-pdf-outline-edit-jump)
    (define-key map [remap org-ctrl-c-ctrl-c] #'eaf-pdf-outline-edit-buffer-confirm)
    (define-key map [remap org-kill-note-or-show-branches] #'kill-buffer-and-window)
    map)
  "Keymap used in `eaf-pdf-outline-edit-mode'.")

(define-derived-mode eaf-pdf-outline-mode outline-mode "PDF Outline"
  "EAF pdf outline mode."
  (setq-local outline-regexp "\\( *\\).")
  (setq-local outline-level
              #'(lambda nil (1+ (/ (length (match-string 1))
                               eaf-pdf-outline-buffer-indent))))
  (toggle-truncate-lines 1)
  (setq buffer-read-only t))

(define-derived-mode eaf-pdf-outline-edit-mode org-mode "PDF Outline Editing"
  "EAF pdf outline edit mode."
  (toggle-truncate-lines 1))

(defun eaf-pdf-outline-buffer-name (&optional pdf-buffer)
  (unless pdf-buffer (setq pdf-buffer (current-buffer)))
  (format "*Outline: %s*"
          (if (bufferp pdf-buffer)
              (buffer-name pdf-buffer)
            pdf-buffer)))

(defun eaf-pdf-outline-edit-buffer-name (&optional pdf-buffer)
  (interactive)
  (unless pdf-buffer (setq pdf-buffer (if (local-variable-p 'eaf-pdf-outline-pdf-document) eaf-pdf-outline-pdf-document (current-buffer))))
  (format "*Outline Edit: %s*"
          (if (bufferp pdf-buffer)
              (buffer-name pdf-buffer)
            pdf-buffer)))

(defun eaf-pdf-outline ()
  "Display an PDF outline of the current buffer."
  (interactive)
  (let ((pdf-buffer (current-buffer))
        (toc (eaf-call-sync "execute_function" eaf--buffer-id "get_toc"))
        (page-number (string-to-number (eaf-call-sync "execute_function" eaf--buffer-id "current_page")))
        (outline-buf (get-buffer-create (eaf-pdf-outline-buffer-name))))
    ;; Save window configuration before outline.
    (setq eaf-pdf--outline-window-configuration (current-window-configuration))

    ;; Insert outline content.
    (with-current-buffer outline-buf
      (setq buffer-read-only nil)
      (erase-buffer)
      (insert toc)
      (setq toc (mapcar #'(lambda (line)
                            (string-to-number (car (last (split-string line " ")))))
                        (butlast (split-string (buffer-string) "\n"))))
      (goto-line (seq-count (apply-partially #'>= page-number) toc))
      (let ((view-read-only nil))
        (read-only-mode 1))
      (eaf-pdf-outline-mode)
      (setq-local eaf-pdf-outline-pdf-document pdf-buffer))

    ;; Popup outline buffer.
    (pop-to-buffer outline-buf)))

(defun eaf-pdf-outline-edit ()
  (interactive)
  (let* ((pdf-buffer (if (local-variable-p 'eaf-pdf-outline-pdf-document) eaf-pdf-outline-pdf-document (current-buffer)))
         (buffer-id (buffer-local-value 'eaf--buffer-id (get-buffer pdf-buffer)))
         (toc (eaf-call-sync "execute_function" buffer-id "get_toc_to_edit"))
         (page-number (string-to-number (or (eaf-call-sync "execute_function" eaf--buffer-id "current_page") "1")))
         (outline-edit-buffer (generate-new-buffer (eaf-pdf-outline-edit-buffer-name))))

    (with-current-buffer outline-edit-buffer
      (setq buffer-read-only nil)
      (erase-buffer)
      (insert toc)
      (setq toc (mapcar #'(lambda (line)
                            (string-to-number (car (last (split-string line " ")))))
                        (butlast (split-string (buffer-string) "\n"))))
      (goto-line (seq-count (apply-partially #'>= page-number) toc))
      (eaf-pdf-outline-edit-mode)
      (set (make-local-variable 'eaf--buffer-id) buffer-id)
      )

    (pop-to-buffer outline-edit-buffer)))

(defun eaf-pdf-outline-jump ()
  "Jump into specific page."
  (interactive)
  (let* ((line (thing-at-point 'line))
         (page-num (substring-no-properties (replace-regexp-in-string "\n" "" (car (last (split-string line " ")))))))
    ;; Jump to page.
    (switch-to-buffer-other-window eaf-pdf-outline-pdf-document)
    (eaf-call-sync "execute_function_with_args" eaf--buffer-id "jump_to_page_with_num" (format "%s" page-num))

    ;; Restore window configuration before outline operation.
    (when eaf-pdf--outline-window-configuration
      (set-window-configuration eaf-pdf--outline-window-configuration)
      (setq eaf-pdf--outline-window-configuration nil))))

(defun eaf-pdf-outline-edit-jump ()
  "Jump into specific page."
  (interactive)
  (let* ((raw-value (org-element-property :raw-value (org-element-at-point)))
         (page-num (and (string-match (rx (1+ num) string-end) raw-value) (match-string 0 raw-value)))
         )
    (if page-num
        (eaf-call-sync "execute_function_with_args" eaf--buffer-id "jump_to_page_with_num" (format "%s" page-num))
      (error "Has no corresponding page number!"))))

(defun eaf-pdf-outline-view ()
  "View the specific page."
  (interactive)
  (let* ((line (thing-at-point 'line))
         (page-num (substring-no-properties (replace-regexp-in-string "\n" "" (car (last (s-split " " line)))))))
    ;; Jump to page.
    (eaf-call-async "execute_function_with_args"
                    (buffer-local-value 'eaf--buffer-id eaf-pdf-outline-pdf-document)
                    "jump_to_page_with_num" (format "%s" page-num))))

(defun eaf-pdf-outline-view-prev ()
  "View the specific page in the previous line."
  (interactive)
  (previous-line)
  (eaf-pdf-outline-view))

(defun eaf-pdf-outline-view-next ()
  "View the specific page in the next line."
  (interactive)
  (next-line)
  (eaf-pdf-outline-view))

(defun eaf-pdf-imenu-create-index-from-toc ()
  "Create an alist based on the table of contents of this buffer.

It call the Python's function \"get_toc\" then from the output, make an alist
with each element that looks like
(\"CHAPTER_NAME\" PAGE_NUMBER 'eaf-pdf-imenu-go-to-index nil).

(See why the element has to be that way in `imenu--index-alist'
 Hint: Look for \"Special elements\" in the documentation.)

the \"CHAPTER_NAME\" part will be replace with \"Page PAGE_NUMBER\"
when there is no table of contents for the buffer."
  (interactive)
  (or imenu--index-alist
      (setq imenu--index-alist
            (let ((toc (eaf-call-sync "execute_function" eaf--buffer-id "get_toc")))
              (cond ((string= toc "")
                     (mapcar #'(lambda (page-num)
                                 (list (concat "Page " (number-to-string page-num)) page-num
                                       #'eaf-pdf-imenu-go-to-index
                                       nil))
                             (number-sequence 1
                                              (string-to-number
                                               (eaf-call-sync "execute_function"
                                                              eaf--buffer-id
                                                              "page_total_number")))))
                    (t
                     (mapcar #'(lambda (line)
                                 (let ((line-split (split-string line " ")))
                                   (list (string-join (butlast line-split) " ")
                                         (string-to-number (car (last line-split)))
                                         #'eaf-pdf-imenu-go-to-index
                                         nil)))
                             (split-string toc "\n"))))))))

(defun eaf-pdf-imenu-go-to-index (_chapter-name page-num _arg)
  "Ignore _CHAPTER-NAME and _ARG, call Python's \"jump_page\" function with PAGE-NUM as its argument.

The _CHAPTER-NAME is from the car of a element in `eaf-pdf-imenu-create-index-from-toc'
The _ARG is hardcoded to be nil from `eaf-pdf-imenu-create-index-from-toc'
Just ignore them and call \"jump_page\" to PAGE-NUM."
  (eaf-call-async "handle_input_response" eaf--buffer-id "jump_page" page-num))

(defun eaf-pdf-imenu-setup ()
  (setq imenu-create-index-function 'eaf-pdf-imenu-create-index-from-toc))

(add-hook 'eaf-pdf-viewer-hook 'eaf-pdf-imenu-setup)

;;;; PDF-viewer
(defun eaf-pdf-get-page-annots (page)
  "Return a map of annotations on PAGE.

The key is the annot id on PAGE."
  (eaf-call-sync "execute_function_with_args" eaf--buffer-id "get_page_annots" (format "%s" page)))

(defun eaf-pdf-get-document-annots ()
  "Return a map of page_index of annots.

The key is the page_index."
  (eaf-call-sync "execute_function" eaf--buffer-id "get_document_annots"))

(defun eaf-pdf-jump-to-annot (annot)
  "Jump to specifical pdf annot."
  (let ((rect (gethash "rect" annot))
        (page (gethash "page" annot)))
    (eaf-call-sync "execute_function_with_args" eaf--buffer-id "jump_to_rect" (format "%s" page) rect)))

(defun eaf--pdf-viewer-bookmark ()
  "Restore EAF buffer according to pdf bookmark from the current file path or web URL."
  `((handler . eaf--bookmark-restore)
    (eaf-app . "pdf-viewer")
    (defaults . ,(list eaf--bookmark-title))
    (filename . ,(eaf-get-path-or-url))))

(defun eaf--pdf-viewer-bookmark-restore (bookmark)
  (eaf-open (cdr (assq 'filename bookmark))))

(defun eaf--pdf-update-position (buffer-id page-index page-total-number)
  "Format mode line position indicator to show the current page and the total pages."
  (let ((buffer (eaf-get-buffer buffer-id))
        (page-index (number-to-string page-index))
        (page-total-number (number-to-string page-total-number)))
    (when buffer
      (with-current-buffer buffer
        (let ((need-update
               (condition-case ex
                   (or (not (equal (cadr mode-line-position) page-index))
                       (not (equal (cadddr mode-line-position) page-total-number)))
                 ('error t))))
          (when need-update
            (setq-local mode-line-position `(" P" ,page-index
                                             "/" ,page-total-number))
            (force-mode-line-update)))))))

(defun eaf-open-pdf-from-history ()
  "A wrapper around `eaf-open' that provides pdf history candidates.
This function works best if paired with a fuzzy search package."
  (interactive)
  (let* ((pdf-history-file-path
          (concat eaf-config-location
                  (file-name-as-directory "pdf")
                  (file-name-as-directory "history")
                  "log.txt"))
         (history-pattern "^\\(.+\\)\\.pdf$")
         (history-file-exists (file-exists-p pdf-history-file-path))
         (eaf-files-opened (mapcar (lambda (buf)
                                     (buffer-local-value 'eaf--buffer-url buf))
                                   (eaf--get-eaf-buffers)))
         (history-pdf (completing-read
                       "[EAF/pdf] Search || History: "
                       (cl-remove-if (lambda (x)
                                       (or (null x)
                                           (member x eaf-files-opened)))
                                     (if history-file-exists
                                         (mapcar
                                          (lambda (h) (when (string-match history-pattern h)
                                                        (if (file-exists-p h)
                                                            (format "%s" h))))
                                          (with-temp-buffer (insert-file-contents pdf-history-file-path)
                                                            (split-string (buffer-string) "\n" t)))
                                       (make-directory (file-name-directory pdf-history-file-path) t)
                                       (with-temp-file pdf-history-file-path ""))))))
    (if history-pdf (eaf-open history-pdf))))

(defun eaf-pdf-delete-invalid-file-record-from-history ()
  " delete invalid file record from eaf pdf history file"
  (interactive)
  (let* ((pdf-history-file-path
          (concat eaf-config-location
                  (file-name-as-directory "pdf")
                  (file-name-as-directory "history")
                  "log.txt"))
         (history-pattern "^\\(.+\\)\\.pdf$")
         (history-file-exists (file-exists-p pdf-history-file-path))
         file-content)
    (when history-file-exists
      (setq file-content (with-temp-buffer
                           (insert-file-contents pdf-history-file-path)
                           (buffer-string)))
      (dolist (each-file (split-string file-content "\n" t))
        (unless (file-exists-p each-file)
          (setq file-content (replace-regexp-in-string (rx--to-expr (format "%s\n"  each-file)) "" file-content))
          (message "delete %s record from history" each-file)))
      (with-temp-file pdf-history-file-path
        (insert file-content))
      )))

(defun eaf-pdf-delete-pages (page-num)
  " Delete pdf pages
1 => delete page 1
1 3 => delete page 1 2 3
"
  (interactive "s delete pages : ")
  (let* ( confirmp start-page end-page (tmp-pages (s-split " " page-num)))
    (setq start-page (car tmp-pages))
    (if (> (length tmp-pages) 1)
        (progn
          (setq end-page (car (cdr tmp-pages)))
          (setq confirmp (yes-or-no-p (format "confirm delete page %s to %s" start-page end-page))))
      (setq confirmp (yes-or-no-p (format "confirm delete page %s" start-page))))
    (if confirmp
        (eaf-call-sync "execute_function_with_args" eaf--buffer-id "delete_pdf_pages" (format "%s" page-num))
      (message "give up delete page"))))

;;;###autoload
(defun eaf-open-office (file)
  "View Microsoft Office FILE as READ-ONLY PDF."
  (interactive "f[EAF/office] Open Office file as PDF: ")
  (if (executable-find "libreoffice")
      (let* ((file-md5 (eaf-get-file-md5 file))
             (basename (file-name-base file))
             (pdf-file (format "/tmp/%s.pdf" file-md5))
             (pdf-argument (format "%s.%s_office_pdf" basename (file-name-extension file))))
        (if (file-exists-p pdf-file)
            (eaf-open pdf-file "pdf-viewer" pdf-argument)
          (message "Converting %s to PDF, EAF will start shortly..." file)
          (make-process
           :name ""
           :buffer " *eaf-open-office*"
           :command (list "libreoffice" "--headless" "--convert-to" "pdf" (file-truename file) "--outdir" "/tmp")
           :sentinel (lambda (_ event)
                       (when (string= (substring event 0 -1) "finished")
                         (rename-file (format "/tmp/%s.pdf" basename) pdf-file)
                         (eaf-open pdf-file "pdf-viewer" pdf-argument)
                         )))))
    (error "[EAF/office] libreoffice is required convert Office file to PDF!")))

(defun eaf-get-file-md5 (file)
  "Get the MD5 value of a specified FILE."
  (car (split-string (shell-command-to-string (format "md5sum '%s'" (file-truename file))) " ")))

;;;; Synctex support

(defvar eaf-pdf-synctex-path "synctex"
  "Path of synctex tool.")

(defvar eaf-pdf-synctex-file-directory-function 'eaf-pdf--get-synctex-file-directory
  "Function to get the *.synctex.gz file directory, look `eaf-pdf--get-synctex-file-directory'")

(defun eaf-pdf--get-synctex-file-directory (pdf-file)
  "Get *.synctex.gz file directory through `pdf-file'"
  (file-name-directory (directory-file-name pdf-file)))

(defun eaf-pdf--find-buffer (pdf-url)
  "Find opened buffer by `pdf-url'"
  (let ((opened-buffer))
    (catch 'found-match-buffer
      (dolist (buffer (buffer-list))
        (set-buffer buffer)
        (when (equal major-mode 'eaf-mode)
          (when (and (string= eaf--buffer-url pdf-url)
                     (string= eaf--buffer-app-name "pdf-viewer"))
            (setq opened-buffer buffer)
            (throw 'found-match-buffer t)))))
    opened-buffer))

(defun eaf-pdf--get-synctex-info (tex-file line-num pdf-file)
  "Use synctex tool to get the page num of `pdf-file' through `tex-file' and `line-num'."
  (if (executable-find eaf-pdf-synctex-path)
      (let ((synctex-result)
            (page-num 1) (pos-x 0) (pos-y 0)
            (synctex-view-command (format "%s view -i %s:1:%s -o %s"
                                          eaf-pdf-synctex-path line-num
                                          (prin1-to-string tex-file)
                                          (prin1-to-string pdf-file))))
        (setq synctex-result (shell-command-to-string synctex-view-command))
        ;; (message "Synctex Result: %s" synctex-result)
        (when synctex-result
          (and (string-match "Page:\\([0-9]+\\)\n" synctex-result)
               (setq page-num  (string-to-number (match-string 1 synctex-result))))
          (and (string-match "x:\\([0-9\\.]+\\)\n" synctex-result)
               (setq pos-x  (string-to-number (match-string 1 synctex-result))))
          (and (string-match "y:\\([0-9\\.]+\\)\n" synctex-result)
               (setq pos-y  (string-to-number (match-string 1 synctex-result)))))
        (format "%d:%f:%f" page-num pos-x pos-y))
    (message "Can not found %s" eaf-pdf-synctex-path)))

(defun eaf-pdf--get-tex-and-line (pdf-file page-num x y)
  "Use synctex tool to get tex file and line num through `page-file', `page-num', `x' and `y'."
  (if (executable-find eaf-pdf-synctex-path)
      (let* ((synctex-result)
             (synctex-dir (funcall eaf-pdf-synctex-file-directory-function pdf-file))
             (synctex-edit-command (format "%s edit -o %s:%s:%s:%s -d %s"
                                           eaf-pdf-synctex-path page-num x y
                                           (prin1-to-string pdf-file)
                                           (prin1-to-string synctex-dir)))
             (tex-file nil)
             (line-num nil))
        (setq synctex-result (shell-command-to-string synctex-edit-command))
        (if (and synctex-result (string-match "Input:\\(.*\\)\nLine:\\([0-9]+\\)\n" synctex-result))
            (setq tex-file  (expand-file-name (match-string 1 synctex-result))
                  line-num (string-to-number (match-string 2 synctex-result)))
          (message "Failed to get tex file and line number. Did you run latex with `--synctex=1'?"))
        `(,tex-file ,line-num))
    (message "Can not found %s" eaf-pdf-synctex-path)
    nil))

(defun eaf-pdf-jump-to-page (url page-num)
  (let* ((pdf-url (expand-file-name url))
         (opened-buffer (eaf-pdf--find-buffer pdf-url))
         (synctex-info (format "%s:0:0" page-num)))

    (if (not opened-buffer)
        (eaf-open pdf-url "pdf-viewer" (format "synctex_info=%s" synctex-info))
      (display-buffer opened-buffer)
      (eaf-call-sync "execute_function_with_args" eaf--buffer-id
                     "jump_to_page_synctex" (format "%s" synctex-info)))))

(defun eaf-pdf-synctex-forward-view ()
  "View the PDF file of Tex synchronously."
  (interactive)
  (let* ((pdf-url (expand-file-name (TeX-active-master (TeX-output-extension))))
         (tex-buffer (window-buffer (minibuffer-selected-window)))
         (tex-file (buffer-file-name tex-buffer))
         (line-num (progn (set-buffer tex-buffer) (line-number-at-pos)))
         (opened-buffer (eaf-pdf--find-buffer pdf-url))
         (synctex-info (eaf-pdf--get-synctex-info tex-file line-num pdf-url)))

    (when (and (one-window-p) (not opened-buffer))
      ;; If the window is sole, then split window
      ;; Original `split-window-sensibly' conflict with `visual-fill-column'
      (if (fboundp 'visual-fill-column-split-window-sensibly)
	      (visual-fill-column-split-window-sensibly)
	    (split-window-sensibly))
      (other-window 1))

    (if (not opened-buffer)
        (eaf-open pdf-url "pdf-viewer" (format "synctex_info=%s" synctex-info))
      (display-buffer opened-buffer)
      (eaf-call-sync "execute_function_with_args" eaf--buffer-id
		             "jump_to_page_synctex" (format "%s" synctex-info)))))

(defun eaf-pdf-synctex-backward-edit (pdf-file page-num x y)
  "Edit the Tex file corresponding to (`page-num', `x' , `y') of the `pdf-file'."
  (let* ((tex-and-line (eaf-pdf--get-tex-and-line pdf-file page-num x y))
         (tex-file (nth 0 tex-and-line))
         (line-num (nth 1 tex-and-line)))
    (when (and tex-file line-num)
      (let ((buffer (get-buffer (file-name-nondirectory tex-file))))
        (if buffer
            (switch-to-buffer-other-window buffer)
          (find-file-other-window tex-file))
        (goto-line line-num)))))

(defun eaf-pdf-outline-edit-buffer-confirm ()
  (interactive)
  (let* ((payload
          (org-element-map (org-element-parse-buffer) 'headline
            (lambda (headline) (let* ((raw-value (org-element-property :raw-value headline))
                                  (level (org-element-property :level headline))
                                  (page-num (and (string-match (rx (1+ num) string-end) raw-value) (match-string 0 raw-value)))
                                  (title (format "%s" (string-trim-right raw-value page-num)))
                                  )
                             (if page-num
                                 (list level (string-trim-right title) (string-to-number page-num))
                               (error "Title: %s has no corresponding page number!" title)))) t))
         )
    (eaf-call-async "execute_function_with_args" eaf--buffer-id "edit_outline_confirm" payload)))

(defun eaf-pdf-extract-page-text ()
  "Display the text of current page in a new buffer."
  (interactive)
  (let ((page-text-buffer (get-buffer-create (format "*Page text: %s*" (buffer-name))))
        (page-text (eaf-call-sync "execute_function" eaf--buffer-id "get_page_text")))
    (unless (string-empty-p page-text)
      (with-current-buffer page-text-buffer
        (erase-buffer)
        (insert page-text)
        (goto-char (point-min)))
      (switch-to-buffer-other-window page-text-buffer))))

;;;; Register as module for EAF
(add-to-list 'eaf-app-binding-alist '("pdf-viewer" . eaf-pdf-viewer-keybinding))

(setq eaf-pdf-viewer-module-path (concat (file-name-directory load-file-name) "eaf_pdf_buffer.py"))
(add-to-list 'eaf-app-module-path-alist '("pdf-viewer" . eaf-pdf-viewer-module-path))

(add-to-list 'eaf-app-bookmark-handlers-alist '("pdf-viewer" . eaf--pdf-viewer-bookmark))
(add-to-list 'eaf-app-bookmark-restore-alist '("pdf-viewer" . eaf--pdf-viewer-bookmark-restore))

(add-to-list 'eaf-app-extensions-alist '("pdf-viewer" . eaf-pdf-extension-list))
(add-to-list 'eaf-app-extensions-alist '("office" . eaf-office-extension-list))

(provide 'eaf-pdf-viewer)
;;; eaf-pdf-viewer.el ends here
