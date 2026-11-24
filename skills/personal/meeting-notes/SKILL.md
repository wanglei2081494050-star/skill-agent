---
name: meeting-notes
description: 把会议语音转写整理成决议清单：区分决议、待办、争议点，每条待办带负责人和截止时间。
metadata:
  version: 1.0.0
  tags: [notes, personal]
allowed-tools:
  - read_skill_file
---

# Meeting notes

## Steps

1. Read the transcript; drop small talk.
2. Extract in this order: 决议 (decided) / 待办 (action) / 争议 (unresolved).
3. Every action item needs owner + due date; if the transcript omits one, mark it
   `TBD` instead of inventing it.
4. Keep the original wording for decisions so the record stays auditable.
5. Deliver a three-section markdown list.
