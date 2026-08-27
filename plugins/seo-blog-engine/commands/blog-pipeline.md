---
description: Run one article through the SEO blog engine end to end (draft → gates → CMS draft). Usage: /blog-pipeline <topic or path to brief/Google-Doc export>
---

Run the `pipeline-run` skill for this website on the topic or brief below.

Preflight: confirm `project.yaml`, `BRAND.md`, `VOICE.md`, and `.env` exist in the working
directory; if not, run `project-init` first. Load `brand-loader`, then execute
`pipeline-run` in order, stopping and reporting at GATE 1. Never publish live.

Topic / brief:
$ARGUMENTS
