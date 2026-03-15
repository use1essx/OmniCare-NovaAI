# Healthcare AI Admin - Styling Guide

## Overview

The admin interface now uses a modern, maintainable CSS architecture with easy-to-customize variables and reusable classes.

## File Structure

```
static/css/
├── admin.css              # Original styles (legacy components, chips, buttons)
├── admin-layout.css       # NEW: Layout system, sidebar, header, main content
├── components.css         # Component-specific styles
└── README-ADMIN-STYLING.md # This file
```

## Quick Customization Guide

### 1. Change Colors

Edit the CSS variables in `admin-layout.css`:

```css
:root {
    /* Sidebar Colors */
    --sidebar-bg: #ffffff;              /* Background color */
    --sidebar-border: #e2e8f0;          /* Border color */
    --sidebar-text: #334155;            /* Text color */
    --sidebar-active-bg: #f1f5f9;       /* Active item background */
    
    /* Primary Brand Colors */
    --primary-blue: #2563eb;            /* Main brand color */
    --primary-emerald: #059669;         /* Success color */
    --primary-amber: #d97706;           /* Warning color */
    --primary-rose: #e11d48;            /* Error color */
    
    /* Layout */
    --sidebar-width: 280px;             /* Sidebar width */
    --header-height: 70px;              /* Header height */
    --content-max-width: 1600px;        /* Max content width */
}
```

### 2. Adjust Spacing

```css
:root {
    --content-padding: 2rem;            /* Main content padding */
}

/* Or adjust per breakpoint in the code */
@media (max-width: 640px) {
    .admin-content {
        padding: 1.5rem 1rem;
    }
}
```

### 3. Change Shadows & Borders

```css
:root {
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    
    --radius-sm: 0.5rem;
    --radius-md: 0.75rem;
    --radius-lg: 1rem;
}
```

### 4. Modify Transitions

```css
:root {
    --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

## Component Classes

### Sidebar

| Class | Purpose |
|-------|---------|
| `.admin-sidebar` | Main sidebar container |
| `.sidebar-header` | Header section with logo |
| `.sidebar-nav` | Navigation container |
| `.sidebar-section` | Section grouping |
| `.sidebar-section-title` | Section header text |
| `.sidebar-nav-item` | Navigation link |
| `.sidebar-nav-item.is-active` | Active navigation item |
| `.sidebar-dropdown-toggle` | Dropdown menu button |
| `.sidebar-dropdown-content` | Dropdown menu container |
| `.sidebar-footer` | Footer section |
| `.sidebar-status-card` | Status display card |

### Header

| Class | Purpose |
|-------|---------|
| `.admin-header` | Main header container |
| `.admin-header-container` | Inner container |
| `.admin-header-left` | Left section (title/breadcrumb) |
| `.admin-header-right` | Right section (actions) |
| `.admin-header-title` | Page title |
| `.admin-header-subtitle` | Small label above title |
| `.admin-header-breadcrumb` | Breadcrumb navigation |

### Main Content

| Class | Purpose |
|-------|---------|
| `.admin-layout` | Root layout wrapper |
| `.admin-main` | Main content wrapper |
| `.admin-content` | Content area |
| `.admin-content-bg` | Background decorations |
| `.admin-content-bg-circle` | Decorative circles |

### Utilities

| Class | Purpose |
|-------|---------|
| `.icon-button` | Icon-only button (circular) |
| `.badge` | Small label/tag |
| `.badge-sm` | Smaller badge variant |
| `.hide-mobile` | Hide on mobile devices |
| `.hide-desktop` | Hide on desktop devices |
| `.custom-scrollbar` | Styled scrollbar |

## Examples

### Example 1: Change Sidebar to Dark Mode

```css
:root {
    --sidebar-bg: #1e293b;
    --sidebar-border: #334155;
    --sidebar-text: #e2e8f0;
    --sidebar-text-hover: #ffffff;
    --sidebar-active-bg: #334155;
    --sidebar-active-text: #ffffff;
}
```

### Example 2: Wider Sidebar

```css
:root {
    --sidebar-width: 320px;  /* Default is 280px */
}
```

### Example 3: Custom Brand Color

```css
:root {
    --primary-blue: #7c3aed;  /* Change to purple */
}

/* This will automatically update:
   - Active nav items
   - Hover states
   - Icon button hovers
   - Links
```

### Example 4: Tighter Content Padding

```css
:root {
    --content-padding: 1.5rem;  /* Default is 2rem */
}
```

### Example 5: Remove Background Decorations

```css
.admin-content-bg-circle {
    display: none;
}
```

## Best Practices

1. **Use CSS Variables**: Always modify variables first before changing component styles
2. **Mobile-First**: Test your changes on mobile devices
3. **Accessibility**: Maintain sufficient color contrast (WCAG AA minimum)
4. **Performance**: Avoid heavy box-shadows on many elements
5. **Consistency**: Use existing utility classes before creating new ones

## Responsive Breakpoints

```css
/* Mobile: < 640px */
/* Tablet: 640px - 1023px */
/* Desktop: >= 1024px */

@media (max-width: 640px) { /* Mobile styles */ }
@media (min-width: 1024px) { /* Desktop styles */ }
```

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- Mobile Safari: iOS 13+
- Chrome Mobile: Latest

## Troubleshooting

### Sidebar not showing on mobile
- Check that `.is-open` class is being toggled
- Verify Alpine.js is loaded

### Styles not applying
- Clear browser cache
- Check CSS file is loading in browser DevTools
- Verify no conflicting Tailwind classes

### Colors not changing
- Make sure you're editing `admin-layout.css` not `admin.css`
- Check CSS variable syntax: `var(--variable-name)`
- Reload page with hard refresh (Ctrl+Shift+R)

## Migration Notes

If upgrading from the old system:
1. New CSS file is automatically included in `base.html`
2. Old inline styles and Tailwind classes replaced with semantic classes
3. Backup files created: `sidebar-backup.html`, `header-backup.html`
4. No breaking changes to functionality

## Support

For questions or issues:
1. Check this documentation first
2. Inspect elements in browser DevTools
3. Review CSS variables in `admin-layout.css`
4. Check console for JavaScript errors

