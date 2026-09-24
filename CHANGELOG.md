# What changed

The newest version first. MedSearch shows the entry for a new version in the
update prompt, so this file is what a user reads before choosing to update:
one line per change, in plain words, no internals.

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
