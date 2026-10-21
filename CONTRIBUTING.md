# Contributing to MedSearch

MedSearch is a completely free and open source tool written under the spirit of the Open Science concept. Any contribution in that very spirit is welcome, while contributions with the goal of closing source or obstructing access to knowledge is strongly disincentivized and will be rejected.

Everyone taking part is expected to follow the [code of conduct](CODE_OF_CONDUCT.md).

## Reporting a problem

Open an [issue](https://github.com/H4lBarAd11/MedSearch/issues/new/choose) and choose
**Report a problem**. The form asks for what makes a problem possible to find:

- what you did, what happened, and what you expected instead;
- the MedSearch version, shown in **Settings ▸ Updates** (on iPhone and iPad, under the
  MedSearch name on the start screen), and your system (macOS, Windows, iOS or iPadOS, and
  its version);
- the databases that were ticked, when it is about a search.

The installed app keeps a record of what it does, `medsearch.log`, in the `.medsearch`
folder of your home folder. The lines from around the problem help. Web addresses in it are
cut short, so it holds no sign-in, but read it before you post it: it can contain the words
you searched for.

A security problem is not reported in a public issue: see [SECURITY.md](SECURITY.md).

## Suggesting a feature

Open an issue and choose **Suggest a feature**. Say what you would like to do and why, for
example the kind of search it would help with. For a new source, name the database and, where
there is one, its public API.

## Changes in code

Small fixes (a typo, a plain bug) are welcome as a pull request straight away. Anything
larger, open an issue first and say what you have in mind, so it is agreed before you spend
time on it.

### Running it from source

```bash
git clone https://github.com/H4lBarAd11/MedSearch.git
cd MedSearch
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python app.py
```

While an installed MedSearch is open, a start from source hands over to it and exits, so quit
that one first.

### What a change needs

- **Tests.** `python -m pytest` runs the whole suite, the page's own tests included (in
  Node, when it is installed). It passes, and the change comes with a test that fails without
  it. The suite never reaches the network or your own settings: every outside service is
  replaced by a fake, and the settings live in a throwaway folder.
- **A line in [CHANGELOG.md](CHANGELOG.md)** for anything a user would notice, under the
  version being prepared: one line, in plain words, with no internals. The update prompt
  shows that file to users before they update.
- **Comments that say what the code does and why.** Names, dates and the story of a change
  belong in the CHANGELOG and in git, not in the code.
- **The house style.** Interface changes keep MedSearch's palette and what each colour means
  (sage for a good outcome, caramel for a caveat, magenta for danger or a retraction), DM
  Sans, and the drawn line icons. A change of look is proposed in its issue first.

### Licence

MedSearch is under the [Apache License 2.0](LICENSE). A contribution is made under the same
licence (its section 5), so what is contributed stays as open as the rest.
