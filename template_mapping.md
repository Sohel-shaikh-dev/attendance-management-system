# Template Standarization Mapping Log

This document serves as a backup mapping for the template standardization phase.
All routing logic, backend endpoints, and functionalities were preserved. Only the internal template filenames and `render_template` calls were safely updated to establish a clean, scalable enterprise-level architecture.

## Naming Convention Rules
- `admin_` prefix: Used for system-wide, global, or administrative functions (e.g., global notices).
- `teacher_` prefix: Used for academic, classroom, and teacher-specific functions (e.g., attendance).
- `student_` prefix: Used for the student portal.

## Renames Executed

| Old Template Name | New Template Name | Associated Routes / Endpoints |
| --- | --- | --- |
| `attendance_summary.html` | `teacher_attendance_summary.html` | `/attendance_summary`, `/teacher_panel` |
| `teacher_attendance_form.html` | `teacher_attendance_mark.html` | `/teacher` |
| `add_notice.html` | `admin_notice_add.html` | `/notice`, `/teacher_notice`, `/add_notice` |
| `all_notices.html` | `admin_notice_list.html` | `/all_notices` |
| `edit_notice.html` | `admin_notice_edit.html` | `/edit_notice/<int:notice_id>` |
| `view_notice.html` | `admin_notice_view.html` | `/view_notice/<int:notice_id>` |
| `student_my_tickets.html` | `student_ticket_list.html` | `/student/support/tickets` |

## Orphaned Templates (Left Untouched)
*These templates were identified as disconnected from any active route but have been kept for safety.*
- `teacher_panel.html`
- `teacher_login.html`
- `notice.html`
