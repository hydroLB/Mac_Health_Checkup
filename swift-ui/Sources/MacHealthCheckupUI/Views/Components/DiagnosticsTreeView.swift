import SwiftUI
import MacHealthCheckupCore

public struct DiagnosticsTreeView: View {
    /**
     Summary
     Render nested diagnostics as an expandable tree rather than a flat key/count list.
     
     Inputs
     theme: Theme for typography and colors.
     diagnostics: Root diagnostics dictionary.
     
     Outputs
     SwiftUI view that supports expanding objects and arrays.
     
     Side effects
     None.
     
     Error handling
     None.
     
     Ties to other methods
     Used by section detail views when rendering snapshot diagnostics.
     
     Why this exists
     Native UI users need access to underlying diagnostic values to understand why collectors return "unknown".
     */

    public let theme: Theme
    public let diagnostics: [String: JSONValue]

    public init(theme: Theme, diagnostics: [String: JSONValue]) {
        /**
         Summary
         Initialize the tree view.
         
         Inputs
         theme: Theme value.
         diagnostics: Root diagnostics dictionary.
         
         Outputs
         None.
         
         Side effects
         None.
         
         Error handling
         None.
         
         Ties to other methods
         Consumed by section detail views.
         
         Why this exists
         Keeps diagnostics rendering reusable and consistent.
         */
        self.theme = theme
        self.diagnostics = diagnostics
    }

    public var body: some View {
        /**
         Summary
         Render the full diagnostics tree.
         
         Inputs
         None.
         
         Outputs
         SwiftUI view.
         
         Side effects
         None.
         
         Error handling
         None.
         
         Ties to other methods
         Uses `NodeView` for recursive rendering.
         
         Why this exists
         Provides a predictable, readable nested view with minimal clutter.
         */
        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(6)) {
            ForEach(diagnostics.keys.sorted(), id: \.self) { key in
                NodeView(theme: theme, name: key, value: diagnostics[key] ?? .null, depth: 0)
            }
        }
        .textSelection(.enabled)
    }
}

private struct NodeView: View {
    let theme: Theme
    let name: String
    let value: JSONValue
    let depth: Int

    @State private var isExpanded: Bool = false

    var body: some View {
        /**
         Summary
         Render a single node and recursively render children when expanded.
         
         Inputs
         None.
         
         Outputs
         SwiftUI view.
         
         Side effects
         None.
         
         Error handling
         None.
         
         Ties to other methods
         Used recursively by `DiagnosticsTreeView`.
         
         Why this exists
         Avoids dumping huge JSON blobs while still making values accessible when needed.
         */
        switch value {
        case .string(let s) where s.count > 280 || s.contains("\n"):
            DisclosureGroup(isExpanded: $isExpanded) {
                ScrollView([.horizontal, .vertical]) {
                    Text(s)
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.field)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .padding(.top, theme.layout.verticalScaled(4))
                }
                .frame(maxHeight: 260)
            } label: {
                HStack(alignment: .top) {
                    Text(name)
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.label)
                        .frame(width: 160, alignment: .leading)
                    Text("Text (\(s.count) chars)")
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.field)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        case .object(let obj):
            DisclosureGroup(isExpanded: $isExpanded) {
                VStack(alignment: .leading, spacing: theme.layout.verticalScaled(6)) {
                    ForEach(obj.keys.sorted(), id: \.self) { childKey in
                        NodeView(theme: theme, name: childKey, value: obj[childKey] ?? .null, depth: depth + 1)
                    }
                }
                .padding(.leading, 14)
                .padding(.top, theme.layout.verticalScaled(4))
            } label: {
                HStack(alignment: .top) {
                    Text(name)
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.label)
                        .frame(width: 160, alignment: .leading)
                    Text("{\(obj.count) keys}")
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.field)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        case .array(let arr):
            DisclosureGroup(isExpanded: $isExpanded) {
                VStack(alignment: .leading, spacing: theme.layout.verticalScaled(6)) {
                    ForEach(Array(arr.enumerated()), id: \.offset) { idx, item in
                        NodeView(theme: theme, name: "[\(idx)]", value: item, depth: depth + 1)
                    }
                }
                .padding(.leading, 14)
                .padding(.top, theme.layout.verticalScaled(4))
            } label: {
                HStack(alignment: .top) {
                    Text(name)
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.label)
                        .frame(width: 160, alignment: .leading)
                    Text("[\(arr.count) items]")
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.field)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        default:
            HStack(alignment: .top) {
                Text(name)
                    .font(theme.fonts.mono)
                    .foregroundStyle(theme.colors.label)
                    .frame(width: 160, alignment: .leading)
                Text(renderScalar(value))
                    .font(theme.fonts.mono)
                    .foregroundStyle(theme.colors.field)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private func renderScalar(_ value: JSONValue) -> String {
        /**
         Summary
         Render a scalar JSON value into a readable string.
         
         Inputs
         value: JSON value.
         
         Outputs
         String representation.
         
         Side effects
         None.
         
         Error handling
         None.
         
         Ties to other methods
         Used by `NodeView.body` for leaf values.
         
         Why this exists
         Keeps scalar rendering consistent and avoids Swift default formatting surprises.
         */
        switch value {
        case .string(let s):
            return s
        case .number(let n):
            return String(n)
        case .bool(let b):
            return b ? "true" : "false"
        case .null:
            return "null"
        case .array:
            return "[…]"
        case .object:
            return "{…}"
        }
    }
}
