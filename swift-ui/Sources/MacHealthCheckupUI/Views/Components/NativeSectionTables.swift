import SwiftUI
import MacHealthCheckupCore

struct DisplayListTableView: View {
    /**
     Summary
     Render the Display section table as a native Settings-style list.

     Inputs
     theme: Theme for consistent colors and typography.
     table: Snapshot table for the display section.

     Outputs
     A SwiftUI view optimized for display rows.

     Side effects
     None.

     Error handling
     None. Missing cells are rendered as placeholders.

     Ties to other methods
     Used by `DetailView` when rendering the "display" section.

     Why this exists
     A grid is difficult to scan for display inventories; a list with a primary label and compact secondary details reads like a native iOS settings screen.
     */

    let theme: Theme
    let table: SnapshotTable

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(table.rows.enumerated()), id: \.offset) { index, row in
                let name = _cell(row, 0).ifEmpty("Display")
                let resolution = _cell(row, 1)
                let connection = _cell(row, 3)
                let refresh = _cell(row, 4)
                let transport = _cell(row, 5)
                let details = [resolution, refresh, connection, transport]
                    .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                    .filter { !$0.isEmpty && $0 != "?" }
                    .joined(separator: "  •  ")

                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Image(systemName: "display")
                        .foregroundStyle(theme.colors.label)
                        .frame(width: 18)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(name)
                            .font(theme.fonts.body)
                            .foregroundStyle(theme.colors.field)
                            .lineLimit(1)
                        if !details.isEmpty {
                            Text(details)
                                .font(theme.fonts.caption)
                                .foregroundStyle(theme.colors.label)
                                .lineLimit(2)
                        }
                    }
                    Spacer()
                }
                .help("\(HelpText.section(key: "display"))\n\nName: \(name)\nDetails: \(details.isEmpty ? "(none)" : details)")
                .padding(.vertical, theme.layout.verticalScaled(7))

                if index < table.rows.count - 1 {
                    Divider()
                        .opacity(0.6)
                }
            }
        }
        .textSelection(.enabled)
    }
}

struct InputDevicesListTableView: View {
    /**
     Summary
     Render the Input section as a clean, iOS Settings-style list.

     Inputs
     theme: Theme for consistent colors and typography.
     table: Snapshot table for the input section.

     Outputs
     A SwiftUI view optimized for input device rows.

     Side effects
     None.

     Error handling
     None. Missing cells are rendered as placeholders.

     Ties to other methods
     Used by `DetailView` when rendering the "input" section.

     Why this exists
     Input devices are easier to scan as a list of concise rows than a grid, and this section should feel like a native Settings screen.
     */

    let theme: Theme
    let table: SnapshotTable

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(table.rows.enumerated()), id: \.offset) { index, row in
                let kind = _cell(row, 0).ifEmpty("Device")
                let device = _cell(row, 1).ifEmpty("Unknown")
                let transport = _cell(row, 2)

                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Image(systemName: _iconName(kind: kind, device: device))
                        .foregroundStyle(theme.colors.label)
                        .frame(width: 18)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(device)
                            .font(theme.fonts.body)
                            .foregroundStyle(theme.colors.field)
                            .lineLimit(1)
                        Text(kind)
                            .font(theme.fonts.caption)
                            .foregroundStyle(theme.colors.label)
                            .lineLimit(1)
                    }
                    Spacer()
                    if !transport.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, transport != "?" {
                        Text(transport)
                            .font(theme.fonts.mono)
                            .foregroundStyle(theme.colors.field.opacity(0.9))
                            .lineLimit(1)
                    }
                }
                .help("\(HelpText.section(key: "input"))\n\nDevice: \(device)\nType: \(kind)\nTransport: \(transport.isEmpty ? "(unknown)" : transport)")
                .padding(.vertical, theme.layout.verticalScaled(7))

                if index < table.rows.count - 1 {
                    Divider()
                        .opacity(0.6)
                }
            }
        }
        .textSelection(.enabled)
    }

    private func _iconName(kind: String, device: String) -> String {
        let k = kind.lowercased()
        let d = device.lowercased()
        if k.contains("backlight") || d.contains("backlight") { return "light.max" }
        if k.contains("keyboard") || d.contains("keyboard") { return "keyboard" }
        if k.contains("trackpad") || d.contains("trackpad") { return "rectangle.and.hand.point.up.left" }
        if k.contains("mouse") || d.contains("mouse") { return "computermouse" }
        if k.contains("game") || d.contains("controller") { return "gamecontroller" }
        return "dot.circle"
    }
}

struct DevicesListTableView: View {
    /**
     Summary
     Render the Devices section as a native Settings-style list grouped by bus.

     Inputs
     theme: Theme for consistent colors and typography.
     table: Snapshot table for the devices section.

     Outputs
     A SwiftUI view optimized for grouped device rows.

     Side effects
     None.

     Error handling
     None. Missing cells are rendered as placeholders.

     Ties to other methods
     Used by `DetailView` when rendering the "devices" section.

     Why this exists
     A flat grid is hard to scan and feels non-native; grouping by bus matches iOS Settings patterns and makes the section feel intentional.
     */

    let theme: Theme
    let table: SnapshotTable

    var body: some View {
        let grouped = _groupRowsByBus(rows: table.rows)
        let buses = Array(grouped.keys)
            .sorted(by: _busSortKey)
            .filter { bus in
                let rows = grouped[bus] ?? []
                return !rows.isEmpty
            }
        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(12)) {
            ForEach(buses, id: \.self) { bus in
                let rows = grouped[bus] ?? []
                VStack(alignment: .leading, spacing: 0) {
                    HStack(spacing: 8) {
                        Image(systemName: _busIcon(bus: bus))
                            .foregroundStyle(theme.colors.label)
                            .frame(width: 18)
                        Text(bus)
                            .font(theme.fonts.caption)
                            .foregroundStyle(theme.colors.label)
                        Spacer()
                    }
                    .padding(.bottom, theme.layout.verticalScaled(6))

                    ForEach(Array(rows.enumerated()), id: \.offset) { index, device in
                        HStack(alignment: .firstTextBaseline, spacing: 12) {
                            Image(systemName: _deviceIcon(device: device))
                                .foregroundStyle(theme.colors.label.opacity(0.9))
                                .frame(width: 18)
                            Text(device)
                                .font(theme.fonts.body)
                                .foregroundStyle(theme.colors.field)
                                .lineLimit(2)
                            Spacer()
                        }
                        .help("\(HelpText.section(key: "devices"))\n\nBus: \(bus)\nDevice: \(device)")
                        .padding(.vertical, theme.layout.verticalScaled(7))
                        if index < rows.count - 1 {
                            Divider().opacity(0.6)
                        }
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, theme.layout.verticalScaled(10))
                .background(theme.colors.background.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .textSelection(.enabled)
    }

    private func _groupRowsByBus(rows: [[String]]) -> [String: [String]] {
        var grouped: [String: [String]] = [:]
        for row in rows {
            let bus = _cell(row, 0).ifEmpty("Other")
            let device = _cell(row, 1).ifEmpty("Unknown")
            grouped[bus, default: []].append(device)
        }
        return grouped
    }

    private func _busSortKey(lhs: String, rhs: String) -> Bool {
        let order = ["USB", "Thunderbolt", "Bluetooth", "Network", "Other"]
        let l = order.firstIndex(of: lhs) ?? order.count
        let r = order.firstIndex(of: rhs) ?? order.count
        if l != r { return l < r }
        return lhs.localizedCaseInsensitiveCompare(rhs) == .orderedAscending
    }

    private func _busIcon(bus: String) -> String {
        switch bus.lowercased() {
        case "usb":
            return "cable.connector"
        case "thunderbolt":
            return "bolt.circle"
        case "bluetooth":
            return "bolt.horizontal"
        case "network":
            return "network"
        default:
            return "dot.circle"
        }
    }

    private func _deviceIcon(device: String) -> String {
        let text = device.lowercased()
        if text.contains("keyboard") { return "keyboard" }
        if text.contains("mouse") { return "computermouse" }
        if text.contains("trackpad") { return "rectangle.and.hand.point.up.left" }
        if text.contains("lan") || text.contains("ethernet") { return "network" }
        if text.contains("controller") || text.contains("gamepad") { return "gamecontroller" }
        return "puzzlepiece.extension"
    }
}

struct IndentedTreeTableView: View {
    /**
     Summary
     Render a single-column table that encodes hierarchy via leading spaces as a nested tree.

     Inputs
     theme: Theme for consistent colors and typography.
     title: Optional title for the tree root.
     rows: Table rows where the first column contains an indented label.

     Outputs
     A SwiftUI view with DisclosureGroups for nesting.

     Side effects
     None.

     Error handling
     Treats malformed indentation as flat rows.

     Ties to other methods
     Used by `DetailView` for the USB Ports section.

     Why this exists
     USB trees should behave like iOS Settings: expandable, nested, and easy to scan.
     */

    final class Node: Identifiable {
        /**
         Summary
         Represent a single tree node with a label and optional children.

         Inputs
         id: Stable identifier.
         label: Row label.
         children: Child nodes.

         Outputs
         Node value suitable for SwiftUI tree rendering.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Built by `buildTree(rows:)` and rendered recursively.

         Why this exists
         Outline-style rendering requires an explicit tree structure.
         */
        let id: String
        let label: String
        var children: [Node]

        init(id: String, label: String, children: [Node] = []) {
            /**
             Summary
             Initialize a tree node.

             Inputs
             id: Stable identifier.
             label: Row label.
             children: Optional child nodes.

             Outputs
             A Node instance.

             Side effects
             None.

             Error handling
             None.

             Ties to other methods
             Used by `buildTree(rows:)`.

             Why this exists
             Reference semantics simplify incremental tree construction from indented rows.
             */
            self.id = id
            self.label = label
            self.children = children
        }
    }

    let theme: Theme
    let title: String?
    let rows: [[String]]
    @State private var expandedNodeIds: Set<String> = []
    @State private var didInitializeExpansion: Bool = false

    var body: some View {
        let nodes = buildTree(rows: rows)
        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(6)) {
            if let title, !title.isEmpty {
                Text(title)
                    .font(theme.fonts.caption)
                    .foregroundStyle(theme.colors.label)
                    .help(HelpText.section(key: "ports"))
            }
            TreeNodesView(theme: theme, nodes: nodes, expandedNodeIds: $expandedNodeIds)
        }
        .textSelection(.enabled)
        .onAppear {
            if didInitializeExpansion { return }
            didInitializeExpansion = true
            expandedNodeIds = _collectExpandableNodeIds(nodes: nodes)
        }
    }

    private func buildTree(rows: [[String]]) -> [Node] {
        /**
         Summary
         Build a tree from rows where indentation encodes depth.

         Inputs
         rows: Table rows; first cell is the label with leading spaces.

         Outputs
         Root nodes for rendering.

         Side effects
         None.

         Error handling
         Returns a flat list when indentation is inconsistent.

         Ties to other methods
         Used by `body` before rendering.

         Why this exists
         The backend emits a single-column indented USB tree; the UI should still render it as a native hierarchy.
         */
        var roots: [Node] = []
        var stack: [Node] = []

        for (index, row) in rows.enumerated() {
            let rawLabel = row.first ?? ""
            let leading = rawLabel.prefix { $0 == " " }.count
            let depth = max(0, leading / 2)
            let label = rawLabel.trimmingCharacters(in: .whitespacesAndNewlines)
            if label.isEmpty { continue }
            let id = "\(depth)|\(index)|\(label)"
            let node = Node(id: id, label: label)

            while stack.count > depth {
                stack.removeLast()
            }
            if let parent = stack.last {
                parent.children.append(node)
            } else {
                roots.append(node)
            }
            stack.append(node)
        }
        return roots
    }

    private func _collectExpandableNodeIds(nodes: [Node]) -> Set<String> {
        /**
         Summary
         Collect the ids of nodes that should be expanded by default.

         Inputs
         nodes: Root nodes of the tree.

         Outputs
         Set of node ids that have children.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `body` to default-expand the Ports tree.

         Why this exists
         The Ports section is most useful when fully unfolded at rest so users can scan the whole topology quickly.
         */
        var out: Set<String> = []
        var stack: [Node] = nodes
        while let node = stack.popLast() {
            if !node.children.isEmpty {
                out.insert(node.id)
                stack.append(contentsOf: node.children)
            }
        }
        return out
    }

    private struct TreeNodesView: View {
        let theme: Theme
        let nodes: [Node]
        @Binding var expandedNodeIds: Set<String>

        var body: some View {
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(nodes.enumerated()), id: \.element.id) { index, node in
                    if node.children.isEmpty {
                        _TreeRow(theme: theme, label: node.label, isGroup: false)
                    } else {
                        let isExpanded = Binding(
                            get: { expandedNodeIds.contains(node.id) },
                            set: { newValue in
                                if newValue {
                                    expandedNodeIds.insert(node.id)
                                } else {
                                    expandedNodeIds.remove(node.id)
                                }
                            }
                        )
                        DisclosureGroup(isExpanded: isExpanded) {
                            TreeNodesView(theme: theme, nodes: node.children, expandedNodeIds: $expandedNodeIds)
                                .padding(.leading, 18)
                        } label: {
                            _TreeRow(theme: theme, label: node.label, isGroup: true)
                        }
                        .foregroundStyle(theme.colors.field)
                    }
                    if index < nodes.count - 1 {
                        Divider().opacity(0.5)
                    }
                }
            }
        }

        private struct _TreeRow: View {
            let theme: Theme
            let label: String
            let isGroup: Bool

            var body: some View {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Image(systemName: _iconName(for: label))
                        .foregroundStyle(theme.colors.label)
                        .frame(width: 18)
                    Text(label)
                        .font(isGroup ? theme.fonts.body.weight(.semibold) : theme.fonts.body)
                        .foregroundStyle(theme.colors.field)
                        .lineLimit(2)
                    Spacer()
                }
                .help("\(HelpText.section(key: "ports"))\n\nUSB node: \(label)")
                .padding(.vertical, theme.layout.verticalScaled(7))
            }

            private func _iconName(for label: String) -> String {
                let lower = label.lowercased()
                if lower.contains("display alt mode") { return "display" }
                if lower.contains("(display") { return "display" }
                if lower.contains("usb") || lower.contains("hub") { return "usb" }
                if lower.contains("billboard") { return "rectangle.on.rectangle" }
                if lower.contains("receiver") { return "dot.radiowaves.left.and.right" }
                if lower.contains("keyboard") { return "keyboard" }
                if lower.contains("mouse") { return "computermouse" }
                return "circle.fill"
            }
        }
    }
}

private func _cell(_ row: [String], _ index: Int) -> String {
    if row.indices.contains(index) {
        return row[index]
    }
    return ""
}

private extension String {
    func ifEmpty(_ fallback: String) -> String {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? fallback : trimmed
    }
}
