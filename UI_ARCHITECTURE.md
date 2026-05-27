# Enterprise UI Architecture Documentation

## Core Design Principles
This project implements a **Global Design System** to standardize the UI across all portals (Admin, Teacher, Student) using a premium SaaS-level glassmorphism aesthetic. 

- **Primary Brand Color**: `#5B7CFA` (Indigo/Blue) for a modern, trustworthy feel.
- **Glassmorphism Containers**: Using `backdrop-filter: blur(16px)` layered over subtle gradient backgrounds.
- **Semantic Colors**: Green for success, Red for danger, Orange for warning. (Hardcoded hex values remain consistent to prevent visual jarring).

## CSS Architecture
1. `global_theme.css`: The source of truth for the entire application. It contains:
   - Root variables (`:root`)
   - Reusable layout components (`.dashboard-container`, `.main-content`)
   - Universal buttons (`.btn`, `.btn-primary`, `.btn-light`, etc.)
   - Table and form components
   - Notifications (`.toast-msg`, `.flash-msg`)

2. **Page-Specific Styles**:
   Any styling strictly coupled to JavaScript behaviors (like chart heights, specific absolute positioned badges, canvas wrappers) must remain inside the specific HTML template's `<style>` tag to prevent unintended breakage. Do NOT globalize overly specific layouts.

## Component Naming Conventions
- **Containers**: `.glass-card` is the standard box.
- **Buttons**: All buttons start with `.btn`. Follow with modifiers: `.btn-primary`, `.btn-danger`, `.btn-light`.
- **Forms**: `.form-group` for wrappers, `.form-control` for inputs.
- **Layouts**: Use Flexbox or Grid. Avoid floating and absolute positioning unless strictly necessary for micro-UI elements (like tooltips).

## Sidebar System
The application utilizes an expandable/collapsible sidebar component.
- The sidebar interacts with the `.main-content` area by transitioning its width (`--sidebar-collapsed` vs `--sidebar-expanded`).
- The `.main-content` flexes to consume remaining space. Do not apply hardcoded `margin-left` inline.

## Future Scalability Recommendations
1. **Modularizing Components**: In the future, `.page-header`, `.flash-wrap`, and `.toast-wrap` could be extracted into their own Jinja2 `{% include 'components/header.html' %}` files.
2. **JavaScript Abstraction**: Reusable charting logic across dashboards (student and teacher) could be consolidated into a `charts_module.js` file.
