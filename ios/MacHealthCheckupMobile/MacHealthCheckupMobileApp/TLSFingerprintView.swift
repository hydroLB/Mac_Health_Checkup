import MacHealthCheckupCore
import SwiftUI
import UIKit

struct TLSFingerprintView: View {
    /**
     Summary
     Render an input field for an optional TLS certificate pin with inline validation.

     Inputs
     tlsPin: Binding to the stored fingerprint string.

     Outputs
     A SwiftUI view with a text field and validation status.

     Side effects
     Reads the system clipboard when the user taps Paste.

     Error handling
     Displays validation state instead of throwing.

     Ties to other methods
     Uses `CertificatePinning.normalizedSHA256Fingerprint` for deterministic validation.

     Why this exists
     Certificate pinning prevents token sniffing on untrusted LANs when using HTTPS with a self-signed cert.
     */

    @Binding var tlsPin: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("TLS certificate pin (sha256, optional)", text: $tlsPin)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .font(.footnote.monospaced())

            HStack(spacing: 10) {
                Button {
                    _paste()
                } label: {
                    Label("Paste", systemImage: "doc.on.clipboard")
                }

                Text(_statusText)
                    .font(.footnote)
                    .foregroundStyle(_statusColor)

                Spacer()
            }

            Text("Use this when your Mac agent runs HTTPS with a self-signed cert. Paste the fingerprint printed by `--serve`.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private var _statusText: String {
        /**
         Summary
         Derive a compact validation status string for the current pin value.

         Inputs
         None.

         Outputs
         Status string.

         Side effects
         None.

         Error handling
         Returns an "Invalid" status instead of throwing.

         Ties to other methods
         Uses `CertificatePinning.normalizedSHA256Fingerprint`.

         Why this exists
         Inline validation keeps settings harder to misuse without requiring trial-and-error network requests.
         */
        let trimmed = tlsPin.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return "Not set"
        }
        if (try? CertificatePinning.normalizedSHA256Fingerprint(trimmed)) != nil {
            return "Valid"
        }
        return "Invalid"
    }

    private var _statusColor: Color {
        /**
         Summary
         Choose a color for the validation status.

         Inputs
         None.

         Outputs
         Color value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Based on `_statusText`.

         Why this exists
         Provides immediate visual feedback for a more native, polished settings experience.
         */
        switch _statusText {
        case "Valid":
            return .green
        case "Invalid":
            return .red
        default:
            return .secondary
        }
    }

    private func _paste() {
        /**
         Summary
         Paste clipboard contents into the pin field.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Reads from `UIPasteboard` and updates the bound value.

         Error handling
         No-ops when the clipboard does not contain a string.

         Ties to other methods
         Used by the Paste button.

         Why this exists
         Reduces friction when users copy the fingerprint from the Mac terminal output.
         */
        if let value = UIPasteboard.general.string {
            tlsPin = value
        }
    }
}

