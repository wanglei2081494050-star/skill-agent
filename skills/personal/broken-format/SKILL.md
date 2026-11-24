---
	name: broken-format
	description: 这个文件故意写成非法 frontmatter：使用 tab 缩进，且缺少 description 字段。
  tags: [demo, broken]
---
# Broken skill (intentionally invalid)

This file is a fixture. The scanner must skip it and report why:
tab indentation is not valid YAML, the closing `---` may be missing, and
`description` is missing. It must never break startup.
