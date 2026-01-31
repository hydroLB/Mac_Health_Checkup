import SwiftUI
import MacHealthCheckupCore

struct SparklineView: View {
    /**
     Summary
     Render a lightweight sparkline line chart for a time-series.
     
     Inputs
     theme: Theme for colors.
     points: Time-series points.
     
     Outputs
     A SwiftUI view suitable for embedding in metric rows.
     
     Side effects
     None.
     
     Error handling
     None.
     
     Ties to other methods
     Consumed by metrics rows using `DashboardViewModel.historyPoints`.
     
     Why this exists
     Users want quick visual trend context without a heavy chart dependency.
     */

    let theme: Theme
    let points: [MetricHistoryStore.Point]

    init(theme: Theme, points: [MetricHistoryStore.Point]) {
        /**
         Summary
         Initialize the sparkline.
         
         Inputs
         theme: Theme.
         points: Series points.
         
         Outputs
         None.
         
         Side effects
         None.
         
         Error handling
         None.
         
         Ties to other methods
         Used by metrics UI.
         
         Why this exists
         Keeps call sites clean and avoids repeating scaling logic.
         */
        self.theme = theme
        self.points = points
    }

    var body: some View {
        /**
         Summary
         Draw the sparkline path.
         
         Inputs
         None.
         
         Outputs
         SwiftUI view.
         
         Side effects
         None.
         
         Error handling
         None.
         
         Ties to other methods
         Uses `scaledPoints`.
         
         Why this exists
         Provides a compact visualization for rapid scanning.
         */
        GeometryReader { geo in
            let pts = scaledPoints(in: geo.size)
            Path { path in
                guard let first = pts.first else { return }
                path.move(to: first)
                for p in pts.dropFirst() {
                    path.addLine(to: p)
                }
            }
            .stroke(theme.colors.section.opacity(0.85), style: StrokeStyle(lineWidth: 1.6, lineJoin: .round))
            .background(theme.colors.background.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .frame(height: 26)
    }

    private func scaledPoints(in size: CGSize) -> [CGPoint] {
        /**
         Summary
         Scale series points into view coordinates.
         
         Inputs
         size: Target view size.
         
         Outputs
         Array of scaled points.
         
         Side effects
         None.
         
         Error handling
         None.
         
         Ties to other methods
         Used by `body`.
         
         Why this exists
         Keeps scaling logic deterministic and independent of Swift Charts.
         */
        let values = points.map { $0.v }
        guard !values.isEmpty else { return [] }
        let minV = values.min() ?? 0
        let maxV = values.max() ?? 0
        let span = max(0.000_001, maxV - minV)

        let trimmed = points.suffix(120)
        let count = max(1, trimmed.count)
        let dx = size.width / CGFloat(max(1, count - 1))
        return trimmed.enumerated().map { idx, p in
            let x = CGFloat(idx) * dx
            let t = (p.v - minV) / span
            let y = size.height - (CGFloat(t) * size.height)
            return CGPoint(x: x, y: y)
        }
    }
}
