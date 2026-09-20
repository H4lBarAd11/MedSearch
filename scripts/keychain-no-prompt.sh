#!/bin/bash
# MedSearch — stop the Keychain asking for your password on every read.
#
#     bash scripts/keychain-no-prompt.sh
#
# WHY IT IS NEEDED. MedSearch stores its API keys as Keychain items that only
# Apple's own keychain tool may read (that is the `-T /usr/bin/security` in
# secrets_store.py). Since macOS Sierra an item also carries a "partition list",
# and until that list names the tool, every read raises the "…wants to use your
# confidential information stored in your keychain" dialog — which accepts the
# login password only; it does not offer Touch ID.
#
# WHAT IT DOES. Adds Apple's tools to the partition list of MedSearch's items,
# and nothing else: other applications are still refused, and every other item
# in your keychain is untouched. macOS requires your login password to change a
# partition list, so it is asked for once here, read without echo, and passed
# only to /usr/bin/security.
#
# RUN IT AGAIN after entering a NEW key in Settings: a newly created item starts
# with an empty partition list again.
set -u

SERVICE="MedSearch"
ACCOUNTS=(anthropic_api_key pubmed_api_key scopus_api_key scopus_insttoken wos_api_key)

if [ "$(uname)" != "Darwin" ]; then
  echo "  This is a macOS script (there is no Keychain elsewhere)."
  exit 1
fi

printf "  Login password for the keychain (not shown): "
read -rs PASSWORD
printf "\n\n"

changed=0 skipped=0 failed=0
for account in "${ACCOUNTS[@]}"; do
  if ! /usr/bin/security find-generic-password -s "$SERVICE" -a "$account" >/dev/null 2>&1; then
    skipped=$((skipped + 1))
    continue
  fi
  if /usr/bin/security set-generic-password-partition-list \
       -S apple-tool:,apple: -s "$SERVICE" -a "$account" -k "$PASSWORD" >/dev/null 2>&1; then
    echo "  ✓ $account"
    changed=$((changed + 1))
  else
    echo "  ✗ $account — not changed (wrong password?)"
    failed=$((failed + 1))
  fi
done
unset PASSWORD

echo ""
echo "  $changed updated, $skipped not stored, $failed failed."
[ "$failed" -eq 0 ] || exit 1
echo "  MedSearch can now read its keys without asking. Run this again after"
echo "  saving a new key in Settings."
