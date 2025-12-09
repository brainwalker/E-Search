# E-Search Documentation

Welcome to the E-Search documentation! This directory contains all project documentation organized by topic.

## Quick Links

### 🚀 Getting Started
- [Quick Start Guide](guides/quickstart.md) - Get up and running quickly
- [Project Summary](project/summary.md) - Overview of the project

### 💾 Database
- [Database Schema](database/schema.md) - Complete database structure reference
- [Locations System](database/locations.md) - Location table implementation
- [Migration Guide](database/migrations.md) - Database migration instructions

### 📖 Guides
- [Quick Start](guides/quickstart.md) - Installation and setup
- [Sync Guide](guides/sync-guide.md) - Using the sync command
- [Git Workflow](guides/git-workflow.md) - Git commands and workflow
- [Branching Strategy](guides/branching.md) - Branch management guide
- [Crawlee Migration Plan](guides/crawlee-migration-plan.md) - **NEW** Multi-source scraper migration
- [Site Implementation Checklist](guides/site-implementation-checklist.md) - **NEW** Per-site progress tracking

### 📊 Project Information
- [Project Analysis](project/analysis.md) - Detailed project analysis
- [Project Summary](project/summary.md) - High-level overview
- [Folder Structure Plan](project/structure-plan.md) - Project organization
- [Verification Report](project/verification.md) - Frontend/backend verification

### 🔌 API Documentation
- API endpoint documentation (coming soon)
- Response schemas (coming soon)

## Documentation Structure

```
docs/
├── README.md (this file)
│
├── database/          # Database documentation
│   ├── schema.md
│   ├── locations.md
│   └── migrations.md
│
├── guides/            # User guides
│   ├── quickstart.md
│   ├── sync-guide.md
│   ├── git-workflow.md
│   ├── branching.md
│   ├── crawlee-migration-plan.md  # 🆕
│   └── site-implementation-checklist.md  # 🆕
│
├── project/           # Project documentation
│   ├── analysis.md
│   ├── summary.md
│   ├── structure-plan.md
│   ├── verification.md
│   └── verification-report.md
│
└── api/              # API documentation
    └── (coming soon)
```

## Contributing to Documentation

When adding new documentation:
1. Choose the appropriate category folder
2. Use clear, descriptive filenames
3. Add a link to this README
4. Follow the existing markdown formatting style
5. Include code examples where appropriate

## Documentation Standards

- **File naming**: Use lowercase with hyphens (e.g., `quick-start.md`)
- **Headers**: Use sentence case for headers
- **Code blocks**: Always specify language for syntax highlighting
- **Links**: Use relative links for internal documentation
- **Examples**: Include practical examples and screenshots where helpful

## Need Help?

- Check the [Quick Start Guide](guides/quickstart.md) first
- Review the [Project Summary](project/summary.md) for an overview
- See the [Database Schema](database/schema.md) for data structure info
