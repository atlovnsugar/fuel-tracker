# Fuel prices in Europe

Free, static web app. GitHub Actions downloads the data, builds the site and publishes it on GitHub Pages. No server and nothing to run on your computer.

| Data | Source | Refresh |
|---|---|---|
| Petrol (Euro-super 95), diesel, heating oil, LPG, EU-27 countries, weekly since 2005, € per litre, taxes included | European Commission Weekly Oil Bulletin, history file | daily check, updates weekly |
| Household natural gas, half-yearly, € per kWh | Eurostat `nrg_pc_202` | daily check |
| Czech regions (14 kraje), Kč per litre | CCS figures as reported by ČTK | **manual**, see "Adding Czech regional data" |
| Map boundaries | Eurostat GISCO | on every build |

## Setup (about 10 minutes, no software needed)

1. **Create a GitHub account** at https://github.com/signup (free).
2. **Create a repository.** Click **+** (top right) → **New repository**. Name it `fuel-tracker`, choose **Public** (free GitHub Pages requires it), leave "Add a README" unticked, click **Create repository**.
3. **Upload the project.** Unzip the download. On the new repository page click **uploading an existing file**. Drag in the `web` and `scripts` folders and `README.md`. Click **Commit changes**.
4. **Add the workflow file** (it lives in a hidden folder, so create it in the browser):
   - Repository page → **Add file** → **Create new file**.
   - In the name box type exactly `.github/workflows/deploy.yml` (typing each `/` creates a folder).
   - Open `.github/workflows/deploy.yml` from the unzipped project in any text editor (on Mac press Cmd+Shift+. in Finder to show hidden folders), copy everything and paste it into GitHub.
   - Click **Commit changes** → **Commit changes**.
5. **Turn on Pages.** Repository **Settings** → **Pages** (left menu) → under **Build and deployment**, set **Source** to **GitHub Actions**. Nothing else to save.
6. **Run the build.** **Actions** tab → **Refresh data and deploy** → **Run workflow** → **Run workflow**. Wait 1–3 minutes until it shows a green tick. (A run started by step 4 may have failed at "deploy" because Pages was not on yet. That is normal; this manual run replaces it.)
7. **Open your site** at `https://YOUR-USERNAME.github.io/fuel-tracker/` (also shown in the finished run under **deploy**).

After that it refreshes itself daily. If a data download fails, the run turns red and **the previous site stays online**. Note: GitHub pauses scheduled runs in a public repo after 60 days with no repository activity; press **Run workflow** to resume.

## If the build fails

Open **Actions** → the red run → **build** → the step **Run mkdir…** and read the last lines.

- `Oil Bulletin layout not recognised`: the log prints the first rows of each sheet. The EC occasionally changes the file; adjust `parse_sheet` in `scripts/fetch_data.py` (or send me the log).
- `Download failed`: the EC or Eurostat site was temporarily unavailable; re-run later.
- `WARNING: gas data unavailable`: not fatal; the site deploys and the gas chart shows a notice.
- No **Source: GitHub Actions** option or deploy step red with "Pages not enabled": redo step 5, then re-run.

## Adding Czech regional data

There is no free official API for regional pump prices, so `web/cz_regions.json` holds snapshots (currently 15 Feb 2023 and 15 Apr 2026, from CCS via ČTK). To add a week, copy a block in `snapshots`, set the date and the 14 values in the order of `regions` (Praha, Středočeský, Jihočeský, Plzeňský, Karlovarský, Ústecký, Liberecký, Královéhradecký, Pardubický, Vysočina, Jihomoravský, Olomoucký, Zlínský, Moravskoslezský), then commit. The site rebuilds automatically.

## Notes on accuracy

- Bulletin prices are the EC's weekly Monday prices, converted to euro at the rate the EC applies. The "EU average" on the charts is an unweighted mean of the 27 members.
- Gas prices use the household band 20–200 GJ per year if Eurostat provides it (the build log states which one was used).
