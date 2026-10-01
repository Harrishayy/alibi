# StatusDot

A status mark that never relies on hue alone: each label has its own shape as well as its colour.

**Use it for** samples in the `SampleStrip`, the online dot in the island header, legends, timeline markers and the corrected dot in "Fix a moment".

**You provide** `label` and an optional `size` (default 12px). Pass `text` to show the word beside the mark, which every legend and list needs.

| Label | Mark | Word |
|---|---|---|
| `on_task` | ● filled circle in `on-task` | On task |
| `idle` | ○ 2px ring in `idle` | Idle |
| `phone` | ■ rounded square in `phone` | Phone |
| `off_task` | hatched disc in `off-task` | Off task |
| `absent` | dashed ring in `absent` | Away |

Marks under 16px switch to the matching `-ink` token in the light theme so they hold 3:1 on white. `phone` and `off_task` share the red; the hatch tells them apart. Without `text` the mark is a `role="img"` with its word as the label.

- Do: recolour a corrected dot in place on `spring-micro`, with a pop on `spring-bouncy`.
- Don't: use green and amber marks without their shapes, or tint Pinch to show status.
