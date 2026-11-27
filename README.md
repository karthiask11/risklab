# Portfolio Risk Lab

Free risk and return tools for NSE stocks (MBA PMS project). Prices from Yahoo Finance.

| Site | Folder | Vercel project setting |
|---|---|---|
| Customer site | `site/` | Root Directory = `site`, Framework = Other, no build command |
| Admin site | `admin/` | Root Directory = `admin`, Framework = Other, no build command |

GitHub Pages also publishes the customer site at https://karthiask11.github.io/risklab/ (with the admin as a backup at `/admin/`).

## Folders

```
src/            source you edit: index_template.html, _core.js (maths), _v2.js (advanced analysis), admin.html
build.py        python build.py  ->  writes site/*.html and admin/index.html from src/
site/           customer site (built pages + data/), has its own vercel.json
  data/         written by the update jobs: prices, stock list, fundamentals, meta, change log
admin/          admin site (built index.html), has its own vercel.json
update.py       evening job: Yahoo Finance prices, stock list (+ admin changes), change log
fundamentals.py about 300 companies' fundamentals a day from Yahoo Finance
live.py         live prices every 15 minutes in market hours (saved to the "live" branch)
firestore.rules Firebase security rules
.github/workflows/update.yml, live.yml   the scheduled jobs
```

To change the site: edit `src/`, run `python build.py`, commit and push.
Not investment advice.
