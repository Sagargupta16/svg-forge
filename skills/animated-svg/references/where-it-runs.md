# Where it runs

A forge file is one self-contained SVG, so the same file works on any surface that shows an image: a landing page, an app, a docs site, a package page, a README. This page says what each surface does with an animated SVG and how to ship to it. GitHub's own rules are in [github-readme.md](github-readme.md).

## How a page shows an SVG

- **As an image** (`<img>`, `<picture>`, CSS `background-image`, a Markdown image): the browser runs the file in what the SVG Integration draft calls secure animated mode. Declarative animation (SMIL, CSS animations and transitions) plays; script, external references and interactivity are off (https://www.w3.org/TR/svg-integration/ , W3C draft, read 2026-11-03). MDN lists the same image contexts and says external resources load only when inlined as `data:` URLs (https://developer.mozilla.org/en-US/docs/Web/SVG/Guides/SVG_as_an_image , modified 2025-05-13). Every forge file is built for this mode, so it animates the same everywhere it is an image.
- **Inline** (`<svg>` in the page's HTML): the file joins the page. Hover and focus work and page CSS reaches it, but its ids and classes share the page's namespace. Forge prefixes every id and class with a hash of the input (or `--id-prefix`), so two cards inline on one page do not collide. Validate with `--target web`.
- **As a document** (`<iframe>`, `<object>`, `<embed>`): the image limits do not apply, so script in the file would run. Forge files carry none; prefer `<img>`.

## Surfaces

| Surface | Ship it as | Moves? | Notes |
| --- | --- | --- | --- |
| Landing page, blog, portfolio | `<img>` or the printed `<picture>` | yes | `--size` to the slot (`readme`, `og`, a width, `WxH`); `--device both --breakpoint <your breakpoint>` for a phone file |
| App you build (React, Vue, Svelte, Astro, plain HTML) | the file as an image URL, or inline for hover | yes | an inline file can follow the app's theme switch through CSS variables ([design.md](design.md) section 7); a React scene with Motion is the motion-scene skill |
| Docs site (MkDocs, Docusaurus, VitePress, Starlight) and package pages | a Markdown image, or `<picture>` where raw HTML passes through | yes | a Markdown image is an `<img>` like any other, served by the site itself |
| GitHub README | `<picture>` with `--theme both` | yes | [github-readme.md](github-readme.md) |
| Link previews (`og:image`, LinkedIn, X) | a PNG of the poster frame | no | the Open Graph spec asks only for a MIME type, and Facebook and LinkedIn document sizes, not SVG (https://ogp.me/ , https://developers.facebook.com/docs/sharing/webmasters/images/ , https://www.linkedin.com/help/linkedin/answer/a521928 , read 2026-11-03); both ask for about 1.91:1 and LinkedIn for at least 1200x627, so render `--size 1200x630` (the `og` preset is GitHub's 1280x640 repository preview), then `frames.py --poster` |
| Slides | the poster PNG at `--scale 2` | no | PowerPoint inserts and edits SVG; Microsoft documents that, not animation playback (https://support.microsoft.com/en-us/office/edit-svg-images-in-microsoft-office-69f29d39-194a-4072-8c35-dbe5e7ea528c , read 2026-11-03). For motion on a slide, record the file as a video |
| Email | the poster PNG | no | Gmail rasterizes an SVG image to a PNG; Apple Mail and Outlook are listed as supporting SVG (https://www.caniemail.com/features/image-svg/ , tested 2026-09-16) |
| Favicon | `--size favicon-32` with a mark, linked as `rel="icon"` | not verified | SVG favicons work in Chrome and Edge 80+, Firefox 41+ and Safari 26+ (https://caniuse.com/link-icon-svg , read 2026-11-03); whether a favicon animates was not checked, so keep its rest frame complete |

## A still from the same file

`frames.py FILE.svg --poster` writes one PNG of the rest frame, the static attributes that a still export shows, at the file's own size with a transparent page. `--scale 2` doubles the pixels for slides and high-density screens, `--times 1.2` picks a moment instead, `--theme dark|light` puts a page color behind it and `--width` resizes it. Because forge entrances are poster safe, the rest frame is the finished card, not an empty stage.

```bash
python scripts/forge.py --kind hero --size 1200x630 --data hero.json --out social.svg
python scripts/frames.py social.svg --poster --out social.png
python scripts/frames.py social.svg --poster --scale 2 --out slide.png
```

## Phone and desktop on your own page

`--device both` writes a 320 px phone file and the desktop file. The printed `<picture>` swaps them at `--breakpoint`, 1012 px by default, which is GitHub's. On your own page, pass the width where your layout gets wide, such as 768, and the desktop file shows from there up. A pack takes the same value as `"breakpoint"`.

## Dark and light on your own page

The `<picture>` snippet picks a file with `prefers-color-scheme`, which follows the browser and OS. A page with its own theme toggle should either swap the `src` from its theme state or inline the file with colors from CSS variables ([design.md](design.md) section 7). Inside an image, `prefers-color-scheme` cannot see the page's toggle.
