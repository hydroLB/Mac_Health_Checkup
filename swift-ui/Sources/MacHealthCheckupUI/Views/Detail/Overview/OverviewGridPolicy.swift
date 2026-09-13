import CoreGraphics

enum OverviewGridPolicy {
    static let maximumColumns = 3
    static let minimumCardWidth: CGFloat = 340

    static func columnCount(
        for availableWidth: CGFloat,
        spacing: CGFloat,
        minimumWidth: CGFloat = minimumCardWidth
    ) -> Int {
        let safeWidth = max(0, availableWidth)
        let safeSpacing = max(0, spacing)
        let safeMinimum = max(1, minimumWidth)
        let fittingColumns = Int((safeWidth + safeSpacing) / (safeMinimum + safeSpacing))
        return min(maximumColumns, max(1, fittingColumns))
    }

    static func isAlert(for health: SectionHealth) -> Bool {
        health == .warn || health == .bad
    }

    static func priority(for health: SectionHealth) -> Int {
        switch health {
        case .bad:
            return 0
        case .warn:
            return 1
        case .unknown:
            return 2
        case .ok:
            return 3
        }
    }
}
