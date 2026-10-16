# Security policy

## Reporting a vulnerability

Please don't report a security problem in a public issue. Report it privately through
GitHub: open the repository's **Security** tab and choose **Report a vulnerability**
([direct link](https://github.com/H4lBarAd11/MedSearch/security/advisories/new)). Only the
maintainer sees it, and the conversation stays private until a fix is released.

Say what can be done, how, and with which version of MedSearch. Steps or a small example
that shows it help most.

## Supported versions

Fixes go into the latest release, which installed copies offer by themselves. Older
versions are not patched: update to the latest.

## What it covers

MedSearch runs on your own computer. What matters most:

- its local server, which answers only MedSearch's own window: every request carries a
  token chosen afresh at each start;
- the API keys and library sign-ins it keeps in the Keychain (on Windows, Credential
  Manager), and the pages it fills those sign-ins in on;
- its updates, which come from this repository's Releases, and Uninstall.

A problem in one of the literature services MedSearch searches belongs to that service.

## What to expect

MedSearch is a personal project, maintained in spare time. A report is answered as soon as
possible, and a confirmed problem is fixed in a new release, credited to the reporter if
they wish.
