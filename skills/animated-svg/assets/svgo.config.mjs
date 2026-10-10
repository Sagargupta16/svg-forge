// svgo.config.mjs: SVGO v4 preset-default made safe for animated SVGs (SMIL and CSS).
//
//   npx -y svgo@4 --config svgo.config.mjs in.svg -o out.svg
//   python scripts/validate_svg.py out.svg --target standalone
//
// Then compare animation counts before and after; they must match:
//   grep -oE '<(animate|animateTransform|animateMotion|set)\b|@keyframes' FILE | sort | uniq -c
//
// Kept on purpose: viewBox and <title>. SVGO v4 dropped removeViewBox and removeTitle from
// preset-default, so nothing here needs to turn them off:
//   https://svgo.dev/docs/migrations/migration-from-v3-to-v4/
//
// Turned off, and why:
//   cleanupIds                  rewrites ids that begin="a.end", href="#a" and url(#a) need;
//                               it only backs off when the file has <style> or <script>
//                               https://svgo.dev/docs/plugins/cleanupIds/
//   removeHiddenElems           deletes opacity="0" elements, the start state of every fade-in
//                               https://svgo.dev/docs/plugins/removeHiddenElems/
//   removeUselessDefs           drops defs that animations or <use> still need
//                               https://github.com/svg/svgo/issues/2290
//   moveGroupAttrsToElems       moves a group transform onto its children, which breaks
//                               animateTransform and CSS transforms on the group
//                               https://github.com/svg/svgo/issues/1437
//   removeUselessStrokeAndFill  removes strokes that are invisible at rest but drawn later
//                               https://github.com/svg/svgo/issues/1677
//   convertShapeToPath          turns <rect>/<circle> into <path>, so attributeName="width"
//                               or "r" targets an attribute that no longer exists
//                               https://github.com/svg/svgo/issues/1634
//   removeUnknownsAndDefaults   strips href from <animate> elements that target another one,
//                               and role="img" from the root (seen with svgo 4.1.0)
//                               https://github.com/svg/svgo/issues/2061
// Precautions (no open issue; each follows from the plugin's source):
//   convertEllipseToCircle      same failure as convertShapeToPath for attributeName="rx"/"ry"
//                               https://svgo.dev/docs/plugins/convertEllipseToCircle/
//   moveElemsAttrsToGroup       in a file without <style>, hoists a transform shared by the
//                               children onto the group; a child's own animateTransform
//                               then no longer replaces it
//                               https://svgo.dev/docs/plugins/moveElemsAttrsToGroup/
//   collapseGroups              folds a positioning <g transform> into a child that CSS
//                               animates; the CSS transform then replaces it
//                               https://svgo.dev/docs/plugins/collapseGroups/
//   mergePaths                  joins sibling paths with equal attributes, so a shared
//                               line-draw class dashes one combined path and nth-child
//                               staggers shift
//                               https://svgo.dev/docs/plugins/mergePaths/
//   inlineStyles                moves .x { animation: ... } into a style attribute, which then
//                               outranks a @media (prefers-reduced-motion) block
//                               https://svgo.dev/docs/plugins/inlineStyles/
//   removeDesc                  keeps the <desc> that aria-labelledby points at
//                               https://svgo.dev/docs/plugins/removeDesc/
//
// Path morphs that interpolate from the base d (to= with no values list): also set
// convertPathData: false, because it may rewrite the base path into different commands.
export default {
  multipass: true,
  plugins: [
    {
      name: "preset-default",
      params: {
        overrides: {
          cleanupIds: false,
          removeHiddenElems: false,
          removeUselessDefs: false,
          moveGroupAttrsToElems: false,
          removeUselessStrokeAndFill: false,
          convertShapeToPath: false,
          removeUnknownsAndDefaults: false,
          convertEllipseToCircle: false,
          moveElemsAttrsToGroup: false,
          collapseGroups: false,
          mergePaths: false,
          inlineStyles: false,
          removeDesc: false,
        },
      },
    },
  ],
};
