# Setup — from zero to a live site

> **Quick start:** to just run it on your Mac, double-click **`START HERE.command`**
> in this folder. It installs everything, asks for your API key, runs the watcher,
> and opens the result. You only need step 3 below (getting the key) first.
>
> The rest of this guide is for putting it on GitHub and making it public, which
> is what turns it into something you can link on a resume.

Follow these in order. Total time about 40 minutes, most of it waiting.

---

## 1. Create a GitHub account (5 min)

Go to **github.com/signup**.

Your username becomes part of your public URL and recruiters will see it, so use
something professional — `mahyra-afif` or `mahyraafif`, not a nickname.

While you're there, fill in your profile: real name, a photo, and a one-line bio.
An empty profile next to a good repo looks abandoned.

---

## 2. Install the tools (10 min)

Open **Terminal** on your Mac (Cmd+Space, type "Terminal").

Check what you already have:

```bash
python3 --version
git --version
```

If Python is missing or below 3.10, install it from **python.org/downloads**.
If Git prompts you to install developer tools, accept.

---

## 3. Get an Anthropic API key (5 min)

1. Go to **console.anthropic.com** and sign in.
2. **API Keys** → **Create Key**. Name it `ai-price-watch`.
3. Copy it immediately — you can't view it again.
4. Add about $5 of credit under **Billing**. At roughly $0.02 per weekly run,
   that lasts years.

**Never paste this key into a file you commit.** It goes in `.env` (already
gitignored) and into GitHub Secrets. If you ever leak one, revoke it in the
console right away.

---

## 4. Run it locally (10 min)

**Easy way:** double-click **`START HERE.command`** in this folder. It handles
everything — installing dependencies, saving your key, running the tests, running
the watcher, and opening the result in your browser.

If macOS says it can't be opened because it's from an unidentified developer:
right-click the file → **Open** → **Open** again. You only do this once.

**Terminal way**, if you prefer it:

```bash
cd ~/Desktop/ai-price-watch

pip3 install -r requirements.txt

cp .env.example .env
open -e .env                      # paste your key after the =, save, close

export $(cat .env | xargs)
python3 -m pytest tests/ -q       # should print "13 passed"
python3 -m src.run
```

The first run takes a couple of minutes — it fetches ten pages and extracts each
one. It will report no changes, which is correct: the first run only establishes
the baseline. Changes appear from the second run.

Open `site/index.html` in your browser to see the result.

**If a provider shows as broken:** that's the guard working. Some pricing pages
render entirely in JavaScript and won't extract from plain HTTP. Remove those
sources from `config/sources.yaml` and keep the ones that work — eight solid
providers beats ten with two permanently broken.

---

## 5. Push to GitHub (10 min)

Create the repo: **github.com/new** → name it `ai-price-watch` → **Public** →
don't add a README (you have one) → **Create repository**.

Then, in Terminal, from the project folder:

```bash
git init
git add .
git commit -m "AI pricing watcher: fetch, extract, diff, publish"
git branch -M main
git remote add origin https://github.com/USERNAME/ai-price-watch.git
git push -u origin main
```

Replace `USERNAME` with yours. GitHub will ask you to authenticate in a browser.

**Before you push, confirm your key isn't in there:**

```bash
git status --porcelain | grep -q "\.env$" && echo "STOP - .env is staged" || echo "safe"
```

---

## 6. Add the key as a secret (2 min)

Your repo → **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**.

- Name: `ANTHROPIC_API_KEY`
- Value: your key

This is how the weekly job authenticates without the key ever being in the code.

---

## 7. Turn on the public page (3 min)

Repo → **Settings** → **Pages**.

- Source: **Deploy from a branch**
- Branch: `main`, folder: **/site**
- **Save**

Wait about a minute. Your site is live at:

```
https://USERNAME.github.io/ai-price-watch/
```

Put that URL in the README (replace the three `USERNAME` placeholders) and in the
repo's **About** section on the right of the repo page.

---

## 8. Test the automation (2 min)

Repo → **Actions** tab → **watch** → **Run workflow**.

Watch it run. Green check means the whole thing works unattended from here — it
will run itself every Monday at 9:00 UTC and commit what it finds.

If it fails, click into the failed step and read the error. The usual causes are
a missing secret (step 6) or a provider blocking the request.

---

## After it's live

**Add the preview image.** Take a screenshot of your live site, save it as
`docs/preview.png`, and push. The README references it.

**Let it run for three weeks before you show anyone.** An empty change log is the
one thing that makes this look unfinished. Three weeks of real detected changes is
what makes it look alive.

**Then write the post.** Once you have real findings — "in six weeks of watching,
these four providers cut prices and here's the pattern" — that's the LinkedIn post,
and the post is what gets the project seen.

---

## What to say about it in an interview

You'll get asked how it works. The two answers worth having ready:

**"How did you decide what counts as a meaningful change?"**
Two layers. Structurally, I don't diff HTML — I extract a normalized record per
model and diff that, because pricing pages get rebuilt constantly and HTML diffing
gives you a false positive nearly every run. Then within real changes, anything
under 5% is logged but not headlined, so a rounding adjustment doesn't read the
same as a price cut.

**"What was the hardest part?"**
Handling silent failure. A scraper that breaks and returns nothing reports "no
changes" forever, and you keep trusting it. So every source declares a minimum
number of models it should return, and a run below that is marked broken — the old
data is preserved, nothing is reported as removed, and the site says which sources
need attention. Failing loudly mattered more than any of the extraction logic.
