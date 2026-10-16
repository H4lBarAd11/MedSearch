# What changed

The newest version first. MedSearch shows the entry for a new version in the
update prompt, so this file is what a user reads before choosing to update:
one line per change, in plain words, no internals.

## 2.2

- New database, free: NCBI Bookshelf. Its books and chapters (StatPearls, GeneReviews, NICE and WHO guidelines, health technology assessments and many more) are found with the same search, years, Strict, author and institution as PubMed, and by DOI. Each is tagged Book, and Read on Bookshelf opens it in a MedSearch window.
- Guidelines now lists the NICE and WHO guidelines kept on NCBI Bookshelf. PubMed returned them, but MedSearch left them out.
- PubMed lists papers only, and the books are under NCBI Bookshelf. A PubMed search showed fewer results than asked for when some of them were books.
- Book is a choice in the results' study-type filter when the list has books.
- Exports and Zotero: a chapter is saved as a chapter of its book, with the book's title, editors and publisher, and a whole book as a book, with its ISBN.
- New database, free: Open Library, the Internet Archive's catalogue of books. A book in the public domain is read free (Read free); many others can be borrowed for an hour or for two weeks with a free Internet Archive account (Borrow). Find in a library looks the book up in WorldCat, the shared catalogue of libraries worldwide, and Open Library opens its page there. Each opens in a MedSearch window, which keeps your sign-in.
- Books that share a short title, such as "Glioma", are no longer taken for one another: a book is shown once only when the same book, by the same first author and from the same year, is found twice.
- The books and chapters OpenAlex and Crossref find are tagged Book and exported as books, with the book's title, editors, publisher and ISBN where Crossref has them. Find in a library looks them up in WorldCat, a chapter as its book.
- Crossref also finds whole books: books, monographs, edited books and reference books.
- A book that OpenAlex or Crossref finds is called free only when there is a PDF of it. OpenAlex and Unpaywall list some paid books as free because of a web page that is not the book, and those now open through your library instead.
- New database, with a free key from a Google Cloud project, added in Settings: Google Books. It knows most books in print, recent editions included. A book in the public domain is read free; for many others Preview shows the pages the publisher allows. Find in a library looks each one up in WorldCat by its ISBN. What may be read depends on the country you search from.
- Library resources, in Settings: tick ClinicalKey, AccessMedicine or UpToDate, or add another platform your library subscribes to, such as Thieme MedOne, with the address of one of its searches. Each gets a Search button at the bottom of the Databases panel, which opens it in its own window through your library, with your search filled in.
- Languages, under Options: add one, and searches find only papers and books in English and that language, English first. A chip beside the search bar shows the languages in use, and its cross goes back to any language. The choice is kept for the next start. Web of Science, Crossref, CORE, arXiv, IEEE Xplore and Semantic Scholar can't be asked for a language: they say so above their results, and leave out only what they say is in another language.
- The menu bar's quick search can use NCBI Bookshelf, Open Library or Google Books as its default source.
- Open at login always starts the installed MedSearch when there is one. When a copy run from its source code turned it on, MedSearch started at login as Python: the Mac showed it with Python's name and icon, and its menu bar icon appeared only with Python allowed in the menu bar (Windows likewise listed Python among the Startup apps). MedSearch now puts such a login item right each time it starts.
- Settings ▸ Uninstall MedSearch, in the installed app: the app, its settings, recent and saved searches, exports and the web data of its windows go to the Trash (on Windows to the Recycle Bin, and Windows' own uninstaller removes the app), and MedSearch quits. API keys and library sign-ins are kept, for a later install.
- Settings says where the email for Unpaywall goes: to Unpaywall, Crossref, NCBI and Open Library, as the contact they ask apps for, and nowhere else. It used to say Unpaywall only.

## 2.1

- Six new databases. Free: Europe PMC (PubMed and PubMed Central, plus preprints from medRxiv, bioRxiv and other preprint servers), OpenAlex, Crossref and CORE. With a free key from each, added in Settings: IEEE Xplore and Semantic Scholar.
- OpenAlex and CORE work without a key. A free key from either, added in Settings, lets it answer more searches a day or a minute.
- Search by DOI asks the new databases as well, each by its own DOI field. IEEE Xplore is asked only about IEEE's own DOIs, as its key allows 200 calls a day.
- Google Scholar: Search Google Scholar, at the bottom of the Databases panel, opens Scholar in its own window with your search and years filled in. Scholar can't be searched from another app, so its results are not added to the list.
- Search by author and by institution, under Options. Type a name and pick it from OpenAlex's suggestions, which show each person's institution, number of papers and ORCID. OpenAlex then finds exactly that person or institution; the other databases match the name as written, with the ORCID where they keep it, and miss papers that spell it differently. A name you don't pick is searched as typed.
- With an author or an institution set, the search box can be left empty: the search lists everything by them. Each one in use shows as a chip beside the search bar, and its cross removes it. Saved searches keep both, and Search Google Scholar passes the author on.
- A database that keeps no authors (Semantic Scholar) or no institutions (arXiv, CORE, Crossref, Semantic Scholar) says so and is left out of such a search, rather than show papers that don't match.
- Fewer repeated papers in the list. A paper is now also recognised by its PubMed ID, and by its title, year and first author when a database lists a repository's copy under another DOI (OpenAlex does). Papers without a title are no longer taken for one another, and titles that differ only by a Greek or other non-Latin letter stay apart.
- Citations: the papers that cite a paper now come from OpenAlex too, with no key, alongside PubMed, Scopus and OpenCitations. OpenAlex often finds many that the others miss.
- Options: the Relevance / Recent switch fills its row in two equal halves, and no longer wobbles when pressed.

## 2.0

- MedSearch for Windows is ready: searching, the icon by the clock, library sign-ins, article windows and PDFs have all been through a hands-on check on Windows 11.
- Windows: searches work on every PC. On a PC that had not yet stored the certificates some databases use, every database said it didn't respond.
- Windows: when Windows closes MedSearch, to sign out, shut down or install an update, MedSearch now quits cleanly. It used to crash.
- Windows: library sign-ins work, Remember sign-in included. In 1.31 they were off on Windows.
- Windows: Search MedSearch… in the menu of the MedSearch icon by the clock brings the window forward, ready to type. Open MedSearch window is gone from that menu, as it did the same.
- The installed app keeps a record of what it does, medsearch.log in the .medsearch folder of your home folder, to attach to a problem report. Web addresses in it are cut short, so it never holds a sign-in.

## 1.31

- MedSearch is now an app to download and install on a Mac (Intel or Apple silicon, macOS 12 and later): no Python, no git, no Terminal. It is on the Releases page on GitHub.
- New: MedSearch for Windows 10 and 11, with its own installer. It is built and checked with every release but not yet used day to day, so reports of anything that doesn't work are welcome.
- The installed app updates itself: Update now downloads the new version, puts it in place and reopens, in a few seconds.
- A Mac that runs MedSearch from a git folder is offered Move to it: MedSearch goes into Applications, and the Desktop icon and Open at login open it from then on. Settings, keys, history and saved searches stay as they are.

## 1.30

- Search by DOI: paste a DOI, a doi.org link or a link to the article, or several DOIs at once, and each ticked database looks those papers up. Years and Strict don't apply. A paper none of the ticked databases has is shown from Crossref, and a DOI nobody knows is reported, so it can be checked for a typo. ClinicalTrials.gov says it can't be searched by DOI; arXiv looks up its own DOIs.

## 1.29

- Checking for a new version no longer uses up GitHub's hourly allowance, which all the Macs on one network share: MedSearch now asks in a way GitHub does not count.
- When an update fails, closing its message puts the offer off until the next day, as Later does. It used to come back each time the window came up.
- The update offer no longer opens over a PDF you are reading.

## 1.28

- A new version is offered within a minute of its release, each time the MedSearch window comes up. It used to be offered only when MedSearch started, so a MedSearch kept in the menu bar could miss it for weeks, and for five minutes after a release it was not seen at all.
- Later puts the offer off until the next day.
- Settings has a Check for updates button. It shows the update if there is one, and otherwise says that this is the latest version, or that GitHub could not be reached.

## 1.27

- On a Mac where Python was installed from python.org, searches work from the first start. Until now every database said it didn't respond, and updates looked offline, until Python's "Install Certificates" step had been run by hand. MedSearch now uses the Mac's own certificates when Python has none.

## 1.26

- Save in the PDF viewer now puts the PDF in your Downloads folder, named after the article, and says so. It used to show the PDF in place of MedSearch, and closing the window then left MedSearch stuck on the PDF until you quit.
- Nothing can take MedSearch's own window away from MedSearch any more: a link, a script or a file dropped on it is refused.
- A paper is no longer called free when the only free part is its graphical abstract, a picture that the open-access indexes list as the PDF for Elsevier papers. It is offered through your library instead. An openly licensed paper now opens at its publisher, not at its entry in the DOAJ directory. Free-copy answers from the last three days are checked again.

## 1.25

- The temporary log of what PDF buttons ask for (added in 1.22 to find Ovid's) is removed, and its file is deleted.

## 1.24

- Ovid's PDF button opens the PDF. A new window a site asks for is now opened the way Safari opens it, as a window of the page that asked for it: Ovid hands over the PDF only to such a window, and sent any other one back to the article.

## 1.23

- New-tab links in article windows open a window again: since 1.20, MedSearch asked for those windows in a way that made no window at all. (Ovid's PDF still did not open: see 1.24.)

## 1.22

- Temporary, to find out why Ovid's PDF button still does nothing: for 20 seconds after you click something labelled PDF in an article window, MedSearch notes what that button asked for in a file on this Mac (~/.medsearch/articles.log). Parts of web addresses that could hold a session are cut short. It will be removed once Ovid works.

## 1.21

- Ovid's PDF button, and any other site's button that sends a form to a new window, now opens the PDF in a new MedSearch window, still signed in to your library. It did nothing at all.

## 1.20

- A site's PDF button in an article window now opens the PDF in a new MedSearch window, still signed in to your library. It used to send you to Safari to sign in again, or do nothing at all.
- A PDF that a site sends as a file is now saved to your Downloads folder and opened in Preview. Other files are saved there and shown in the Finder. They used to be dropped without a word.
- The databases you tick in the Databases panel are remembered: MedSearch starts with them after quitting or updating, instead of PubMed alone. A quick search from the menu bar, or a saved search run again, does not change them.
- The Settings button shows a gear instead of a sun.

## 1.19

- MedSearch opens with a splash: the icon's book and magnifier are drawn in the middle of the screen while it loads, and the window then opens out of them.
- Each library in Settings has a new "Remember sign-in" box. Tick it and MedSearch keeps your library login in the Keychain; the next time the library's login page appears, it is filled in and sent for you. It is filled only on that library's own site, and unticking the box deletes it. It starts unticked, since a Mac shared by several people would otherwise sign everyone in as the first person.

## 1.18

- Closing the PDF viewer with the window's red button or ⌘W now closes only the viewer. It used to hide the whole MedSearch window in the menu bar. The same goes for any other MedSearch dialog that is open; with nothing open, closing the window hides it in the menu bar as before.

## 1.17

- The MedSearch window no longer stays blank when it is opened again right after quitting. macOS could end the part of the window that draws the page just as it started; MedSearch now loads the page again whenever that happens.

## 1.16

- The citation window's "Cited by" list now also asks PubMed and Scopus (with your Scopus key) who cites the paper, so it finds more of the papers that cite it, and says which source found each one. If a source failed or has no key, the window says so, so a short list is never passed off as the whole story.
- Scopus results now come with their abstracts, taken from PubMed where PubMed has the paper. A Scopus result without one says why: not in PubMed, or PubMed could not be reached.
- Scopus searches for more than 25 results work: Scopus refused them, and MedSearch now asks for them 25 at a time.
- When Scopus cannot be reached at all, MedSearch says so plainly instead of "HTTP no answer".

## 1.15

- Free articles from PubMed Central now open in MedSearch's own PDF viewer. PubMed Central refuses to hand its PDFs to programs, so the viewer either sent you to the browser or fetched a copy from Sci-Hub; it now takes them from the open-access copy NCBI publishes for programs to use.

## 1.14

- On Macs that use Apple's own Python, MedSearch now shows in the Dock under its name and icon instead of "python3" with a blank icon.

## 1.13

- Web of Science now answers ordinary searches. It only accepted queries written in its own field syntax, so a plain search like "glioblastoma" was refused; MedSearch now searches titles, abstracts and keywords for you. Queries already written in Web of Science syntax (TI=, AU=, …) are sent as they are.

## 1.12

- Web of Science works again. Every search was being refused because MedSearch asked for its results in an order the service no longer accepts, and the answers it did get were read in a shape the service no longer uses. Results now carry their DOI, PubMed ID and citation count.

## 1.11

- Opening MedSearch again while it is running in the menu bar (from Spotlight, Launchpad or the Finder) now brings its window back. It used to do nothing.
- The menu bar icon steps aside while MedSearch is the app in front, and returns when you switch to another app or close the window.

## 1.10

- Scopus now says when an API key is wrong instead of sending you to the VPN. A mistyped key and an off-campus connection used to give the same message.
- Web of Science's refusal message now mentions a subscription still awaiting approval.

## 1.9

- The menu bar icon is back. macOS was refusing it to the process it starts MedSearch as; MedSearch now starts a step out of the way, which it does not refuse. Nothing else changes — it is still MedSearch in the Dock and the app switcher.

## 1.8

- The menu bar icon no longer goes missing after a restart. Starting MedSearch while the previous copy was still closing left the icon with nowhere to go, and macOS never gave it a place afterwards — it now asks again until it has one.
- The icon stays where you put it: ⌘-drag it along the bar and that is where it will be next time.
- If the icon is ever missing, MedSearch writes down when and why (`~/.medsearch/menubar.log`).

## 1.7

- Changing a setting no longer asks for your Mac password once for every key you have saved: only a key you actually changed is written to the Keychain.

## 1.6

- The update prompt now says what the new version changes.
- Sci-Hub mirrors reorder themselves when one stops working.

## 1.5

- API keys are kept in the macOS Keychain instead of a settings file.
- Settings shows what the AI has cost this month, and can stop it at a monthly limit you set.

## 1.4

- The menu bar item is part of MedSearch now: one app to install and update, instead of two.
- Closing the window leaves MedSearch in the menu bar; Settings can start it at login.
- A new icon, and the whole interface brought into one style.
- AI answers are shown as proper headings and lists instead of raw Markdown.
- Errors always arrive as a dialog, never a note that scrolls past.
