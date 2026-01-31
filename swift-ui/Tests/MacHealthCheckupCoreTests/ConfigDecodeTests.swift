import XCTest
@testable import MacHealthCheckupCore

final class ConfigDecodeTests: XCTestCase {
    func testDecodeAndValidateConfig() throws {
        /**
         Summary
         Ensure the Swift config model decodes and validates expected fields.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when decoding or validation fails.

         Ties to other methods
         Uses `AppConfig.validated`.

         Why this exists
         Protects the frontend from config schema drift.
         */
        let json = """
        {
          "colors": {
            "bg": "#000000",
            "fg": "#ffffff",
            "ok": "#00ff00",
            "warn": "#ffff00",
            "bad": "#ff0000",
            "section": "#339af0",
            "label": "#f1c40f",
            "field": "#daf6ff"
          },
          "fonts": {
            "family_default": "Helvetica",
            "family_mono": "Menlo",
            "size_section": 16,
            "size_banner": 18,
            "size_field": 13,
            "size_tooltip": 10,
            "weight_bold": "bold",
            "weight_normal": "normal"
          },
          "ui": { "window_size": "820x1180", "window_title": "Mac Health Checkup" },
          "gui": {
            "section_rows": [["A","B","a"]],
            "scrollable_rows": {},
            "card_bg": "#111111",
            "card_border": "#222222",
            "section_padx": 8,
            "section_pady": 8,
            "auto_refresh_ms": 1000
          },
          "timeouts": { "default_cmd_timeout": 10 }
        }
        """
        let data = Data(json.utf8)
        let config = try JSONDecoder().decode(AppConfig.self, from: data)
        _ = try config.validated()
    }
}
