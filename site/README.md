# site/ — the interactive decision tool

A static, single-page site so a viewer can **feel** the tool: pick any deal
from the twelve-deal book, drag the committee inputs and watch the
buy / build / partner verdict, the zero-line, the synergy-decay signature,
the IRR waterfall and the whole book recompute. No build step, no
dependencies, no server — open `index.html` or deploy the folder.

## What's here

- `index.html` — the page (deal picker, inputs, verdict, live derivation,
  the twelve-deal book, the multiple × capture decision surface, the decay
  signature, the IRR waterfall, build log, hostile attacks, tagged sources).
- `model.js` — the same closed forms as the Python `decision/` package
  (the zero-line `m*(c)`, the strategy net PVs against the target's own DCF
  anchor, the buy price cap, the synergy decay, the IRR gate bridge). UMD,
  so it loads in the browser **and** under Node.
- `app.js` — wires the controls to `model.js`; one `render()` pass
  recomputes everything from the current inputs.
- `style.css` — the dark case-study system.
- `verify.js` — the cross-language pin: asserts the JS numbers equal the
  Python baseline (`out/decision_numbers.json`) to the bit.

## Run it

```bash
node site/verify.js            # the JS pins match the Python baseline
# then open site/index.html, or:
node -e "require('http').createServer((q,s)=>{const fs=require('fs');s.end(fs.readFileSync('site/index.html'))}).listen(8080)"
```

## Deploy to Vercel

From the `site/` folder (so the page is served at the domain root, not
`/site/`):

```bash
cd site
npx vercel            # preview deploy
npx vercel --prod     # production deploy (returns the .vercel.app URL)
```

Redeploy after any edit the same way. The repo's `vercel.json` sets
`rootDirectory: site`, so a git-linked project auto-deploys `site/` on every
push.
