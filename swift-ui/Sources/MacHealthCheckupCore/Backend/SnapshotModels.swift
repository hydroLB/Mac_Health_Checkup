import Foundation

public struct Snapshot: Codable, Sendable {
    /**
     Summary
     Decode the JSON snapshot payload emitted by `python -m mac_health_checkup --snapshot-json`.

     Inputs
     schema_version: Snapshot schema version.
     generated_at_unix_ms: Generation timestamp in milliseconds.
     theme: Theme payload derived from central config.
     section_catalog: Section ordering and labels from config.
     sections: Per-section render payloads.
     ok: Whether the snapshot succeeded.
     error: Optional top-level error message.

     Outputs
     Decoded snapshot suitable for SwiftUI rendering.

     Side effects
     None.

     Error handling
     Validation errors are thrown by `validated()`.

     Ties to other methods
     Produced by snapshot backend clients.

     Why this exists
     Keeps the SwiftUI frontend strictly typed and resilient to schema drift.
     */

    public let schema_version: Int
    public let generated_at_unix_ms: Int
    public let theme: SnapshotTheme
    public let section_catalog: [SnapshotSectionDescriptor]
    public let sections: [SnapshotSection]
    public let ok: Bool
    public let error: String?

    public func validated() throws -> Snapshot {
        /**
         Summary
         Validate the decoded snapshot payload for expected shape.

         Inputs
         None.

         Outputs
         The same `Snapshot` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when schema version is unsupported.

         Ties to other methods
         Called by the backend client before publishing data to the UI.

         Why this exists
         Prevents rendering crashes by catching unexpected payload shapes early.
         */
        if schema_version != 2 {
            throw AppError.context(#fileID, #function, "Unsupported snapshot schema_version=\(schema_version)")
        }
        return self
    }
}

public struct SnapshotTheme: Codable, Sendable {
    public let ui: SnapshotThemeUI
    public let colors: SnapshotThemeColors
    public let fonts: SnapshotThemeFonts
    public let gui: SnapshotThemeGui
}

public struct SnapshotThemeUI: Codable, Sendable {
    public let window_title: String
}

public struct SnapshotThemeColors: Codable, Sendable {
    public let bg: String
    public let fg: String
    public let ok: String
    public let warn: String
    public let bad: String
    public let section: String
    public let label: String
    public let field: String
}

public struct SnapshotThemeFonts: Codable, Sendable {
    public let family_default: String
    public let family_mono: String
    public let size_section: Int
    public let size_banner: Int
    public let size_field: Int
    public let size_tooltip: Int
}

public struct SnapshotThemeGui: Codable, Sendable {
    public let card_bg: String
    public let card_border: String
    public let section_padx: Int
    public let section_pady: Int
    public let auto_refresh_ms: Int
    public let scrollable_rows: [String: Int]
}

public struct SnapshotSectionDescriptor: Codable, Sendable, Identifiable {
    public var id: String { key }
    public let title: String
    public let subtitle: String
    public let key: String
}

public struct SnapshotSection: Codable, Sendable, Identifiable {
    public var id: String { key }

    public let key: String
    public let field: String?
    public let metrics: [MetricsRow]?
    public let table: SnapshotTable?
    public let diagnostics: [String: JSONValue]?
}

public struct MetricsRow: Codable, Sendable {
    public let label: String
    public let value: String
    public let status: String

    public init(from decoder: any Decoder) throws {
        /**
         Summary
         Decode a metrics row from a fixed-size JSON array.

         Inputs
         decoder: Decoder for the metrics row.

         Outputs
         A decoded `MetricsRow`.

         Side effects
         None.

         Error handling
         Throws decoding errors for malformed rows.

         Ties to other methods
         Used by `SnapshotSection.metrics`.

         Why this exists
         The backend encodes rows as arrays to keep the JSON compact.
         */
        var container = try decoder.unkeyedContainer()
        label = try container.decode(String.self)
        value = try container.decode(String.self)
        status = try container.decode(String.self)
    }

    public func encode(to encoder: any Encoder) throws {
        /**
         Summary
         Encode a metrics row using the backend's fixed-size JSON array shape.

         Inputs
         encoder: Encoder receiving the metrics row.

         Outputs
         None.

         Side effects
         Writes the label, value, and status to the encoder in schema order.

         Error handling
         Propagates encoding errors.

         Ties to other methods
         Keeps snapshot cache output compatible with `init(from:)` and the Python snapshot schema.

         Why this exists
         Synthesized keyed encoding would not round-trip through the custom unkeyed decoder.
         */
        var container = encoder.unkeyedContainer()
        try container.encode(label)
        try container.encode(value)
        try container.encode(status)
    }
}

public struct SnapshotTable: Codable, Sendable {
    public let headers: [String]
    public let rows: [[String]]
}

public enum JSONValue: Codable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    public init(from decoder: any Decoder) throws {
        /**
         Summary
         Decode an arbitrary JSON value into a strongly typed enum.

         Inputs
         decoder: Decoder for the value.

         Outputs
         A decoded `JSONValue`.

         Side effects
         None.

         Error handling
         Throws decoding errors when no JSON representation matches.

         Ties to other methods
         Used to retain diagnostics payloads without losing types.

         Why this exists
         Keeps debug payloads available for UI error screens without resorting to untyped `Any`.
         */
        if let container = try? decoder.singleValueContainer() {
            if container.decodeNil() {
                self = .null
                return
            }
            if let value = try? container.decode(Bool.self) {
                self = .bool(value)
                return
            }
            if let value = try? container.decode(Double.self) {
                self = .number(value)
                return
            }
            if let value = try? container.decode(String.self) {
                self = .string(value)
                return
            }
        }
        if var unkeyed = try? decoder.unkeyedContainer() {
            var values: [JSONValue] = []
            while !unkeyed.isAtEnd {
                values.append(try unkeyed.decode(JSONValue.self))
            }
            self = .array(values)
            return
        }
        if let keyed = try? decoder.container(keyedBy: DynamicCodingKey.self) {
            var dict: [String: JSONValue] = [:]
            for key in keyed.allKeys {
                dict[key.stringValue] = try keyed.decode(JSONValue.self, forKey: key)
            }
            self = .object(dict)
            return
        }
        throw AppError.context(#fileID, #function, "Unsupported JSON value")
    }

    public func encode(to encoder: any Encoder) throws {
        /**
         Summary
         Encode an arbitrary JSON value without losing its original JSON shape.

         Inputs
         encoder: Encoder receiving the JSON value.

         Outputs
         None.

         Side effects
         Writes one JSON-compatible value to the encoder.

         Error handling
         Propagates encoding failures from nested values.

         Ties to other methods
         Enables complete snapshot payloads, including diagnostics, to be persisted and decoded from cache.

         Why this exists
         The enum needs an explicit encoder so its associated values remain raw JSON rather than enum case wrappers.
         */
        switch self {
        case let .string(value):
            var container = encoder.singleValueContainer()
            try container.encode(value)
        case let .number(value):
            var container = encoder.singleValueContainer()
            try container.encode(value)
        case let .bool(value):
            var container = encoder.singleValueContainer()
            try container.encode(value)
        case let .object(value):
            var container = encoder.singleValueContainer()
            try container.encode(value)
        case let .array(value):
            var container = encoder.singleValueContainer()
            try container.encode(value)
        case .null:
            var container = encoder.singleValueContainer()
            try container.encodeNil()
        }
    }
}

private struct DynamicCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        self.intValue = nil
    }

    init?(intValue: Int) {
        self.stringValue = "\(intValue)"
        self.intValue = intValue
    }
}
