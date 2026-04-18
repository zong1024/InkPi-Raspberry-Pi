# InkPi Overleaf Paper

This folder is a self-contained Overleaf-ready paper project for the current InkPi system.

## Files

- `main.tex`: paper source
- `figures/system-flow.png`: overall project flow chart
- `figures/qt-home.png`: Qt home UI screenshot
- `figures/qt-result.png`: Qt result UI screenshot

## Recommended Overleaf Setup

1. Create a new Overleaf project.
2. Upload the whole `paper/overleaf` folder or zip it first and upload the zip.
3. The project already includes `latexmkrc`, so Overleaf should use `XeLaTeX` automatically.
4. If Overleaf still keeps an old setting, switch the compiler to `XeLaTeX` manually and recompile `main.tex`.

## Notes

- The paper is written against the current project state as of `2026-04-19`.
- The current paper wording assumes formal support for `楷书 + 行书` single-character evaluation only.
- The public backend deployment described in the text corresponds to the current Debian 12 backend node.
- If you need to replace the author, school, or course information, edit the title block in `main.tex`.
