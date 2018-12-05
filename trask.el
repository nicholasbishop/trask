(defconst trask-mode-syntax-table
  (let ((table (make-syntax-table)))
    ;; ' delimits strings
    (modify-syntax-entry ?' "\"" table)
    ;; # starts a comment
    (modify-syntax-entry ?# "<" table)
    ;; \n ends a comment
    (modify-syntax-entry ?\n ">" table)
    (modify-syntax-entry ?{ "(}" table)
    (modify-syntax-entry ?} "){" table)
    table))

(defconst trask-mode-keywords
  '("true" "false"))

(defconst trask-mode-font-lock-defaults
  `((
     ("^\\([a-zA-Z0-9-_]+\\) {" . (1 font-lock-function-name-face))
     ( ,(regexp-opt trask-mode-keywords 'words) . font-lock-builtin-face)
     )))

(defvar trask-mode-indent-offset 2)

;; https://stackoverflow.com/questions/4158216/emacs-custom-indentation
(defun trask-mode-indent-line ()
  (interactive)
  (let ((indent-col 0))
    (save-excursion
      (beginning-of-line)
      (condition-case nil
          (while t
            (backward-up-list 1)
            (when (looking-at "[[{]")
              (setq indent-col (+ indent-col trask-mode-indent-offset))))
        (error nil)))
    (save-excursion
      (back-to-indentation)
      (when (and (looking-at "[]}]") (>= indent-col trask-mode-indent-offset))
        (setq indent-col (- indent-col trask-mode-indent-offset))))
    (indent-line-to indent-col)))

(define-derived-mode trask-mode fundamental-mode "Trask Mode"
  :syntax-table trask-mode-syntax-table
  (setq font-lock-defaults trask-mode-font-lock-defaults)
  (font-lock-fontify-buffer)
  (make-local-variable 'trask-mode-indent-offset)
  (set (make-local-variable 'indent-line-function) 'trask-mode-indent-line)))
