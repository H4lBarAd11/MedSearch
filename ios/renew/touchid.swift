// MedSearch for iOS — the automatic renewal's confirmation (renew.sh): Touch ID,
// or the Mac's password where Touch ID is not available or fails.
// Exit 0: confirmed; 1: not.   touchid "the reason shown in the dialog"
import Foundation
import LocalAuthentication

let reason = CommandLine.arguments.count > 1 ? CommandLine.arguments[1]
                                              : "renew the signing of your apps"
let context = LAContext()
context.localizedFallbackTitle = "Use Password"
var error: NSError?
// Touch ID first; the password only when there is no Touch ID to use.
let policy: LAPolicy = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
    ? .deviceOwnerAuthenticationWithBiometrics : .deviceOwnerAuthentication
let done = DispatchSemaphore(value: 0)
var confirmed = false
context.evaluatePolicy(policy, localizedReason: reason) { ok, _ in
    confirmed = ok
    done.signal()
}
// The dialog waits for the person; give up after ten minutes.
if done.wait(timeout: .now() + 600) == .timedOut { exit(1) }
exit(confirmed ? 0 : 1)
