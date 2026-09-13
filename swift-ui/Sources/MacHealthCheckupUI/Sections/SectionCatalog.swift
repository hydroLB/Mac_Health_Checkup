import Foundation
import MacHealthCheckupCore

public struct SectionDescriptor: Sendable, Identifiable {
    public var id: String { key }
    public let title: String
    public let subtitle: String
    public let key: String

    public init(title: String, subtitle: String, key: String) {
        /**
         Summary
         Initialize a section descriptor from backend-provided catalog metadata.

         Inputs
         title: User-facing section title.
         subtitle: User-facing section subtitle.
         key: Stable section identifier.

         Outputs
         A section descriptor suitable for dashboard navigation.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SectionCatalog.fromConfig` and the iOS client when mapping a remote snapshot catalog.

         Why this exists
         The iOS app consumes `MacHealthCheckupUI` as a separate module and cannot access a synthesized internal initializer.
         */
        self.title = title
        self.subtitle = subtitle
        self.key = key
    }
}

public enum SectionCatalog {
    /**
     Summary
     Build a deterministic section list from config `gui.section_rows`.

     Inputs
     None.

     Outputs
     Section descriptors for navigation and rendering.

     Side effects
     None.

     Error handling
     Throws `AppError` when section rows are malformed.

     Ties to other methods
     Used by `DashboardViewModel` and `SidebarView`.

     Why this exists
     Keeps the SwiftUI frontend aligned with the Python UI section ordering.
     */

    public static func fromConfig(_ config: AppConfig) throws -> [SectionDescriptor] {
        /**
         Summary
         Convert raw `section_rows` arrays into typed section descriptors.

         Inputs
         config: Validated `AppConfig`.

         Outputs
         Ordered section descriptors.

         Side effects
         None.

         Error handling
         Throws `AppError` when rows do not contain exactly 3 items.

         Ties to other methods
         Used during app bootstrap to build navigation.

         Why this exists
         Keeps section parsing strict so the UI fails fast when config is invalid.
         */
        var out: [SectionDescriptor] = []
        for row in config.gui.section_rows {
            if row.count != 3 {
                throw AppError.context(#fileID, #function, "gui.section_rows must contain 3-item rows")
            }
            out.append(SectionDescriptor(title: row[0], subtitle: row[1], key: row[2]))
        }
        return out
    }
}
