# Credly Badges to README

A GitHub Action that fetches **all** your [Credly](https://www.credly.com) badges
— across every page — and injects them into your `README.md`.

Most existing actions scrape the rendered Credly profile page and only capture
the first ~48 badges. This action queries Credly's public JSON endpoint and
follows pagination (`metadata.total_pages`), so **every** badge is included.

## Usage

1. Add the markers where you want the badges to appear in your `README.md`:

   ```md
   <!--START_SECTION:credly-badges-->
   <!--END_SECTION:credly-badges-->
   ```

2. Create a workflow, e.g. `.github/workflows/update-badges.yml`:

   ```yaml
   name: Update badges

   on:
     schedule:
       - cron: "0 2 * * *" # daily at 02:00 UTC
     workflow_dispatch:

   permissions:
     contents: write

   jobs:
     update-readme:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: OrekiYuta/credly-badges-readme@v1
           with:
             credly_user: your-credly-username
   ```

Find your Credly username in your profile URL:
`https://www.credly.com/users/<credly_user>/badges`.

## Inputs

| Input               | Required | Default                                         | Description                                                     |
| ------------------- | -------- | ----------------------------------------------- | --------------------------------------------------------------- |
| `credly_user`       | Yes      | —                                               | Credly username or vanity slug.                                 |
| `sort`              | No       | `RECENT`                                        | `RECENT` = newest first; empty string keeps Credly's order.     |
| `readme_path`       | No       | `README.md`                                     | File to update.                                                 |
| `section_start`     | No       | `<!--START_SECTION:credly-badges-->`            | Start marker.                                                   |
| `section_end`       | No       | `<!--END_SECTION:credly-badges-->`              | End marker.                                                     |
| `badge_size`        | No       | `80x80`                                         | Thumbnail size. Empty = full-size images.                       |
| `max_badges`        | No       | `0`                                             | Limit number of badges (`0` = all).                             |
| `columns`           | No       | `0`                                             | Badges per row via an HTML table. `0` = inline (wraps by width).|
| `commit`            | No       | `true`                                          | Commit and push changes automatically.                         |
| `commit_message`    | No       | `docs: update README with latest Credly badges` | Commit message.                                                 |
| `commit_user_name`  | No       | `github-actions[bot]`                           | Git author name.                                                |
| `commit_user_email` | No       | `github-actions[bot]@users.noreply.github.com`  | Git author email.                                               |

## Outputs

| Output        | Description                                        |
| ------------- | -------------------------------------------------- |
| `badge_count` | Number of badges written to the README.            |
| `changed`     | `true`/`false` — whether the README was modified.  |

## Advanced example

Handle committing yourself and use the outputs:

```yaml
jobs:
  update-readme:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: badges
        uses: OrekiYuta/credly-badges-readme@v1
        with:
          credly_user: your-credly-username
          sort: RECENT
          badge_size: "110x110"
          columns: "5"
          commit: "false"
      - name: Show result
        run: |
          echo "Wrote ${{ steps.badges.outputs.badge_count }} badges"
          echo "Changed: ${{ steps.badges.outputs.changed }}"
```

## Layout

By default badges are written inline and GitHub wraps them to fill the width.
Set `columns` to a number to render a fixed grid using an HTML table — e.g.
`columns: "5"` produces 5 badges per row. Use `0` (default) to keep the inline,
width-based flow.

## Notes

- The action needs `permissions: contents: write` when `commit: true`.
- Only public badges are returned by Credly's endpoint.
- No third-party dependencies — pure Python standard library.

## License

[MIT](LICENSE) © [OrekiYuta](https://github.com/OrekiYuta)
